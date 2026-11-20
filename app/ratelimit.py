"""Per-IP rate limit for the public demo endpoint.

A sliding window kept in memory: enough for one app instance. With several instances the counters would move to
Redis (the same idea, shared). Kept small and dependency-free so the tests can drive the clock.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    def __init__(self, limit: int, window_s: float = 60.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window_s = window_s
        self.clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        """Records a hit for `key`. Returns 0 when allowed, else the seconds to wait (for the Retry-After header)."""
        now = self.clock()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, int(hits[0] + self.window_s - now) + 1)
            hits.append(now)
            # Drop empty keys now and then, so a crowd of one-time visitors does not grow memory forever.
            if len(self._hits) > 10_000:
                for stale in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window_s]:
                    del self._hits[stale]
            return 0
