"""Operational Complexity Validator — over-engineering detection and service count sanity."""

from typing import Optional

from app.validators.base import BaseValidator
from app.validators.models import ValidationError, Severity, ErrorCode
from app.validators.reference_data import ENTERPRISE_SERVICES


class OperationalComplexityValidator(BaseValidator):
    """Detects over-engineering and unnecessary operational complexity."""

    @property
    def name(self) -> str:
        return "OperationalComplexityValidator"

    def validate(self, design: dict, requirements: str = "") -> list[ValidationError]:
        errors = []

        components = self._get_components(design)
        nf = self._get_non_functional(design)
        flat_text = self._flatten_text(design)
        all_techs = self._all_tech_stack(design)
        req_lower = requirements.lower()

        declared_throughput = self._parse_throughput(nf.get("throughput", ""))
        service_count = sum(1 for c in components if c.get("type", "").lower() == "service")
        total_components = len(components)

        # ── 1. Too Many Services for the Scale ──
        errors.extend(self._check_service_count(service_count, total_components, declared_throughput, req_lower))

        # ── 2. Kafka for Low Throughput ──
        errors.extend(self._check_kafka_overkill(all_techs, flat_text, declared_throughput))

        # ── 3. Multi-Region for MVP/Small Scale ──
        errors.extend(self._check_multi_region_overkill(design, declared_throughput, req_lower))

        # ── 4. Enterprise Services for Startup Scale ──
        errors.extend(self._check_enterprise_overkill(all_techs, declared_throughput, req_lower))

        return errors

    def _check_service_count(
        self, service_count: int, total_components: int, throughput: Optional[int], req_text: str
    ) -> list[ValidationError]:
        """Flag excessive services for the declared scale."""
        errors = []

        # Heuristic: more than 15 components is always suspicious
        if total_components > 15:
            errors.append(self._error(
                code=ErrorCode.OPS_TOO_MANY_SERVICES,
                severity=Severity.HIGH,
                message=f"{total_components} components defined — this is operationally complex and expensive to maintain",
                suggestion="Consolidate related services. Consider bounded contexts — not every entity needs its own service.",
            ))

        # Microservices for small scale
        elif service_count >= 8 and (throughput is None or throughput < 5_000):
            is_mvp = any(kw in req_text for kw in ["mvp", "prototype", "proof of concept", "poc", "small", "startup"])
            if is_mvp or (throughput and throughput < 1_000):
                errors.append(self._error(
                    code=ErrorCode.OPS_TOO_MANY_SERVICES,
                    severity=Severity.MEDIUM,
                    message=(
                        f"{service_count} services for {'<1K RPS' if throughput and throughput < 1000 else 'small scale'} — "
                        f"microservices overhead may outweigh benefits at this scale"
                    ),
                    suggestion="Start with a modular monolith and extract services as scale demands it",
                ))

        return errors

    def _check_kafka_overkill(
        self, all_techs: list[str], flat_text: str, throughput: Optional[int]
    ) -> list[ValidationError]:
        """Kafka is overkill for low throughput systems."""
        errors = []

        has_kafka = any("kafka" in t or "msk" in t for t in all_techs)
        if not has_kafka:
            has_kafka = "kafka" in flat_text or "msk" in flat_text

        if has_kafka and throughput is not None and throughput < 10_000:
            errors.append(self._error(
                code=ErrorCode.OPS_KAFKA_LOW_THROUGHPUT,
                severity=Severity.MEDIUM,
                message=(
                    f"Kafka/MSK included but throughput is only {throughput:,} RPS. "
                    f"Kafka's operational overhead (ZooKeeper/KRaft, brokers, partitions) "
                    f"is not justified below ~10K messages/sec."
                ),
                suggestion=(
                    "Consider simpler alternatives: Redis Streams (< 50K mps), "
                    "RabbitMQ (< 30K mps), or SQS (managed, zero-ops)"
                ),
            ))

        return errors

    def _check_multi_region_overkill(
        self, design: dict, throughput: Optional[int], req_text: str
    ) -> list[ValidationError]:
        """Multi-region for MVP or small scale is over-engineering."""
        errors = []

        deployment = self._get_deployment(design)
        regions = deployment.get("regions", [])
        nf = self._get_non_functional(design)
        avail = self._parse_availability(nf.get("availability_target", ""))

        is_mvp = any(kw in req_text for kw in ["mvp", "prototype", "poc", "proof of concept", "small scale", "startup"])
        is_low_throughput = throughput is not None and throughput < 5_000
        avail_doesnt_require = avail is not None and avail < 99.99

        if len(regions) >= 3 and (is_mvp or is_low_throughput) and avail_doesnt_require:
            errors.append(self._error(
                code=ErrorCode.OPS_MULTI_REGION_MVP,
                severity=Severity.MEDIUM,
                message=f"Multi-region deployment ({len(regions)} regions) for {'MVP/startup' if is_mvp else 'low-throughput'} system",
                suggestion=(
                    "Start with single-region multi-AZ. Add regions when you have "
                    "geographic latency requirements or regulatory needs."
                ),
            ))

        return errors

    def _check_enterprise_overkill(
        self, all_techs: list[str], throughput: Optional[int], req_text: str
    ) -> list[ValidationError]:
        """Heavyweight enterprise services for startup scale."""
        errors = []

        is_small = any(kw in req_text for kw in ["mvp", "startup", "poc", "small", "simple"])
        is_low_throughput = throughput is not None and throughput < 5_000

        if not (is_small or is_low_throughput):
            return errors

        enterprise_used = []
        for tech in all_techs:
            for enterprise in ENTERPRISE_SERVICES:
                if enterprise in tech:
                    enterprise_used.append(enterprise)

        if len(enterprise_used) >= 3:
            errors.append(self._error(
                code=ErrorCode.OPS_ENTERPRISE_FOR_STARTUP,
                severity=Severity.MEDIUM,
                message=(
                    f"Using {len(enterprise_used)} enterprise-grade services "
                    f"({', '.join(enterprise_used[:5])}) for a {'small-scale' if is_small else 'low-throughput'} system"
                ),
                suggestion=(
                    "Consider simpler alternatives: PostgreSQL over Aurora, "
                    "Docker Compose over Kubernetes, SQS over Kafka. "
                    "Right-size your infrastructure to your scale."
                ),
            ))

        return errors
