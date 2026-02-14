"""Validation Engine — orchestrates all validators, computes score, produces report.

This is the main entry point for design validation. It runs all registered
validators against the design and produces a comprehensive ValidationReport.

Usage:
    engine = ValidationEngine()
    report = engine.validate(design_json, requirements_text)
    if not report.passed:
        # Send back to architect with report.errors
"""

import time
import json
from typing import Optional, Union

import structlog

from app.validators.base import BaseValidator
from app.validators.models import ValidationError, ValidationReport

# Import all validators
from app.validators.schema_validator import SchemaValidator
from app.validators.availability_validator import AvailabilityValidator
from app.validators.capacity_validator import CapacityValidator
from app.validators.consistency_validator import ConsistencyValidator
from app.validators.contradiction_validator import ContradictionValidator
from app.validators.operational_complexity_validator import OperationalComplexityValidator
from app.validators.missing_requirement_validator import MissingRequirementValidator
from app.validators.domain_pattern_validator import DomainPatternValidator

logger = structlog.get_logger()


class ValidationEngine:
    """Orchestrates all validators and produces a unified validation report.

    Design principles:
        - Deterministic: same input → same output
        - Fast: < 50ms total for all validators
        - Extensible: add validators without modifying engine
        - Observable: logs every validation run with timing
    """

    def __init__(self, validators: Optional[list[BaseValidator]] = None):
        """Initialize with default validators or custom list.

        Args:
            validators: Optional list of validators. If None, uses all defaults.
        """
        self.validators = validators or self._default_validators()

    @staticmethod
    def _default_validators() -> list[BaseValidator]:
        """Create the default validator chain in execution order."""
        return [
            SchemaValidator(),           # Must run first — others depend on valid structure
            AvailabilityValidator(),     # SPOF detection + composite availability math
            CapacityValidator(),         # Throughput benchmarks + scaling checks
            ConsistencyValidator(),      # Data consistency model checks
            ContradictionValidator(),    # Cross-field contradiction detection
            OperationalComplexityValidator(),  # Over-engineering detection
            MissingRequirementValidator(),     # Requirements coverage
            DomainPatternValidator()           # Domain-specific pattern checks
        ]

    def validate(self, design: Union[dict, str], requirements: str = "") -> ValidationReport:
        """Run all validators against the design and produce a report.

        Args:
            design: Architecture JSON (dict or JSON string)
            requirements: Original user requirements text

        Returns:
            ValidationReport with pass/fail, score, and all errors
        """
        start_time = time.perf_counter()

        # Parse JSON string if needed
        if isinstance(design, str):
            try:
                design = json.loads(design)
            except json.JSONDecodeError as e:
                return ValidationReport.build([
                    ValidationError(
                        code="SCHEMA_INVALID_TYPE",
                        severity="critical",
                        message=f"Cannot parse architecture JSON: {str(e)}",
                        suggestion="Ensure the architecture output is valid JSON",
                    )
                ])

        # Run all validators
        all_errors: list[ValidationError] = []
        validator_timings: dict[str, float] = {}

        for validator in self.validators:
            v_start = time.perf_counter()
            try:
                errors = validator.validate(design, requirements)
                all_errors.extend(errors)
            except Exception as e:
                logger.error(
                    "validator_failed",
                    validator=validator.name,
                    error=str(e),
                )
                # Don't let one broken validator kill the whole pipeline
                all_errors.append(ValidationError(
                    code="SCHEMA_INVALID_TYPE",
                    severity="medium",
                    message=f"Validator '{validator.name}' crashed: {str(e)}",
                ))
            finally:
                v_duration = (time.perf_counter() - v_start) * 1000
                validator_timings[validator.name] = round(v_duration, 2)

        # Build report
        report = ValidationReport.build(all_errors)

        total_duration = (time.perf_counter() - start_time) * 1000

        logger.info(
            "validation_complete",
            passed=report.passed,
            score=report.score,
            summary=report.summary,
            total_errors=len(all_errors),
            duration_ms=round(total_duration, 2),
            validator_timings=validator_timings,
        )

        return report

    def validate_with_context(
        self,
        design: Union[dict, str],
        requirements: str = "",
        previous_report: Optional[ValidationReport] = None,
    ) -> ValidationReport:
        """Validate with awareness of previous validation (for revision loops).

        Checks if the same critical errors persist across revisions.

        Args:
            design: Current architecture JSON
            requirements: Original requirements
            previous_report: Report from previous validation round

        Returns:
            ValidationReport with additional context about recurring issues
        """
        report = self.validate(design, requirements)

        if previous_report:
            # Check for recurring critical errors
            prev_critical_codes = {
                e.code for e in previous_report.errors if e.severity == "critical"
            }
            curr_critical_codes = {
                e.code for e in report.errors if e.severity == "critical"
            }

            recurring = prev_critical_codes & curr_critical_codes
            if recurring:
                report.verdict += (
                    f" WARNING: {len(recurring)} critical issue(s) persist from previous revision: "
                    f"{', '.join(recurring)}"
                )

        return report

    def add_validator(self, validator: BaseValidator) -> None:
        """Add a custom validator to the chain."""
        self.validators.append(validator)

    def remove_validator(self, validator_name: str) -> None:
        """Remove a validator by name."""
        self.validators = [v for v in self.validators if v.name != validator_name]


# Module-level singleton
validation_engine = ValidationEngine()
