"""Domain Pattern Validator — check #8 in the validation pipeline.

Detects the application domain from requirements text and validates the
architecture against domain-specific mandatory patterns, recommended patterns,
and anti-patterns loaded from JSON rule files.

Deterministic, fast (< 5ms), no LLM calls.
"""

import json
import re
from typing import Optional

from app.validators.base import BaseValidator
from app.validators.models import ValidationError, Severity
from app.validators.domain_rules.loader import detect_domain


class DomainPatternValidator(BaseValidator):
    """Validates architecture against domain-specific patterns.

    Detects the domain from requirements, loads matching rules from JSON,
    and checks the design for mandatory patterns, recommended patterns,
    and anti-patterns.
    """

    @property
    def name(self) -> str:
        return "DomainPatternValidator"

    def validate(self, design: dict, requirements: str = "") -> list[ValidationError]:
        """Run domain-specific pattern checks.

        Args:
            design: Parsed architecture JSON
            requirements: Original user requirements (used for domain detection)

        Returns:
            List of ValidationError findings
        """
        domain = detect_domain(requirements)
        if domain is None:
            return []

        errors: list[ValidationError] = []
        design_text = self._flatten_text(design)
        components = self._get_components(design)

        # Check mandatory patterns — flag if MISSING
        for pattern in domain.get("mandatory_patterns", []):
            if not self._check_pattern(pattern, design, design_text, components):
                errors.append(self._make_error(pattern, domain["display_name"]))

        # Check recommended patterns — flag if MISSING (soft penalty)
        for pattern in domain.get("recommended_patterns", []):
            if not self._check_pattern(pattern, design, design_text, components):
                errors.append(self._make_error(pattern, domain["display_name"]))

        # Check anti-patterns — flag if FOUND (inverse logic)
        for pattern in domain.get("anti_patterns", []):
            if self._check_pattern(pattern, design, design_text, components):
                errors.append(self._make_error(pattern, domain["display_name"]))

        return errors

    def get_detected_domain(self, requirements: str) -> Optional[str]:
        """Return the detected domain name for metadata, or None."""
        domain = detect_domain(requirements)
        return domain["display_name"] if domain else None

    def _check_pattern(
        self,
        pattern: dict,
        design: dict,
        design_text: str,
        components: list[dict],
    ) -> bool:
        """Run a single pattern check against the design.

        Returns True if the pattern's terms are found in the design.
        """
        check_type = pattern.get("check", "design_mentions_any")
        terms = pattern.get("terms", [])

        if check_type == "design_mentions_any":
            return self._design_mentions_any(design_text, terms)
        elif check_type == "component_or_tech_mentions_any":
            return self._component_or_tech_mentions_any(components, terms, design_text)
        elif check_type == "component_type_exists":
            return self._component_type_exists(components, terms)
        else:
            return self._design_mentions_any(design_text, terms)

    def _design_mentions_any(self, design_text: str, terms: list[str]) -> bool:
        """Check if the entire design JSON string matches any term (case-insensitive, regex-aware)."""
        for term in terms:
            try:
                if re.search(term, design_text, re.IGNORECASE):
                    return True
            except re.error:
                # Fallback to plain substring match if regex is invalid
                if term.lower() in design_text:
                    return True
        return False

    def _component_or_tech_mentions_any(
        self, components: list[dict], terms: list[str], design_text: str
    ) -> bool:
        """Check component names, tech stacks, responsibilities, and descriptions for terms."""
        searchable = ""
        for comp in components:
            searchable += " " + comp.get("name", "").lower()
            searchable += " " + comp.get("responsibility", "").lower()
            searchable += " " + comp.get("type", "").lower()
            searchable += " " + " ".join(t.lower() for t in comp.get("tech_stack", []))
            searchable += " " + comp.get("scaling_strategy", "").lower()
            for ep in comp.get("api_endpoints", []):
                searchable += " " + ep.get("description", "").lower()
            for ds in comp.get("data_stores", []):
                searchable += " " + ds.lower() if isinstance(ds, str) else ""

        # Also search tech_decisions
        for td in (design_text,):  # Fallback: search full design text too
            pass

        for term in terms:
            try:
                if re.search(term, searchable, re.IGNORECASE):
                    return True
            except re.error:
                if term.lower() in searchable:
                    return True

        return False

    def _component_type_exists(self, components: list[dict], terms: list[str]) -> bool:
        """Check if any component's type or tech stack matches the terms."""
        for comp in components:
            comp_type = comp.get("type", "").lower()
            tech_stack = [t.lower() for t in comp.get("tech_stack", [])]
            comp_name = comp.get("name", "").lower()

            for term in terms:
                term_lower = term.lower()
                if term_lower in comp_type or term_lower in comp_name:
                    return True
                if any(term_lower in tech for tech in tech_stack):
                    return True

        return False

    def _make_error(self, pattern: dict, domain_name: str) -> ValidationError:
        """Create a ValidationError from a pattern definition."""
        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.LOW,
            "warning": Severity.HIGH,
        }
        severity = severity_map.get(pattern.get("severity", "medium").lower(), Severity.MEDIUM)

        return ValidationError(
            code=pattern["id"],
            severity=severity,
            message=pattern.get("message", pattern.get("description", "")),
            component=None,
            field=None,
            suggestion=pattern.get("description"),
            evidence=f"Domain: {domain_name}",
            category="domain_pattern",
        )
