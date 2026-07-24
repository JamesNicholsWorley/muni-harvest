"""Persistent, self-healing BrowserPool — the fix for boot-a-browser-per-site.

Boots N warm stealth drivers ONCE and leases them from a queue. Crucially it
*recycles* drivers: a driver that errored (or has been used many times, so it may
have leaked memory/state) is quit and replaced with a fresh one, so a single crash
can't cascade into every subsequent host failing. Requires the `live` extra.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from queue import Queue

from .waf_session import build_driver


class BrowserPool:
    def __init__(self, size: int = 3, stealth: bool = True, headful: bool = False,
                 recycle_after: int = 15):
        self.size = size
        self.stealth = stealth
        self.headful = headful
        self.recycle_after = recycle_after
        self._q: Queue = Queue()
        self._uses: dict[int, int] = {}
        self._lock = threading.Lock()
        for _ in range(size):
            self._spawn()

    def _spawn(self):
        d = build_driver(headful=self.headful, stealth=self.stealth)
        self._uses[id(d)] = 0
        self._q.put(d)
        return d

    def _kill(self, driver) -> None:
        self._uses.pop(id(driver), None)
        try:
            driver.quit()
        except Exception:  # noqa: BLE001
            pass

    def acquire(self, timeout: float = 180):
        return self._q.get(timeout=timeout)

    def release(self, driver, broken: bool = False) -> None:
        """Return a driver to the pool, or recycle it if broken / over-used."""
        with self._lock:
            used = self._uses.get(id(driver), 0) + 1
            if broken or used >= self.recycle_after:
                self._kill(driver)
                self._spawn()          # keep the pool at full strength
            else:
                self._uses[id(driver)] = used
                self._q.put(driver)

    @contextmanager
    def lease(self, timeout: float = 180):
        driver = self.acquire(timeout)
        broken = False
        try:
            yield driver
        except Exception:
            broken = True
            raise
        finally:
            self.release(driver, broken=broken)

    def close(self) -> None:
        with self._lock:
            while not self._q.empty():
                try:
                    self._kill(self._q.get_nowait())
                except Exception:  # noqa: BLE001
                    break

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
