"""robots.txt policy — Disallow rules, Crawl-delay, and declared Sitemaps.

Wraps stdlib urllib.robotparser but fetches via our polite fetch() (correct UA,
gzip, backoff) rather than robotparser's own bare urlopen.
"""

from __future__ import annotations

from urllib.robotparser import RobotFileParser

from ..core import DEFAULT_UA, fetch


class RobotsPolicy:
    def __init__(self, host: str):
        self.host = host
        self._rp = RobotFileParser()
        self.sitemaps: list[str] = []
        self.crawl_delay: float | None = None
        self._loaded = False

    def load(self) -> "RobotsPolicy":
        url = f"https://{self.host}/robots.txt"
        try:
            body = fetch(url, tries=2, timeout=20).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — no robots.txt = allow all (be polite anyway)
            self._rp.parse([])
            self._loaded = True
            return self
        self._rp.parse(body.splitlines())
        self.sitemaps = list(self._rp.site_maps() or [])
        try:
            self.crawl_delay = self._rp.crawl_delay(DEFAULT_UA)
        except Exception:  # noqa: BLE001
            self.crawl_delay = None
        self._loaded = True
        return self

    def allowed(self, url: str) -> bool:
        if not self._loaded:
            return True
        try:
            return self._rp.can_fetch(DEFAULT_UA, url)
        except Exception:  # noqa: BLE001
            return True
