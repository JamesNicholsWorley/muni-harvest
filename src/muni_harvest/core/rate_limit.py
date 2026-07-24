"""Min-interval rate limiter (vendored from AbundanceHistory/harvesters/common.py).

Thread-safe: a shared instance can throttle a whole ThreadPoolExecutor.
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Simple min-interval limiter. `per_minute<=0` disables throttling."""

    def __init__(self, per_minute: float):
        self.interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self.interval <= 0:
            return
        # Serialize so concurrent workers honour a single global spacing.
        with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self._last = time.monotonic()
