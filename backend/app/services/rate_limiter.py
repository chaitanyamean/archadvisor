"""Rate limiter — sliding window counter for per-IP session limits."""

import time
from collections import defaultdict
from typing import Optional

from app.config import get_settings


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter.

    Tracks timestamps of requests per key (IP address).
    Allows up to `max_requests` within a rolling `window_seconds` window.
    """

    def __init__(
        self,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ):
        settings = get_settings()
        self.max_requests = max_requests or settings.RATE_LIMIT_MAX_SESSIONS
        self.window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str) -> None:
        """Remove timestamps outside the current window."""
        cutoff = time.time() - self.window_seconds
        self._timestamps[key] = [
            ts for ts in self._timestamps[key] if ts > cutoff
        ]

    def allow_request(self, key: str) -> bool:
        """Check if a request is allowed and record it.

        Returns True if under the limit, False if rate limited.
        """
        self._prune(key)

        if len(self._timestamps[key]) < self.max_requests:
            self._timestamps[key].append(time.time())
            return True

        return False

    def remaining(self, key: str) -> int:
        """Get remaining requests allowed in the current window."""
        self._prune(key)
        return max(0, self.max_requests - len(self._timestamps[key]))

    def reset_time(self, key: str) -> float:
        """Seconds until the oldest request in the window expires."""
        self._prune(key)
        if not self._timestamps[key]:
            return 0
        oldest = self._timestamps[key][0]
        return max(0, (oldest + self.window_seconds) - time.time())


# Module-level singleton
rate_limiter = SlidingWindowRateLimiter()
