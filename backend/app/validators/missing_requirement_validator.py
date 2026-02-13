"""Missing Requirement Validator — cross-checks user requirements against architecture components.

If the user asks for analytics, the architecture must include an analytics component.
If they mention auth, there must be an auth strategy. And so on.
"""

from app.validators.base import BaseValidator
from app.validators.models import ValidationError, Severity, ErrorCode
from app.validators.reference_data import REQUIREMENT_COMPONENT_MAP


class MissingRequirementValidator(BaseValidator):
    """Detects when user requirements are not addressed in the architecture."""

    @property
    def name(self) -> str:
        return "MissingRequirementValidator"

    def validate(self, design: dict, requirements: str = "") -> list[ValidationError]:
        errors = []

        if not requirements:
            return errors

        flat_design = self._flatten_text(design)
        req_lower = requirements.lower()

        for req_name, config in REQUIREMENT_COMPONENT_MAP.items():
            keywords = config["keywords"]
            error_code_str = config["error_code"]

            # Check if requirement mentions this capability
            requirement_mentions = any(kw.lower() in req_lower for kw in keywords)
            if not requirement_mentions:
                continue

            # Check if architecture addresses it
            architecture_addresses = any(kw.lower() in flat_design for kw in keywords)

            # Also check component names and responsibilities
            if not architecture_addresses:
                for comp in self._get_components(design):
                    comp_text = (
                        f"{comp.get('name', '')} {comp.get('responsibility', '')} "
                        f"{' '.join(comp.get('tech_stack', []))}"
                    ).lower()
                    if any(kw.lower() in comp_text for kw in keywords):
                        architecture_addresses = True
                        break

            # Also check non_functional and deployment sections
            if not architecture_addresses:
                nf_text = str(self._get_non_functional(design)).lower()
                deploy_text = str(self._get_deployment(design)).lower()
                decisions_text = str(self._get_tech_decisions(design)).lower()
                combined = f"{nf_text} {deploy_text} {decisions_text}"
                if any(kw.lower() in combined for kw in keywords):
                    architecture_addresses = True

            if not architecture_addresses:
                try:
                    error_code = ErrorCode(error_code_str)
                except ValueError:
                    error_code = ErrorCode.SCHEMA_MISSING_FIELD

                # Determine severity based on requirement type
                severity = self._get_severity_for_requirement(req_name)

                # Find which keyword matched in requirements
                matched_keyword = next(
                    (kw for kw in keywords if kw.lower() in req_lower), keywords[0]
                )

                errors.append(self._error(
                    code=error_code,
                    severity=severity,
                    message=f"Requirements mention '{matched_keyword}' but architecture has no corresponding component or strategy",
                    suggestion=f"Add a {req_name} component or address {req_name} in the architecture",
                    evidence=f"Keyword '{matched_keyword}' found in requirements but not in design",
                ))

        return errors

    def _get_severity_for_requirement(self, req_name: str) -> Severity:
        """Determine severity based on requirement type."""
        critical_requirements = {"auth", "encryption"}
        high_requirements = {"disaster_recovery", "monitoring", "rate_limiting"}
        medium_requirements = {"analytics", "search", "notification", "caching", "logging"}

        if req_name in critical_requirements:
            return Severity.HIGH
        elif req_name in high_requirements:
            return Severity.HIGH
        elif req_name in medium_requirements:
            return Severity.MEDIUM
        return Severity.LOW
