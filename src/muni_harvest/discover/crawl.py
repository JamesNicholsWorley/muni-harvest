"""Polite same-site live crawler that reconstructs the navigation tree.

Politeness (all levers): per-HOST adaptive delay (AIMD — additive-decrease on
success, multiplicative-increase on 429/503/slow), robots Disallow + Crawl-delay
honored, Retry-After respected (in core.fetch), depth + page caps, and full
resumability upstream (the orchestrator skips hosts already done). One worker per
host => many hosts in flight without hammering any single one.

Cross-domain policy: PAGES are only enqueued if same-site; FILES are captured even
off-host when they sit on the storage allowlist (Drive/S3/Dropbox/CDN).
"""

from __future__ import annotations

import time
from collections import deque
from urllib.parse import urldefrag, urljoin, urlsplit

from ..core import fetch
from .htmllinks import extract
from .model import (
    is_file_url, make_node, norm_host, same_site, urlkey,
)
from .storage import resolve_download

_SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "#", "data:")


class AdaptiveDelay:
    """Per-host AIMD pacing. Starts at max(base, robots crawl-delay)."""

    def __init__(self, base: float, ceiling: float = 30.0):
        self.base = base
        self.delay = base
        self.ceiling = ceiling

    def sleep(self) -> None:
        if self.delay > 0:
            time.sleep(self.delay)

    def ok(self, latency: float) -> None:
        # Slow responses (host straining) => back off; fast => ease toward base.
        if latency > 5.0:
            self.delay = min(self.ceiling, self.delay * 1.5)
        else:
            self.delay = max(self.base, self.delay - 0.25)

    def throttled(self) -> None:
        self.delay = min(self.ceiling, max(self.base, self.delay) * 2.0)


def crawl_site(seed_host: str, *, municipality: str = "", robots=None,
               seed_urls: list[str] | None = None, max_depth: int = 4,
               max_pages: int = 400, base_delay: float = 1.0) -> list[dict]:
    """BFS from the homepage + seeds. Returns page + file nodes with nav-tree fields."""
    crawl_delay = getattr(robots, "crawl_delay", None) or 0.0
    pacer = AdaptiveDelay(max(base_delay, float(crawl_delay)))

    home = f"https://{seed_host}/"
    frontier: deque = deque()
    frontier.append((home, 0, "", "", ""))
    for s in (seed_urls or []):
        frontier.append((s, 1, home, "", "sitemap/cms"))

    queued = {urlkey(home)}
    emitted: set[str] = set()
    nodes: list[dict] = []
    pages = 0

    def emit(node: dict) -> None:
        k = node["urlkey"]
        if k not in emitted:
            emitted.add(k)
            nodes.append(node)

    while frontier and pages < max_pages:
        url, depth, parent, anchor, crumb = frontier.popleft()
        if robots is not None and not robots.allowed(url):
            continue
        pacer.sleep()
        t0 = time.monotonic()
        try:
            raw = fetch(url, tries=2, timeout=30)
        except Exception:  # noqa: BLE001 — dead/slow page: back off, skip
            pacer.throttled()
            continue
        pacer.ok(time.monotonic() - t0)
        pages += 1

        html = raw[:2_000_000].decode("utf-8", errors="replace")
        page = extract(html)
        page_crumb = page.breadcrumb or crumb or page.title
        emit(make_node(seed_host=seed_host, municipality=municipality, url=url,
                       kind="page", mimetype="text/html", anchor=anchor,
                       depth=depth, parent_url=parent, breadcrumb=page_crumb,
                       discovered_via="crawl"))

        for href, text in page.links:
            if not href or href.lower().startswith(_SKIP_SCHEMES):
                continue
            absu = urldefrag(urljoin(url, href))[0]
            if not absu.lower().startswith("http"):
                continue
            host = norm_host(urlsplit(absu).netloc)

            if is_file_url(absu):
                dl, shost = resolve_download(absu)
                emit(make_node(seed_host=seed_host, municipality=municipality,
                               url=dl, kind="file", anchor=text, depth=depth + 1,
                               parent_url=url, breadcrumb=page_crumb,
                               discovered_via="crawl", storage_host=shost))
                continue

            # a page: only follow within the town's own domain
            if depth + 1 > max_depth or not same_site(host, seed_host):
                continue
            k = urlkey(absu)
            if k in queued:
                continue
            queued.add(k)
            frontier.append((absu, depth + 1, url, text, page_crumb))

    return nodes
