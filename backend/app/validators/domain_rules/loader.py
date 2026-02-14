"""Domain pattern loader — detects domain from requirements and loads matching rules.

Deterministic, fast (< 1ms), no LLM calls. Uses keyword frequency scoring
to match user requirements against domain pattern files.
"""

import json
import re
from pathlib import Path
from typing import Optional

RULES_DIR = Path(__file__).parent

# Cache loaded domain files to avoid re-reading from disk
_domain_cache: dict[str, dict] = {}


def _load_all_domains() -> dict[str, dict]:
    """Load and cache all JSON domain files from the rules directory."""
    if _domain_cache:
        return _domain_cache

    for json_file in RULES_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            domain_name = data.get("domain", json_file.stem)
            _domain_cache[domain_name] = data
        except (json.JSONDecodeError, KeyError):
            continue

    return _domain_cache


def detect_domain(requirements: str) -> Optional[dict]:
    """Scan requirements text against all domain keyword lists.

    Uses keyword frequency scoring — domain with most keyword hits wins.
    Minimum 2 keyword matches required to avoid false positives.

    Args:
        requirements: User's original requirements text

    Returns:
        Best-matching domain pattern dict, or None if no match (< 2 hits)
    """
    if not requirements:
        return None

    domains = _load_all_domains()
    req_lower = requirements.lower()

    best_domain = None
    best_score = 0

    for domain_data in domains.values():
        keywords = domain_data.get("keywords", [])
        score = sum(1 for kw in keywords if kw.lower() in req_lower)

        if score > best_score:
            best_score = score
            best_domain = domain_data

    # Require at least 2 keyword matches to avoid false positives
    if best_score >= 2:
        return best_domain

    return None


def load_domain_rules(domain_name: str) -> Optional[dict]:
    """Load a specific domain's pattern file by name.

    Args:
        domain_name: Domain identifier (e.g., "url_shortener", "payments")

    Returns:
        Domain pattern dict, or None if not found
    """
    domains = _load_all_domains()
    return domains.get(domain_name)


def get_all_domains() -> list[str]:
    """List all available domain pattern names."""
    domains = _load_all_domains()
    return list(domains.keys())
