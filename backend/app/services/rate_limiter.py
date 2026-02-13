"""Rate limiter — token bucket implementation for API requests."""

import time
from collections import defaultdict
from typing import Optional

from app.config import get_settings


class TokenBucketRateLimiter:
    """In-memory token bucket rate limiter.

    For production with multiple instances, swap to Redis-backed implementation.
    """

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        refill_seconds: Optional[int] = None,
    ):
        settings = get_settings()
        self.max_tokens = max_tokens or settings.RATE_LIMIT_MAX_SESSIONS
        self.refill_seconds = refill_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
        self._buckets: dict = defaultdict(
            lambda: {"tokens": self.max_tokens, "last_refill": time.time()}
        )

    def allow_request(self, key: str = "global") -> bool:
        """Check if a request is allowed and consume a token.

        Args:
            key: Rate limit key (e.g., IP address, API key, or "global")

        Returns:
            True if request is allowed, False if rate limited
        """
        bucket = self._buckets[key]
        now = time.time()

        # Calculate token refill
        elapsed = now - bucket["last_refill"]
        tokens_to_add = int(elapsed / self.refill_seconds * self.max_tokens)

        if tokens_to_add > 0:
            bucket["tokens"] = min(self.max_tokens, bucket["tokens"] + tokens_to_add)
            bucket["last_refill"] = now

        # Check and consume
        if bucket["tokens"] > 0:
            bucket["tokens"] -= 1
            return True

        return False

    def remaining_tokens(self, key: str = "global") -> int:
        """Get remaining tokens for a key without consuming."""
        bucket = self._buckets.get(key)
        if bucket is None:
            return self.max_tokens
        return bucket["tokens"]

    def reset_time(self, key: str = "global") -> float:
        """Get seconds until next token refill."""
        bucket = self._buckets.get(key)
        if bucket is None:
            return 0
        elapsed = time.time() - bucket["last_refill"]
        return max(0, self.refill_seconds / self.max_tokens - elapsed)


# Module-level singleton
rate_limiter = TokenBucketRateLimiter()
