"""Reference data — throughput benchmarks, availability estimates, known patterns.

This is the encoded engineering knowledge that makes validation deterministic.
All numbers are conservative real-world estimates, not theoretical maximums.
"""

# ──────────────────────────────────────────────────────────────────────
# THROUGHPUT BENCHMARKS (requests/sec or messages/sec per single node)
# ──────────────────────────────────────────────────────────────────────

THROUGHPUT_BENCHMARKS: dict[str, dict] = {
    # Databases
    "postgresql": {"rps": 10_000, "write_rps": 5_000, "with_replicas": 50_000},
    "postgres": {"rps": 10_000, "write_rps": 5_000, "with_replicas": 50_000},
    "mysql": {"rps": 10_000, "write_rps": 5_000, "with_replicas": 40_000},
    "mongodb": {"rps": 25_000, "write_rps": 15_000, "with_replicas": 100_000},
    "cassandra": {"rps": 50_000, "write_rps": 50_000, "with_replicas": 200_000},
    "dynamodb": {"rps": 40_000, "write_rps": 40_000, "with_replicas": 1_000_000},
    "cockroachdb": {"rps": 8_000, "write_rps": 3_000, "with_replicas": 30_000},
    "tidb": {"rps": 15_000, "write_rps": 8_000, "with_replicas": 60_000},

    # Caches
    "redis": {"rps": 100_000, "write_rps": 80_000},
    "memcached": {"rps": 200_000, "write_rps": 200_000},
    "elasticache": {"rps": 100_000, "write_rps": 80_000},

    # Message Brokers
    "kafka": {"mps": 200_000, "per_partition": 10_000},
    "rabbitmq": {"mps": 30_000},
    "sqs": {"mps": 3_000, "fifo_mps": 300},
    "nats": {"mps": 500_000},
    "pulsar": {"mps": 100_000},
    "redis_streams": {"mps": 100_000},

    # Web Servers / API Frameworks
    "nginx": {"rps": 50_000},
    "envoy": {"rps": 40_000},
    "haproxy": {"rps": 60_000},
    "fastapi": {"rps": 8_000},
    "express": {"rps": 5_000},
    "spring_boot": {"rps": 3_000},
    "spring": {"rps": 3_000},
    "django": {"rps": 2_000},
    "flask": {"rps": 1_500},
    "go_net_http": {"rps": 30_000},
    "actix": {"rps": 40_000},
    "fiber": {"rps": 25_000},
}


# ──────────────────────────────────────────────────────────────────────
# COMPONENT AVAILABILITY ESTIMATES (single instance, no redundancy)
# ──────────────────────────────────────────────────────────────────────

COMPONENT_AVAILABILITY: dict[str, float] = {
    # Load Balancers (managed)
    "alb": 0.9999,
    "nlb": 0.9999,
    "elb": 0.9999,
    "cloud_load_balancer": 0.9999,
    "load_balancer": 0.9995,

    # Compute
    "ec2": 0.9995,
    "ecs": 0.9999,
    "eks": 0.9995,
    "lambda": 0.9999,
    "cloud_run": 0.9999,
    "cloud_functions": 0.9999,
    "fargate": 0.9999,
    "kubernetes": 0.9995,
    "vm": 0.9990,

    # Databases
    "rds": 0.9995,
    "rds_multi_az": 0.9999,
    "aurora": 0.9999,
    "dynamodb": 0.9999,
    "cloud_sql": 0.9995,
    "cosmosdb": 0.9999,
    "postgresql": 0.9990,
    "mysql": 0.9990,
    "mongodb": 0.9990,
    "cassandra": 0.9995,

    # Caches
    "elasticache": 0.9999,
    "redis": 0.9990,
    "redis_cluster": 0.9999,
    "memcached": 0.9990,

    # Message Brokers
    "msk": 0.9999,
    "kafka": 0.9990,
    "sqs": 0.9999,
    "sns": 0.9999,
    "rabbitmq": 0.9990,
    "eventbridge": 0.9999,

    # Storage
    "s3": 0.99999,
    "gcs": 0.99999,
    "ebs": 0.9999,

    # API Gateway
    "api_gateway": 0.9999,
    "apigee": 0.9999,
    "kong": 0.9995,

    # CDN
    "cloudfront": 0.9999,
    "cloudflare": 0.9999,

    # Default
    "service": 0.9995,
    "microservice": 0.9995,
}


# ──────────────────────────────────────────────────────────────────────
# EVENTUALLY CONSISTENT DATABASES
# ──────────────────────────────────────────────────────────────────────

EVENTUALLY_CONSISTENT_DBS = {
    "cassandra", "dynamodb", "cosmosdb", "couchdb", "couchbase",
    "riak", "voldemort", "scylladb",
}


# ──────────────────────────────────────────────────────────────────────
# MESSAGE BROKERS (for contradiction detection)
# ──────────────────────────────────────────────────────────────────────

MESSAGE_BROKERS = {
    "kafka", "rabbitmq", "sqs", "sns", "nats", "pulsar",
    "eventbridge", "redis_streams", "kinesis", "pubsub",
    "cloud_pubsub", "msk", "amazon_mq", "activemq", "zeromq",
}


# ──────────────────────────────────────────────────────────────────────
# ENTERPRISE / HEAVYWEIGHT SERVICES (for over-engineering detection)
# ──────────────────────────────────────────────────────────────────────

ENTERPRISE_SERVICES = {
    "kafka", "msk", "kubernetes", "eks", "gke", "aks",
    "aurora", "spanner", "cosmosdb", "redshift", "bigquery",
    "databricks", "snowflake", "elasticsearch", "opensearch",
    "istio", "consul", "vault", "terraform",
}


# ──────────────────────────────────────────────────────────────────────
# KNOWN GOOD PATTERNS — expected components for given requirement types
# ──────────────────────────────────────────────────────────────────────

EXPECTED_PATTERNS: dict[str, dict] = {
    "high_throughput": {
        "threshold_rps": 10_000,
        "requires": ["load_balancer", "horizontal_scaling", "caching"],
        "recommends": ["circuit_breaker", "rate_limiting", "auto_scaling"],
    },
    "high_availability": {
        "threshold_percent": 99.99,
        "requires": ["multi_az", "health_check", "auto_failover", "replication"],
        "recommends": ["chaos_testing", "runbook", "automated_recovery"],
    },
    "financial_data": {
        "keywords": ["payment", "transaction", "financial", "banking", "billing", "invoice"],
        "requires": ["encryption_at_rest", "audit_logging", "idempotency"],
        "recommends": ["pci", "compliance", "reconciliation"],
    },
    "user_facing": {
        "keywords": ["user", "customer", "client", "consumer", "subscriber"],
        "requires": ["authentication", "rate_limiting"],
        "recommends": ["cdn", "caching", "monitoring"],
    },
    "real_time": {
        "keywords": ["real-time", "realtime", "real time", "live", "streaming", "websocket"],
        "requires": ["message_broker", "event_driven"],
        "recommends": ["backpressure", "circuit_breaker"],
    },
}


# ──────────────────────────────────────────────────────────────────────
# REQUIREMENT KEYWORD → EXPECTED COMPONENT MAPPING
# ──────────────────────────────────────────────────────────────────────

REQUIREMENT_COMPONENT_MAP: dict[str, dict] = {
    "auth": {
        "keywords": ["auth", "authentication", "login", "oauth", "sso", "jwt", "identity"],
        "expect_in": "components",
        "error_code": "MISSING_AUTH",
    },
    "analytics": {
        "keywords": ["analytics", "tracking", "metrics", "dashboard", "reporting", "insights"],
        "expect_in": "components",
        "error_code": "MISSING_ANALYTICS",
    },
    "disaster_recovery": {
        "keywords": ["disaster recovery", "DR", "RPO", "RTO", "backup", "failover"],
        "expect_in": "non_functional",
        "error_code": "MISSING_DR",
    },
    "monitoring": {
        "keywords": ["monitoring", "observability", "alerting", "health check"],
        "expect_in": "components",
        "error_code": "MISSING_MONITORING",
    },
    "encryption": {
        "keywords": ["encryption", "encrypted", "TLS", "SSL", "encrypt at rest", "PCI"],
        "expect_in": "components",
        "error_code": "MISSING_ENCRYPTION",
    },
    "rate_limiting": {
        "keywords": ["rate limit", "throttle", "rate-limit", "throttling", "quota"],
        "expect_in": "components",
        "error_code": "MISSING_RATE_LIMITING",
    },
    "search": {
        "keywords": ["search", "full-text search", "elasticsearch", "opensearch"],
        "expect_in": "components",
        "error_code": "MISSING_SEARCH",
    },
    "notification": {
        "keywords": ["notification", "push notification", "alert", "email notification", "SMS"],
        "expect_in": "components",
        "error_code": "MISSING_NOTIFICATION",
    },
    "caching": {
        "keywords": ["cache", "caching", "low latency", "sub-100ms", "sub-50ms"],
        "expect_in": "components",
        "error_code": "MISSING_CACHING",
    },
}
