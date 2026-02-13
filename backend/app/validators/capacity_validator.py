"""Capacity Validator — throughput feasibility, scaling strategy, hotspot detection."""

from app.validators.base import BaseValidator
from app.validators.models import ValidationError, Severity, ErrorCode
from app.validators.reference_data import THROUGHPUT_BENCHMARKS


class CapacityValidator(BaseValidator):
    """Validates capacity claims against known throughput benchmarks."""

    @property
    def name(self) -> str:
        return "CapacityValidator"

    def validate(self, design: dict, requirements: str = "") -> list[ValidationError]:
        errors = []

        nf = self._get_non_functional(design)
        components = self._get_components(design)
        flat_text = self._flatten_text(design)

        # Parse declared throughput
        declared_throughput = self._parse_throughput(nf.get("throughput", ""))

        # ── 1. Throughput vs Benchmark ──
        if declared_throughput:
            errors.extend(self._check_throughput_feasibility(components, declared_throughput))

        # ── 2. High Throughput without Auto-Scaling ──
        if declared_throughput and declared_throughput >= 10_000:
            errors.extend(self._check_autoscaling(components, flat_text, declared_throughput))

        # ── 3. Single Node High RPS ──
        if declared_throughput and declared_throughput >= 10_000:
            errors.extend(self._check_single_node(components, declared_throughput))

        # ── 4. Hotspot / Sharding Risk ──
        if declared_throughput and declared_throughput >= 5_000:
            errors.extend(self._check_sharding(components, flat_text, declared_throughput))

        # ── 5. Missing Scaling Strategy ──
        errors.extend(self._check_scaling_strategy(components))

        return errors

    def _check_throughput_feasibility(
        self, components: list[dict], declared_throughput: int
    ) -> list[ValidationError]:
        """Compare declared throughput against known benchmarks per technology."""
        errors = []

        for comp in components:
            comp_name = comp.get("name", "Unknown")
            tech_stack = [t.lower().replace(" ", "_") for t in comp.get("tech_stack", [])]
            scaling = comp.get("scaling_strategy", "").lower()

            for tech in tech_stack:
                # Find matching benchmark
                for bench_key, bench_data in THROUGHPUT_BENCHMARKS.items():
                    if bench_key in tech or tech in bench_key:
                        max_rps = bench_data.get("rps", bench_data.get("mps", 0))

                        # If scaling mentions replicas/horizontal, use higher limit
                        if self._contains_any(scaling, ["horizontal", "replica", "shard", "partition", "cluster"]):
                            max_rps = bench_data.get("with_replicas", max_rps * 3)

                        if declared_throughput > max_rps:
                            errors.append(self._error(
                                code=ErrorCode.CAP_THROUGHPUT_EXCEEDS_BENCHMARK,
                                severity=Severity.HIGH,
                                message=(
                                    f"Declared throughput ({declared_throughput:,} RPS) exceeds "
                                    f"'{bench_key}' benchmark ({max_rps:,} RPS) in '{comp_name}'"
                                ),
                                component=comp_name,
                                suggestion=(
                                    f"Add horizontal scaling, read replicas, or caching. "
                                    f"'{bench_key}' single node handles ~{bench_data.get('rps', bench_data.get('mps', 0)):,} RPS."
                                ),
                                evidence=f"tech: {tech}, benchmark: {bench_key}, declared: {declared_throughput:,}, max: {max_rps:,}",
                            ))
                        break  # Only match first benchmark per tech

        return errors

    def _check_autoscaling(
        self, components: list[dict], flat_text: str, declared_throughput: int
    ) -> list[ValidationError]:
        """High throughput requires auto-scaling mention."""
        errors = []

        autoscale_keywords = [
            "auto-scaling", "autoscaling", "auto_scaling", "horizontal scaling",
            "hpa", "keda", "target tracking", "scale out", "elastic",
        ]

        if not self._contains_any(flat_text, autoscale_keywords):
            errors.append(self._error(
                code=ErrorCode.CAP_NO_AUTOSCALING,
                severity=Severity.HIGH,
                message=f"Declared throughput is {declared_throughput:,} RPS but no auto-scaling strategy mentioned",
                suggestion="Add auto-scaling: HPA for K8s, target tracking for ECS, or managed auto-scaling",
                evidence=f"Searched for: {', '.join(autoscale_keywords[:5])}",
            ))

        return errors

    def _check_single_node(
        self, components: list[dict], declared_throughput: int
    ) -> list[ValidationError]:
        """Flag services that appear to be single-node handling high traffic."""
        errors = []

        single_indicators = [
            "single", "1 instance", "one instance", "standalone", "single node",
        ]

        for comp in components:
            comp_name = comp.get("name", "Unknown")
            comp_type = comp.get("type", "").lower()
            scaling = comp.get("scaling_strategy", "").lower()
            comp_text = f"{comp_name} {comp_type} {scaling}".lower()

            if comp_type in ("service", "gateway") and self._contains_any(comp_text, single_indicators):
                errors.append(self._error(
                    code=ErrorCode.CAP_SINGLE_NODE_HIGH_RPS,
                    severity=Severity.CRITICAL,
                    message=f"'{comp_name}' appears to be single-node but must handle {declared_throughput:,} RPS",
                    component=comp_name,
                    suggestion="Deploy multiple instances behind a load balancer with auto-scaling",
                ))

        return errors

    def _check_sharding(
        self, components: list[dict], flat_text: str, declared_throughput: int
    ) -> list[ValidationError]:
        """Detect missing sharding/partitioning for high-throughput databases."""
        errors = []

        shard_keywords = [
            "shard", "partition", "hash ring", "consistent hash",
            "range partition", "key-based partition",
        ]

        for comp in components:
            comp_type = comp.get("type", "").lower()
            if comp_type != "database":
                continue

            comp_name = comp.get("name", "Unknown")
            comp_text = self._flatten_text(comp)

            if not self._contains_any(comp_text, shard_keywords):
                # Check write throughput specifically
                threshold = 20_000  # Sharding becomes important above this
                if declared_throughput >= threshold:
                    errors.append(self._error(
                        code=ErrorCode.CAP_NO_SHARDING,
                        severity=Severity.HIGH,
                        message=(
                            f"Database '{comp_name}' has no sharding strategy with "
                            f"{declared_throughput:,} RPS declared throughput"
                        ),
                        component=comp_name,
                        suggestion="Add partitioning strategy: hash-based sharding, range partitioning, or use a natively distributed database",
                    ))

                # Hotspot risk
                if declared_throughput >= 5_000:
                    write_keywords = ["write-heavy", "write heavy", "all writes", "primary writer"]
                    if self._contains_any(comp_text, write_keywords):
                        errors.append(self._error(
                            code=ErrorCode.CAP_HOTSPOT_RISK,
                            severity=Severity.MEDIUM,
                            message=f"Write-heavy database '{comp_name}' may have hotspot risk without partitioning",
                            component=comp_name,
                            suggestion="Implement write distribution via consistent hashing or application-level sharding",
                        ))

        return errors

    def _check_scaling_strategy(self, components: list[dict]) -> list[ValidationError]:
        """Every service component should have a scaling strategy."""
        errors = []

        for comp in components:
            comp_type = comp.get("type", "").lower()
            if comp_type not in ("service", "gateway"):
                continue

            scaling = comp.get("scaling_strategy", "").strip()
            if not scaling:
                errors.append(self._error(
                    code=ErrorCode.CAP_NO_SCALING_STRATEGY,
                    severity=Severity.MEDIUM,
                    message=f"Service '{comp.get('name', 'Unknown')}' has no scaling_strategy defined",
                    component=comp.get("name"),
                    suggestion="Specify: horizontal, vertical, or auto-scaling strategy",
                ))

        return errors
