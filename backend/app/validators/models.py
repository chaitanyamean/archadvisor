"""Validation models — error types, severity levels, scoring, and report structure.

All validation is deterministic: same input → same output, no randomness, no LLM calls.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Validation finding severity levels."""

    CRITICAL = "critical"  # Design is fundamentally broken
    HIGH = "high"          # Serious gap that will cause production issues
    MEDIUM = "medium"      # Should be addressed but not blocking
    LOW = "low"            # Suggestion for improvement


class ErrorCode(str, Enum):
    """Deterministic error codes for every validation rule.

    Naming convention: CATEGORY_SPECIFIC_ISSUE
    """

    # Schema errors
    SCHEMA_MISSING_FIELD = "SCHEMA_MISSING_FIELD"
    SCHEMA_INVALID_TYPE = "SCHEMA_INVALID_TYPE"
    SCHEMA_INVALID_VALUE = "SCHEMA_INVALID_VALUE"
    SCHEMA_EMPTY_COMPONENTS = "SCHEMA_EMPTY_COMPONENTS"

    # Availability errors
    SPOF_DATABASE = "SPOF_DATABASE"
    SPOF_CACHE = "SPOF_CACHE"
    SPOF_GATEWAY = "SPOF_GATEWAY"
    SPOF_QUEUE = "SPOF_QUEUE"
    SPOF_GENERIC = "SPOF_GENERIC"
    AVAIL_TARGET_UNREACHABLE = "AVAIL_TARGET_UNREACHABLE"
    AVAIL_COMPOSITE_BELOW_TARGET = "AVAIL_COMPOSITE_BELOW_TARGET"
    AVAIL_NO_MULTI_AZ = "AVAIL_NO_MULTI_AZ"
    AVAIL_NO_REPLICATION = "AVAIL_NO_REPLICATION"
    AVAIL_SINGLE_REGION_HIGH_SLA = "AVAIL_SINGLE_REGION_HIGH_SLA"

    # Capacity errors
    CAP_THROUGHPUT_EXCEEDS_BENCHMARK = "CAP_THROUGHPUT_EXCEEDS_BENCHMARK"
    CAP_NO_AUTOSCALING = "CAP_NO_AUTOSCALING"
    CAP_SINGLE_NODE_HIGH_RPS = "CAP_SINGLE_NODE_HIGH_RPS"
    CAP_NO_SHARDING = "CAP_NO_SHARDING"
    CAP_HOTSPOT_RISK = "CAP_HOTSPOT_RISK"
    CAP_NO_SCALING_STRATEGY = "CAP_NO_SCALING_STRATEGY"

    # Consistency errors
    CONSIST_EVENTUAL_NO_JUSTIFICATION = "CONSIST_EVENTUAL_NO_JUSTIFICATION"
    CONSIST_STRONG_MULTI_REGION_LATENCY = "CONSIST_STRONG_MULTI_REGION_LATENCY"
    CONSIST_STRONG_WITH_EVENTUAL_DB = "CONSIST_STRONG_WITH_EVENTUAL_DB"
    CONSIST_MISSING_STRATEGY = "CONSIST_MISSING_STRATEGY"

    # Contradiction errors
    CONTRA_EVENT_DRIVEN_NO_BROKER = "CONTRA_EVENT_DRIVEN_NO_BROKER"
    CONTRA_STRONG_CONSIST_EVENTUAL_DB = "CONTRA_STRONG_CONSIST_EVENTUAL_DB"
    CONTRA_SERVERLESS_WITH_K8S = "CONTRA_SERVERLESS_WITH_K8S"
    CONTRA_LOW_LATENCY_MANY_HOPS = "CONTRA_LOW_LATENCY_MANY_HOPS"
    CONTRA_MULTI_REGION_SINGLE_DEPLOY = "CONTRA_MULTI_REGION_SINGLE_DEPLOY"
    CONTRA_STYLE_MISMATCH = "CONTRA_STYLE_MISMATCH"
    CONTRA_STATELESS_WITH_LOCAL_STATE = "CONTRA_STATELESS_WITH_LOCAL_STATE"

    # Operational complexity errors
    OPS_TOO_MANY_SERVICES = "OPS_TOO_MANY_SERVICES"
    OPS_OVER_ENGINEERED = "OPS_OVER_ENGINEERED"
    OPS_KAFKA_LOW_THROUGHPUT = "OPS_KAFKA_LOW_THROUGHPUT"
    OPS_MULTI_REGION_MVP = "OPS_MULTI_REGION_MVP"
    OPS_ENTERPRISE_FOR_STARTUP = "OPS_ENTERPRISE_FOR_STARTUP"

    # Missing requirement errors
    MISSING_AUTH = "MISSING_AUTH"
    MISSING_ANALYTICS = "MISSING_ANALYTICS"
    MISSING_DR = "MISSING_DR"
    MISSING_MONITORING = "MISSING_MONITORING"
    MISSING_LOGGING = "MISSING_LOGGING"
    MISSING_RATE_LIMITING = "MISSING_RATE_LIMITING"
    MISSING_ENCRYPTION = "MISSING_ENCRYPTION"
    MISSING_SEARCH = "MISSING_SEARCH"
    MISSING_NOTIFICATION = "MISSING_NOTIFICATION"
    MISSING_CACHING = "MISSING_CACHING"


class ValidationError(BaseModel):
    """A single validation finding."""

    code: ErrorCode
    severity: Severity
    message: str
    component: Optional[str] = None  # Which component is affected
    field: Optional[str] = None      # Which JSON field triggered this
    suggestion: Optional[str] = None # How to fix it
    evidence: Optional[str] = None   # What data triggered the finding

    class Config:
        use_enum_values = True


class ScoreBreakdown(BaseModel):
    """Score breakdown by category. Each starts at max and gets penalties subtracted."""

    reliability: float = Field(default=30.0, description="Max 30 — availability, SPOF, replication")
    scalability: float = Field(default=25.0, description="Max 25 — throughput, sharding, auto-scaling")
    consistency: float = Field(default=15.0, description="Max 15 — data consistency, contradiction-free")
    security: float = Field(default=15.0, description="Max 15 — auth, encryption, compliance")
    operational: float = Field(default=15.0, description="Max 15 — simplicity, right-sized, manageable")

    @property
    def total(self) -> float:
        return max(0, self.reliability + self.scalability + self.consistency + self.security + self.operational)


# Penalty weights per severity per category
PENALTY_WEIGHTS = {
    Severity.CRITICAL: {
        "reliability": 15,
        "scalability": 12,
        "consistency": 8,
        "security": 8,
        "operational": 8,
    },
    Severity.HIGH: {
        "reliability": 8,
        "scalability": 6,
        "consistency": 5,
        "security": 5,
        "operational": 5,
    },
    Severity.MEDIUM: {
        "reliability": 4,
        "scalability": 3,
        "consistency": 3,
        "security": 3,
        "operational": 3,
    },
    Severity.LOW: {
        "reliability": 1,
        "scalability": 1,
        "consistency": 1,
        "security": 1,
        "operational": 1,
    },
}

# Map error codes to scoring categories
ERROR_CATEGORY_MAP = {
    # Reliability
    ErrorCode.SPOF_DATABASE: "reliability",
    ErrorCode.SPOF_CACHE: "reliability",
    ErrorCode.SPOF_GATEWAY: "reliability",
    ErrorCode.SPOF_QUEUE: "reliability",
    ErrorCode.SPOF_GENERIC: "reliability",
    ErrorCode.AVAIL_TARGET_UNREACHABLE: "reliability",
    ErrorCode.AVAIL_COMPOSITE_BELOW_TARGET: "reliability",
    ErrorCode.AVAIL_NO_MULTI_AZ: "reliability",
    ErrorCode.AVAIL_NO_REPLICATION: "reliability",
    ErrorCode.AVAIL_SINGLE_REGION_HIGH_SLA: "reliability",

    # Scalability
    ErrorCode.CAP_THROUGHPUT_EXCEEDS_BENCHMARK: "scalability",
    ErrorCode.CAP_NO_AUTOSCALING: "scalability",
    ErrorCode.CAP_SINGLE_NODE_HIGH_RPS: "scalability",
    ErrorCode.CAP_NO_SHARDING: "scalability",
    ErrorCode.CAP_HOTSPOT_RISK: "scalability",
    ErrorCode.CAP_NO_SCALING_STRATEGY: "scalability",

    # Consistency
    ErrorCode.CONSIST_EVENTUAL_NO_JUSTIFICATION: "consistency",
    ErrorCode.CONSIST_STRONG_MULTI_REGION_LATENCY: "consistency",
    ErrorCode.CONSIST_STRONG_WITH_EVENTUAL_DB: "consistency",
    ErrorCode.CONSIST_MISSING_STRATEGY: "consistency",
    ErrorCode.CONTRA_EVENT_DRIVEN_NO_BROKER: "consistency",
    ErrorCode.CONTRA_STRONG_CONSIST_EVENTUAL_DB: "consistency",
    ErrorCode.CONTRA_SERVERLESS_WITH_K8S: "consistency",
    ErrorCode.CONTRA_LOW_LATENCY_MANY_HOPS: "consistency",
    ErrorCode.CONTRA_MULTI_REGION_SINGLE_DEPLOY: "consistency",
    ErrorCode.CONTRA_STYLE_MISMATCH: "consistency",
    ErrorCode.CONTRA_STATELESS_WITH_LOCAL_STATE: "consistency",

    # Security
    ErrorCode.MISSING_AUTH: "security",
    ErrorCode.MISSING_ENCRYPTION: "security",

    # Operational
    ErrorCode.OPS_TOO_MANY_SERVICES: "operational",
    ErrorCode.OPS_OVER_ENGINEERED: "operational",
    ErrorCode.OPS_KAFKA_LOW_THROUGHPUT: "operational",
    ErrorCode.OPS_MULTI_REGION_MVP: "operational",
    ErrorCode.OPS_ENTERPRISE_FOR_STARTUP: "operational",
    ErrorCode.MISSING_ANALYTICS: "operational",
    ErrorCode.MISSING_DR: "reliability",
    ErrorCode.MISSING_MONITORING: "operational",
    ErrorCode.MISSING_LOGGING: "operational",
    ErrorCode.MISSING_RATE_LIMITING: "security",
    ErrorCode.MISSING_SEARCH: "operational",
    ErrorCode.MISSING_NOTIFICATION: "operational",
    ErrorCode.MISSING_CACHING: "scalability",

    # Schema errors don't fit a category — apply to reliability
    ErrorCode.SCHEMA_MISSING_FIELD: "reliability",
    ErrorCode.SCHEMA_INVALID_TYPE: "reliability",
    ErrorCode.SCHEMA_INVALID_VALUE: "reliability",
    ErrorCode.SCHEMA_EMPTY_COMPONENTS: "reliability",
}


class ValidationReport(BaseModel):
    """Complete validation report — the output of the validation engine."""

    passed: bool = Field(description="True if no critical errors and score >= 60")
    score: float = Field(description="Architecture quality score 0-100")
    score_breakdown: ScoreBreakdown
    summary: dict = Field(
        description="Count of errors by severity",
        default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0},
    )
    errors: list[ValidationError] = Field(default_factory=list)
    verdict: str = Field(default="", description="Human-readable verdict")

    @classmethod
    def build(cls, errors: list[ValidationError]) -> "ValidationReport":
        """Build a complete report from a list of validation errors."""
        # Count by severity
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for err in errors:
            summary[err.severity] += 1

        # Compute score
        score_breakdown = ScoreBreakdown()
        for err in errors:
            category = ERROR_CATEGORY_MAP.get(ErrorCode(err.code), "operational")
            penalty = PENALTY_WEIGHTS.get(Severity(err.severity), {}).get(category, 2)
            current = getattr(score_breakdown, category)
            setattr(score_breakdown, category, max(0, current - penalty))

        score = score_breakdown.total

        # Determine pass/fail
        passed = summary["critical"] == 0 and score >= 60

        # Generate verdict
        if passed and score >= 80:
            verdict = f"PASS — Strong design (score: {score:.0f}/100). Ready for review."
        elif passed:
            verdict = f"PASS — Acceptable design (score: {score:.0f}/100) with {summary['high']} high-severity findings to address."
        elif summary["critical"] > 0:
            verdict = f"FAIL — {summary['critical']} critical issue(s) must be resolved before review. Score: {score:.0f}/100."
        else:
            verdict = f"FAIL — Score {score:.0f}/100 is below threshold (60). Address high-severity findings."

        return cls(
            passed=passed,
            score=round(score, 1),
            score_breakdown=score_breakdown,
            summary=summary,
            errors=sorted(errors, key=lambda e: list(Severity).index(Severity(e.severity))),
            verdict=verdict,
        )
