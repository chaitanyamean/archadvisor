"""Availability Validator — SPOF detection, composite availability math, replication checks.

This is the high-value validator that computes actual composite availability
from the architecture topology and compares it against the declared target.
"""

import re
from typing import Optional

from app.validators.base import BaseValidator
from app.validators.models import ValidationError, Severity, ErrorCode
from app.validators.reference_data import COMPONENT_AVAILABILITY

# Keywords that indicate redundancy
REDUNDANCY_KEYWORDS = [
    "cluster", "replica", "multi-az", "multi_az", "multi-region",
    "failover", "standby", "hot-standby", "sentinel", "replication",
    "redundant", "ha ", "high availability", "active-passive", "active-active",
]

# Keywords for single-instance indicators
SINGLE_INSTANCE_KEYWORDS = [
    "single", "standalone", "one instance", "single node", "1 instance",
    "single-instance", "no replica",
]


class AvailabilityValidator(BaseValidator):
    """Validates availability claims against architecture topology."""

    @property
    def name(self) -> str:
        return "AvailabilityValidator"

    def validate(self, design: dict, requirements: str = "") -> list[ValidationError]:
        errors = []

        nf = self._get_non_functional(design)
        components = self._get_components(design)
        deployment = self._get_deployment(design)
        flat_text = self._flatten_text(design)

        avail_target = self._parse_availability(nf.get("availability_target", ""))

        # ── 1. SPOF Detection ──
        errors.extend(self._detect_spofs(components, flat_text, avail_target))

        # ── 2. Composite Availability Check ──
        if avail_target and avail_target >= 99.0:
            errors.extend(self._check_composite_availability(components, avail_target, flat_text))

        # ── 3. High SLA requires Multi-AZ/Region ──
        if avail_target and avail_target >= 99.99:
            errors.extend(self._check_high_sla_requirements(deployment, flat_text, avail_target))

        # ── 4. Replication Strategy ──
        if avail_target and avail_target >= 99.9:
            errors.extend(self._check_replication(components, flat_text, avail_target))

        return errors

    def _detect_spofs(
        self, components: list[dict], flat_text: str, avail_target: Optional[float]
    ) -> list[ValidationError]:
        """Detect single points of failure in the architecture."""
        errors = []
        severity = Severity.CRITICAL if (avail_target and avail_target >= 99.9) else Severity.HIGH

        for comp in components:
            comp_name = comp.get("name", "Unknown")
            comp_type = comp.get("type", "").lower()
            comp_text = f"{comp_name} {comp_type} {comp.get('scaling_strategy', '')} {' '.join(comp.get('tech_stack', []))}".lower()

            has_redundancy = self._contains_any(comp_text, REDUNDANCY_KEYWORDS)
            is_single = self._contains_any(comp_text, SINGLE_INSTANCE_KEYWORDS)

            # Database SPOF
            if comp_type == "database" and (is_single or not has_redundancy):
                errors.append(self._error(
                    code=ErrorCode.SPOF_DATABASE,
                    severity=severity,
                    message=f"Database '{comp_name}' appears to be a single instance with no replication",
                    component=comp_name,
                    suggestion="Add read replicas, multi-AZ deployment, or clustering",
                    evidence=f"No redundancy keywords found in: {comp_text[:100]}",
                ))

            # Cache SPOF
            elif comp_type == "cache" and (is_single or not has_redundancy):
                errors.append(self._error(
                    code=ErrorCode.SPOF_CACHE,
                    severity=Severity.HIGH,
                    message=f"Cache '{comp_name}' is a single instance — cache failure will cascade to database",
                    component=comp_name,
                    suggestion="Use Redis Sentinel, Redis Cluster, or ElastiCache with replicas",
                ))

            # Gateway SPOF
            elif comp_type == "gateway" and (is_single or not has_redundancy):
                errors.append(self._error(
                    code=ErrorCode.SPOF_GATEWAY,
                    severity=severity,
                    message=f"API Gateway '{comp_name}' appears to be a single instance — all traffic routes through it",
                    component=comp_name,
                    suggestion="Use a managed gateway (AWS ALB, API Gateway) or deploy multiple instances behind a load balancer",
                ))

            # Queue SPOF
            elif comp_type == "queue" and (is_single or not has_redundancy):
                errors.append(self._error(
                    code=ErrorCode.SPOF_QUEUE,
                    severity=Severity.HIGH,
                    message=f"Message queue '{comp_name}' is a single instance — async processing will halt on failure",
                    component=comp_name,
                    suggestion="Use a managed service (SQS, MSK) or deploy a multi-broker cluster",
                ))

        return errors

    def _check_composite_availability(
        self, components: list[dict], avail_target: float, flat_text: str
    ) -> list[ValidationError]:
        """Compute composite availability from component chain and compare to target.

        Composite = product of individual component availabilities (serial chain).
        """
        errors = []

        # Identify components in the critical path (serial dependencies)
        component_avails = []
        for comp in components:
            comp_name = comp.get("name", "").lower()
            comp_type = comp.get("type", "").lower()
            tech_stack = [t.lower() for t in comp.get("tech_stack", [])]
            comp_text = f"{comp_name} {comp_type} {' '.join(tech_stack)}"

            # Try to match to known availability figure
            avail = self._estimate_component_availability(comp_text, comp_type)
            if avail:
                component_avails.append((comp.get("name", "Unknown"), avail))

        if len(component_avails) >= 2:
            # Composite availability = product of all serial components
            composite = 1.0
            for _, avail in component_avails:
                composite *= avail

            composite_percent = composite * 100

            if composite_percent < avail_target:
                bottlenecks = sorted(component_avails, key=lambda x: x[1])[:3]
                bottleneck_str = ", ".join(
                    f"{name} ({avail*100:.3f}%)" for name, avail in bottlenecks
                )
                errors.append(self._error(
                    code=ErrorCode.AVAIL_COMPOSITE_BELOW_TARGET,
                    severity=Severity.CRITICAL,
                    message=(
                        f"Composite availability is {composite_percent:.2f}%, "
                        f"below target of {avail_target}%. "
                        f"Bottlenecks: {bottleneck_str}"
                    ),
                    suggestion=(
                        "Add redundancy to bottleneck components, use managed services "
                        "with higher SLAs, or lower the availability target"
                    ),
                    evidence=f"Computed from {len(component_avails)} serial components",
                ))

        return errors

    def _estimate_component_availability(self, comp_text: str, comp_type: str) -> Optional[float]:
        """Estimate a component's availability from its description."""
        # Check for managed service indicators (higher availability)
        has_redundancy = self._contains_any(comp_text, REDUNDANCY_KEYWORDS)

        # Try to match specific services
        for service_key, avail in COMPONENT_AVAILABILITY.items():
            if service_key.replace("_", " ") in comp_text or service_key in comp_text:
                if has_redundancy:
                    # Redundant: approximate as 1 - (1-a)^2
                    return 1 - (1 - avail) ** 2
                return avail

        # Fallback by type
        type_defaults = {
            "service": 0.9995,
            "database": 0.9990,
            "cache": 0.9990,
            "queue": 0.9990,
            "gateway": 0.9995,
            "cdn": 0.9999,
            "storage": 0.9999,
        }
        base = type_defaults.get(comp_type, 0.9995)
        return 1 - (1 - base) ** 2 if has_redundancy else base

    def _check_high_sla_requirements(
        self, deployment: dict, flat_text: str, avail_target: float
    ) -> list[ValidationError]:
        """99.99%+ SLA requires multi-AZ or multi-region."""
        errors = []

        multi_az_keywords = ["multi-az", "multi_az", "multiple availability zones", "multi-region", "multi_region"]
        has_multi_az = self._contains_any(flat_text, multi_az_keywords)

        if not has_multi_az:
            regions = deployment.get("regions", [])
            if len(regions) <= 1:
                errors.append(self._error(
                    code=ErrorCode.AVAIL_SINGLE_REGION_HIGH_SLA,
                    severity=Severity.CRITICAL,
                    message=f"Availability target {avail_target}% requires multi-AZ or multi-region, but design appears single-region",
                    field="deployment.regions",
                    suggestion="Deploy across at least 2 availability zones, or use multi-region active-passive",
                ))

        return errors

    def _check_replication(
        self, components: list[dict], flat_text: str, avail_target: float
    ) -> list[ValidationError]:
        """High availability requires explicit replication strategy."""
        errors = []

        replication_keywords = [
            "replication", "replica", "standby", "follower", "secondary",
            "read replica", "multi-master", "primary-secondary",
        ]

        # Check databases specifically
        for comp in components:
            if comp.get("type", "").lower() in ("database",):
                comp_text = self._flatten_text(comp)
                if not self._contains_any(comp_text, replication_keywords):
                    errors.append(self._error(
                        code=ErrorCode.AVAIL_NO_REPLICATION,
                        severity=Severity.HIGH,
                        message=f"Database '{comp.get('name', 'Unknown')}' has no replication strategy specified with {avail_target}% SLA target",
                        component=comp.get("name"),
                        suggestion="Specify replication: primary-replica, multi-master, or managed service with automatic replication",
                    ))

        return errors
