"""robots.txt policy — Disallow rules, Crawl-delay, and declared Sitemaps.

Wraps stdlib urllib.robotparser but fetches via our polite fetch() (correct UA,
gzip, backoff) rather than robotparser's own bare urlopen.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from ..core import DEFAULT_UA, fetch


def _pattern_to_re(pat: str) -> re.Pattern | None:
    """Compile a robots path pattern ('/*.pdf$') to a regex anchored at the path start."""
    if not pat.startswith("/"):
        return None
    end = pat.endswith("$")
    body = pat[:-1] if end else pat
    rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    try:
        return re.compile("^" + rx + ("$" if end else ""))
    except re.error:
        return None


def _wildcard_allows(body: str) -> list[re.Pattern]:
    """Allow patterns for `User-agent: *` that contain a wildcard or an end-anchor.

    stdlib RobotFileParser matches Allow/Disallow by literal path prefix, so it cannot
    express `Allow: /*.pdf$` and simply denies -- leaving us MORE restrictive than the
    site asked. cms3.revize.com (Boylston, Marshfield) says `Disallow: /` but explicitly
    allows /*.pdf$, .DOC, .DOCX, .PPT, .PPTX; under the Robots Exclusion Protocol the
    longest matching rule wins, so those documents are permitted. Only ever used to GRANT
    access a site explicitly gave -- never to deny more.
    """
    out: list[re.Pattern] = []
    in_star = False
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            in_star = value == "*"
        elif field == "allow" and in_star and ("*" in value or value.endswith("$")):
            rx = _pattern_to_re(value)
            if rx is not None:
                out.append(rx)
    return out


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
        self._allow_rx: list[re.Pattern] = []
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
        self._allow_rx = _wildcard_allows(body)
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
            if self._rp.can_fetch(DEFAULT_UA, url):
                return True
        except Exception:  # noqa: BLE001
            return True
        # Denied by prefix matching -- but check the wildcard Allow rules stdlib cannot
        # express. This only ever grants what robots.txt explicitly permits.
        p = urlsplit(url)
        path = p.path + (("?" + p.query) if p.query else "")
        return any(rx.match(path) for rx in self._allow_rx)
