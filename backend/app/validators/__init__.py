"""Design Validator — deterministic validation layer for architecture designs.

Usage:
    from app.validators import validation_engine

    report = validation_engine.validate(design_json, requirements_text)
    if not report.passed:
        # Route back to Architect with report.errors
"""

from app.validators.engine import ValidationEngine, validation_engine
from app.validators.models import ValidationReport, ValidationError, Severity, ErrorCode

__all__ = [
    "ValidationEngine",
    "validation_engine",
    "ValidationReport",
    "ValidationError",
    "Severity",
    "ErrorCode",
]
