"""Consistency Validator — data consistency model checks and justification enforcement."""

from app.validators.base import BaseValidator
from app.validators.models import ValidationError, Severity, ErrorCode
from app.validators.reference_data import EVENTUALLY_CONSISTENT_DBS


class ConsistencyValidator(BaseValidator):
    """Validates data consistency claims and their feasibility."""

    @property
    def name(self) -> str:
        return "ConsistencyValidator"

    def validate(self, design: dict, requirements: str = "") -> list[ValidationError]:
        errors = []

        nf = self._get_non_functional(design)
        components = self._get_components(design)
        deployment = self._get_deployment(design)
        tech_decisions = self._get_tech_decisions(design)
        flat_text = self._flatten_text(design)

        consistency = nf.get("data_consistency", "").lower().strip()

        if not consistency:
            errors.append(self._error(
                code=ErrorCode.CONSIST_MISSING_STRATEGY,
                severity=Severity.MEDIUM,
                message="No data consistency strategy declared in non_functional requirements",
                field="non_functional.data_consistency",
                suggestion="Specify: 'strong', 'eventual', or 'causal'",
            ))
            return errors

        # ── 1. Eventual Consistency must be justified ──
        if consistency == "eventual":
            errors.extend(self._check_eventual_justification(tech_decisions))

        # ── 2. Strong Consistency + Multi-Region = latency risk ──
        if consistency == "strong":
            errors.extend(self._check_strong_multi_region(deployment, flat_text))

        # ── 3. Strong Consistency + Eventually Consistent DB = contradiction ──
        if consistency == "strong":
            errors.extend(self._check_strong_with_eventual_db(components))

        return errors

    def _check_eventual_justification(self, tech_decisions: list[dict]) -> list[ValidationError]:
        """Eventual consistency must be a deliberate choice with justification."""
        errors = []

        consistency_keywords = [
            "eventual", "consistency", "CAP", "trade-off", "tradeoff",
            "latency vs consistency", "availability over consistency",
        ]

        has_justification = False
        for decision in tech_decisions:
            decision_text = f"{decision.get('decision', '')} {decision.get('reasoning', '')}".lower()
            if any(kw.lower() in decision_text for kw in consistency_keywords):
                has_justification = True
                break

        if not has_justification:
            errors.append(self._error(
                code=ErrorCode.CONSIST_EVENTUAL_NO_JUSTIFICATION,
                severity=Severity.MEDIUM,
                message="Eventual consistency declared but no justification in tech_decisions",
                field="non_functional.data_consistency",
                suggestion=(
                    "Add a tech_decision explaining why eventual consistency was chosen: "
                    "e.g., CAP theorem tradeoff, latency requirements, read-heavy workload"
                ),
            ))

        return errors

    def _check_strong_multi_region(self, deployment: dict, flat_text: str) -> list[ValidationError]:
        """Strong consistency + multi-region = high cross-region latency risk."""
        errors = []

        multi_region_keywords = [
            "multi-region", "multi_region", "cross-region", "geo-distributed",
            "global deployment", "multiple regions",
        ]

        is_multi_region = self._contains_any(flat_text, multi_region_keywords)
        regions = deployment.get("regions", [])
        if len(regions) > 1:
            is_multi_region = True

        if is_multi_region:
            errors.append(self._error(
                code=ErrorCode.CONSIST_STRONG_MULTI_REGION_LATENCY,
                severity=Severity.HIGH,
                message=(
                    "Strong consistency with multi-region deployment will incur high "
                    "cross-region latency (50-200ms per write for consensus)"
                ),
                suggestion=(
                    "Consider: (1) Causal consistency with conflict resolution, "
                    "(2) Single-leader with read replicas, or "
                    "(3) Accept eventual consistency with compensating transactions"
                ),
            ))

        return errors

    def _check_strong_with_eventual_db(self, components: list[dict]) -> list[ValidationError]:
        """Strong consistency claim but using an eventually consistent database."""
        errors = []

        for comp in components:
            if comp.get("type", "").lower() != "database":
                continue

            comp_name = comp.get("name", "Unknown")
            tech_stack = [t.lower() for t in comp.get("tech_stack", [])]
            comp_text = f"{comp_name} {' '.join(tech_stack)}".lower()

            for db in EVENTUALLY_CONSISTENT_DBS:
                if db in comp_text:
                    errors.append(self._error(
                        code=ErrorCode.CONSIST_STRONG_WITH_EVENTUAL_DB,
                        severity=Severity.CRITICAL,
                        message=(
                            f"Design claims 'strong' consistency but uses '{db}' "
                            f"in '{comp_name}', which is eventually consistent by default"
                        ),
                        component=comp_name,
                        suggestion=(
                            f"Either: (1) Switch to a strongly consistent DB (PostgreSQL, MySQL, CockroachDB), "
                            f"(2) Change consistency model to 'eventual', or "
                            f"(3) Use '{db}' with strong consistency settings (e.g., DynamoDB strongly consistent reads)"
                        ),
                    ))
                    break

        return errors
