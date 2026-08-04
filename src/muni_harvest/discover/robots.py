"""robots.txt policy — Disallow rules, Crawl-delay, and declared Sitemaps.

Wraps stdlib urllib.robotparser but fetches via our polite fetch() (correct UA,
gzip, backoff) rather than robotparser's own bare urlopen.
"""

from __future__ import annotations

from urllib.robotparser import RobotFileParser

from ..core import DEFAULT_UA, fetch


class RobotsPolicy:
    """robots.txt for one host.

    `override=True` ignores Disallow rules for a specific, named host. Used ONLY for
    municipalities whose CMS ships a blanket `User-agent: * / Disallow: /` template that
    also bans everyone but Googlebot -- over public records the town is legally required
    to publish. It is an owner decision per host, never a default, and callers pair it
    with a much slower crawl delay and a lower page cap: if we are going to read a site
    that asked us not to, we take less from it and take it slowly.
    """

    def __init__(self, host: str, override: bool = False):
        self.host = host
        self.override = override
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
        if self.override:
            return True
        if not self._loaded:
            return True
        try:
            return self._rp.can_fetch(DEFAULT_UA, url)
        except Exception:  # noqa: BLE001
            return True
