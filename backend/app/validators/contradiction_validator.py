"""Contradiction Validator — detects internal contradictions across design fields.

This catches the most embarrassing LLM mistakes: when different parts of the
generated architecture contradict each other.
"""

from typing import Optional

from app.validators.base import BaseValidator
from app.validators.models import ValidationError, Severity, ErrorCode
from app.validators.reference_data import MESSAGE_BROKERS, EVENTUALLY_CONSISTENT_DBS


class ContradictionValidator(BaseValidator):
    """Detects contradictions between architecture claims and implementation."""

    @property
    def name(self) -> str:
        return "ContradictionValidator"

    def validate(self, design: dict, requirements: str = "") -> list[ValidationError]:
        errors = []

        style = design.get("architecture_style", "").lower().replace(" ", "_")
        nf = self._get_non_functional(design)
        components = self._get_components(design)
        deployment = self._get_deployment(design)
        flat_text = self._flatten_text(design)
        all_techs = self._all_tech_stack(design)
        comp_types = [c.get("type", "").lower() for c in components]
        comp_names = self._component_names_lower(design)

        # ── 1. Event-Driven but no Message Broker ──
        if "event" in style:
            has_broker = any(
                broker in flat_text for broker in MESSAGE_BROKERS
            )
            has_queue_component = "queue" in comp_types
            if not has_broker and not has_queue_component:
                errors.append(self._error(
                    code=ErrorCode.CONTRA_EVENT_DRIVEN_NO_BROKER,
                    severity=Severity.CRITICAL,
                    message="Architecture style is 'event-driven' but no message broker found in components",
                    suggestion="Add a message broker: Kafka, RabbitMQ, SQS, Pulsar, or Redis Streams",
                    evidence=f"Style: {style}, searched for: {', '.join(list(MESSAGE_BROKERS)[:6])}",
                ))

        # ── 2. Strong Consistency + Eventually Consistent DB ──
        consistency = nf.get("data_consistency", "").lower()
        if consistency == "strong":
            for tech in all_techs:
                for db in EVENTUALLY_CONSISTENT_DBS:
                    if db in tech:
                        errors.append(self._error(
                            code=ErrorCode.CONTRA_STRONG_CONSIST_EVENTUAL_DB,
                            severity=Severity.CRITICAL,
                            message=f"Claims 'strong' consistency but tech stack includes '{db}' (eventually consistent)",
                            suggestion=f"Either switch DB or change consistency model to 'eventual'",
                        ))
                        break

        # ── 3. Serverless + Kubernetes ──
        if "serverless" in style:
            k8s_keywords = ["kubernetes", "k8s", "eks", "gke", "aks", "helm"]
            if any(kw in flat_text for kw in k8s_keywords):
                errors.append(self._error(
                    code=ErrorCode.CONTRA_SERVERLESS_WITH_K8S,
                    severity=Severity.HIGH,
                    message="Architecture style is 'serverless' but Kubernetes is mentioned in deployment",
                    suggestion="Choose one: true serverless (Lambda/Cloud Run) or container orchestration (K8s). They serve different operational models.",
                    evidence=f"Style: {style}, found K8s references in design",
                ))

        # ── 4. Low Latency + Too Many Synchronous Hops ──
        latency_targets = nf.get("latency_targets", {})
        p99 = self._parse_latency_ms(latency_targets.get("p99") or latency_targets.get("p50", ""))
        if p99 is not None and p99 <= 100:
            # Count service-type components (each is a potential network hop)
            service_count = sum(1 for c in components if c.get("type", "").lower() == "service")
            if service_count >= 6:
                errors.append(self._error(
                    code=ErrorCode.CONTRA_LOW_LATENCY_MANY_HOPS,
                    severity=Severity.HIGH,
                    message=(
                        f"Latency target is {p99}ms (p99) but architecture has {service_count} services. "
                        f"Each synchronous hop adds 5-20ms network latency."
                    ),
                    suggestion=(
                        "Reduce synchronous call chain: use async processing, collapse services, "
                        "or add caching to avoid downstream calls"
                    ),
                    evidence=f"p99 target: {p99}ms, service count: {service_count}, estimated min latency: {service_count * 5}ms",
                ))

        # ── 5. Multi-Region in NFRs but Single Region in Deployment ──
        nf_text = str(nf).lower()
        deploy_regions = deployment.get("regions", [])

        nf_mentions_multi = self._contains_any(nf_text, ["multi-region", "multi_region", "global", "cross-region"])
        deploy_is_single = len(deploy_regions) <= 1

        if nf_mentions_multi and deploy_is_single:
            errors.append(self._error(
                code=ErrorCode.CONTRA_MULTI_REGION_SINGLE_DEPLOY,
                severity=Severity.HIGH,
                message="Non-functional requirements mention multi-region but deployment specifies single region",
                field="deployment.regions",
                suggestion="Add multiple regions to deployment configuration to match NFR claims",
            ))

        # ── 6. Microservices Style but Only 1-2 Components ──
        if "microservice" in style and len(components) <= 2:
            errors.append(self._error(
                code=ErrorCode.CONTRA_STYLE_MISMATCH,
                severity=Severity.MEDIUM,
                message=f"Architecture style is '{style}' but only {len(components)} components defined — this is effectively a monolith",
                suggestion="Either add more granular service boundaries or change architecture_style to 'monolith' or 'modular_monolith'",
            ))

        # ── 7. Monolith Style but 10+ Services ──
        if "monolith" in style and len(components) >= 10:
            errors.append(self._error(
                code=ErrorCode.CONTRA_STYLE_MISMATCH,
                severity=Severity.MEDIUM,
                message=f"Architecture style is '{style}' but {len(components)} components defined — this looks like microservices",
                suggestion="Change architecture_style to 'microservices' or consolidate components",
            ))

        # ── 8. Claims Stateless but Has Local State ──
        local_state_keywords = ["local file", "in-memory state", "session storage", "local disk", "local storage"]
        stateless_keywords = ["stateless", "horizontally scalable", "no shared state"]

        for comp in components:
            comp_text = self._flatten_text(comp)
            if self._contains_any(comp_text, stateless_keywords) and self._contains_any(comp_text, local_state_keywords):
                errors.append(self._error(
                    code=ErrorCode.CONTRA_STATELESS_WITH_LOCAL_STATE,
                    severity=Severity.HIGH,
                    message=f"'{comp.get('name', 'Unknown')}' claims stateless but references local state storage",
                    component=comp.get("name"),
                    suggestion="Move state to external store (Redis, DB) or remove stateless claim",
                ))

        return errors

    def _parse_latency_ms(self, value) -> Optional[int]:
        """Parse latency target: '100ms', '0.1s', '100', etc."""
        if not value:
            return None
        if isinstance(value, (int, float)):
            return int(value)

        text = str(value).lower().strip()

        # Handle seconds
        if "s" in text and "ms" not in text:
            try:
                import re
                num = float(re.search(r"[\d.]+", text).group())
                return int(num * 1000)
            except (AttributeError, ValueError):
                return None

        # Handle milliseconds
        try:
            import re
            num = float(re.search(r"[\d.]+", text).group())
            return int(num)
        except (AttributeError, ValueError):
            return None
