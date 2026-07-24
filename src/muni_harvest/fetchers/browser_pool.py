"""Persistent BrowserPool — the fix for the fatal boot-a-browser-per-site pattern.

Boots N warm stealth drivers ONCE and leases them from a queue; a caller borrows a
driver, uses it, and returns it. The browser tier is machine-bound (2-6 drivers),
sized independently of the politeness-bound cheap tier. Requires the `live` extra.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from queue import Queue

from .waf_session import build_driver


class BrowserPool:
    def __init__(self, size: int = 3, stealth: bool = True, headful: bool = False):
        self.size = size
        self._q: Queue = Queue()
        self._drivers: list = []
        self._lock = threading.Lock()
        for _ in range(size):
            d = build_driver(headful=headful, stealth=stealth)
            self._drivers.append(d)
            self._q.put(d)

    @contextmanager
    def lease(self, timeout: float = 180):
        """Borrow a warm driver; guaranteed returned to the pool on exit."""
        driver = self._q.get(timeout=timeout)
        try:
            yield driver
        finally:
            self._q.put(driver)

    def close(self) -> None:
        with self._lock:
            for d in self._drivers:
                try:
                    d.quit()
                except Exception:  # noqa: BLE001
                    pass
            self._drivers.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
