"""Domain pattern rules — JSON-based domain-specific validation patterns."""

from app.validators.domain_rules.loader import detect_domain, load_domain_rules, get_all_domains

__all__ = ["detect_domain", "load_domain_rules", "get_all_domains"]
