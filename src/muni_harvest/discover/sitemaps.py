"""Sitemap seeding — a good START, never a coverage claim.

Handles the shapes seen in the wild: sitemap-index recursion, gzipped sitemaps,
XML urlsets, and plain-text (one-URL-per-line) sitemaps. Namespace-agnostic. Caps
recursion + total URLs so a pathological sitemap can't blow up the frontier.
"""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET

from ..core import fetch

_TAG = re.compile(r"\}")  # strip XML namespace: {ns}loc -> loc


def _localname(tag: str) -> str:
    return _TAG.split(tag)[-1]


def _get_bytes(url: str) -> bytes:
    raw = fetch(url, tries=2, timeout=30)
    if url.endswith(".gz") or raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    return raw


def fetch_sitemap(url: str, *, max_index: int = 50, max_urls: int = 50000,
                  _seen: set | None = None) -> list[str]:
    """Return all content URLs reachable from a sitemap (recursing indexes)."""
    seen = _seen if _seen is not None else set()
    if url in seen or len(seen) > max_index:
        return []
    seen.add(url)
    try:
        raw = _get_bytes(url)
    except Exception:  # noqa: BLE001
        return []

    text = raw.decode("utf-8", errors="replace").strip()
    urls: list[str] = []

    # Plain-text sitemap: lines of URLs, no XML.
    if not text.lstrip().startswith("<"):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("http"):
                urls.append(line)
        return urls[:max_urls]

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return urls

    tag = _localname(root.tag).lower()
    locs = [e.text.strip() for e in root.iter()
            if _localname(e.tag).lower() == "loc" and e.text]

    if tag == "sitemapindex":
        for child_sm in locs:
            if len(seen) > max_index:
                break
            urls.extend(fetch_sitemap(child_sm, max_index=max_index,
                                      max_urls=max_urls, _seen=seen))
    else:  # urlset (or unknown but has <loc>s)
        urls.extend(locs)
    return urls[:max_urls]


def sitemap_urls(host: str, declared: list[str] | None = None,
                 max_urls: int = 50000) -> list[str]:
    """Union of URLs from robots-declared sitemaps + the conventional /sitemap.xml."""
    candidates = list(declared or [])
    candidates.append(f"https://{host}/sitemap.xml")
    out: list[str] = []
    seen: set = set()
    for sm in dict.fromkeys(candidates):  # dedup, keep order
        out.extend(fetch_sitemap(sm, _seen=seen, max_urls=max_urls))
        if len(out) >= max_urls:
            break
    # dedup content URLs, preserve order
    return list(dict.fromkeys(out))[:max_urls]
