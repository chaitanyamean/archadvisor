"""Schema Validator — validates required fields, types, and value constraints."""

from app.validators.base import BaseValidator
from app.validators.models import ValidationError, Severity, ErrorCode

# Required top-level keys
REQUIRED_KEYS = ["overview", "architecture_style", "components", "non_functional", "tech_decisions", "deployment"]

# Valid architecture styles
VALID_STYLES = {"microservices", "event-driven", "event_driven", "monolith", "serverless", "hybrid", "modular_monolith"}

# Valid consistency models
VALID_CONSISTENCY = {"strong", "eventual", "causal"}


class SchemaValidator(BaseValidator):
    """Validates the structural integrity of the architecture JSON."""

    @property
    def name(self) -> str:
        return "SchemaValidator"

    def validate(self, design: dict, requirements: str = "") -> list[ValidationError]:
        errors = []

        # 1. Required top-level keys
        for key in REQUIRED_KEYS:
            if key not in design:
                errors.append(self._error(
                    code=ErrorCode.SCHEMA_MISSING_FIELD,
                    severity=Severity.CRITICAL,
                    message=f"Required field '{key}' is missing from architecture design",
                    field=key,
                    suggestion=f"Add '{key}' to the architecture JSON",
                ))

        # 2. Components must be non-empty list
        components = design.get("components")
        if components is not None:
            if not isinstance(components, list):
                errors.append(self._error(
                    code=ErrorCode.SCHEMA_INVALID_TYPE,
                    severity=Severity.CRITICAL,
                    message="'components' must be a list",
                    field="components",
                ))
            elif len(components) == 0:
                errors.append(self._error(
                    code=ErrorCode.SCHEMA_EMPTY_COMPONENTS,
                    severity=Severity.CRITICAL,
                    message="'components' list is empty — no architecture components defined",
                    field="components",
                    suggestion="Define at least one component in the architecture",
                ))
            else:
                # Validate each component has required sub-fields
                for i, comp in enumerate(components):
                    if not isinstance(comp, dict):
                        continue
                    for required_field in ["name", "type", "responsibility"]:
                        if required_field not in comp:
                            errors.append(self._error(
                                code=ErrorCode.SCHEMA_MISSING_FIELD,
                                severity=Severity.HIGH,
                                message=f"Component #{i+1} is missing '{required_field}'",
                                component=comp.get("name", f"Component #{i+1}"),
                                field=f"components[{i}].{required_field}",
                            ))

        # 3. Architecture style validation
        style = design.get("architecture_style", "")
        if style and style.lower().replace(" ", "_") not in VALID_STYLES:
            errors.append(self._error(
                code=ErrorCode.SCHEMA_INVALID_VALUE,
                severity=Severity.MEDIUM,
                message=f"Architecture style '{style}' is not a recognized pattern",
                field="architecture_style",
                suggestion=f"Use one of: {', '.join(sorted(VALID_STYLES))}",
            ))

        # 4. Non-functional requirements validation
        nf = design.get("non_functional", {})
        if isinstance(nf, dict):
            # Availability target format
            avail = nf.get("availability_target", "")
            if avail:
                parsed = self._parse_availability(avail)
                if parsed is None:
                    errors.append(self._error(
                        code=ErrorCode.SCHEMA_INVALID_VALUE,
                        severity=Severity.MEDIUM,
                        message=f"Cannot parse availability target: '{avail}'",
                        field="non_functional.availability_target",
                        suggestion="Use format like '99.99%' or '99.9%'",
                    ))
                elif parsed < 90 or parsed > 99.9999:
                    errors.append(self._error(
                        code=ErrorCode.SCHEMA_INVALID_VALUE,
                        severity=Severity.MEDIUM,
                        message=f"Availability target {avail} is outside realistic range (90% - 99.9999%)",
                        field="non_functional.availability_target",
                    ))

            # Data consistency model
            consistency = nf.get("data_consistency", "")
            if consistency and consistency.lower() not in VALID_CONSISTENCY:
                errors.append(self._error(
                    code=ErrorCode.SCHEMA_INVALID_VALUE,
                    severity=Severity.MEDIUM,
                    message=f"Data consistency model '{consistency}' is not recognized",
                    field="non_functional.data_consistency",
                    suggestion=f"Use one of: {', '.join(sorted(VALID_CONSISTENCY))}",
                ))

        # 5. Tech decisions should have reasoning
        decisions = design.get("tech_decisions", [])
        if isinstance(decisions, list):
            for i, dec in enumerate(decisions):
                if isinstance(dec, dict):
                    if not dec.get("reasoning"):
                        errors.append(self._error(
                            code=ErrorCode.SCHEMA_MISSING_FIELD,
                            severity=Severity.LOW,
                            message=f"Tech decision #{i+1} '{dec.get('decision', 'unknown')}' has no reasoning",
                            field=f"tech_decisions[{i}].reasoning",
                            suggestion="Always justify technology choices",
                        ))

        return errors
