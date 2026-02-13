"""Base validator — abstract class implementing the Strategy Pattern.

Each validator is a standalone, independently testable unit.
New validators are added without modifying the engine.
"""

from abc import ABC, abstractmethod
import re
from typing import Optional

from app.validators.models import ValidationError, Severity, ErrorCode


class BaseValidator(ABC):
    """Abstract base for all design validators.

    Contract:
        - validate() is deterministic: same input → same output
        - validate() must complete in < 10ms per validator
        - validate() returns a list of ValidationError (empty = no issues)
        - No LLM calls, no network calls, no randomness
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging."""
        ...

    @abstractmethod
    def validate(self, design: dict, requirements: str = "") -> list[ValidationError]:
        """Run validation checks against the design.

        Args:
            design: Parsed architecture JSON from the Architect agent
            requirements: Original user requirements text

        Returns:
            List of ValidationError findings (empty if no issues)
        """
        ...

    # ── Helper Methods ──

    def _error(
        self,
        code: ErrorCode,
        severity: Severity,
        message: str,
        component: Optional[str] = None,
        field: Optional[str] = None,
        suggestion: Optional[str] = None,
        evidence: Optional[str] = None,
    ) -> ValidationError:
        """Convenience method to create a ValidationError."""
        return ValidationError(
            code=code,
            severity=severity,
            message=message,
            component=component,
            field=field,
            suggestion=suggestion,
            evidence=evidence,
        )

    def _flatten_text(self, design: dict) -> str:
        """Flatten entire design JSON into lowercase text for keyword searching."""
        import json
        return json.dumps(design, default=str).lower()

    def _get_components(self, design: dict) -> list[dict]:
        """Safely extract components list."""
        return design.get("components", [])

    def _get_non_functional(self, design: dict) -> dict:
        """Safely extract non_functional requirements."""
        return design.get("non_functional", {})

    def _get_deployment(self, design: dict) -> dict:
        """Safely extract deployment config."""
        return design.get("deployment", {})

    def _get_tech_decisions(self, design: dict) -> list[dict]:
        """Safely extract tech decisions."""
        return design.get("tech_decisions", [])

    def _parse_throughput(self, value) -> Optional[int]:
        """Parse throughput from various formats: '10K RPS', '10000', '10,000/sec', etc."""
        if isinstance(value, (int, float)):
            return int(value)
        if not isinstance(value, str):
            return None

        text = value.lower().replace(",", "").replace(" ", "")

        # Handle K/M suffixes
        multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
        for suffix, mult in multipliers.items():
            if suffix in text:
                try:
                    num = float(re.search(r"[\d.]+", text).group())
                    return int(num * mult)
                except (AttributeError, ValueError):
                    return None

        # Plain number
        try:
            return int(float(re.search(r"[\d.]+", text).group()))
        except (AttributeError, ValueError):
            return None

    def _parse_availability(self, value) -> Optional[float]:
        """Parse availability target: '99.99%', '99.9', 'four nines', etc."""
        if isinstance(value, (int, float)):
            return float(value) if value < 1 else float(value)
        if not isinstance(value, str):
            return None

        text = value.lower().strip().rstrip("%")

        # Named availability
        named = {
            "two nines": 99.0,
            "three nines": 99.9,
            "four nines": 99.99,
            "five nines": 99.999,
        }
        for name, val in named.items():
            if name in text:
                return val

        try:
            return float(text)
        except ValueError:
            return None

    def _contains_any(self, text: str, keywords: list[str]) -> bool:
        """Check if text contains any of the keywords (case-insensitive)."""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def _component_names_lower(self, design: dict) -> list[str]:
        """Get all component names as lowercase strings."""
        return [c.get("name", "").lower() for c in self._get_components(design)]

    def _all_tech_stack(self, design: dict) -> list[str]:
        """Get all tech stack items across all components as lowercase."""
        techs = []
        for comp in self._get_components(design):
            for tech in comp.get("tech_stack", []):
                techs.append(tech.lower())
        return techs
