"""CMS fingerprinting + listing-endpoint seeds.

Municipal sites cluster on a few platforms whose document indexes are far richer
than the homepage nav. We fingerprint the platform from the homepage HTML/headers,
then hand the crawler high-value seed paths (CivicPlus AgendaCenter/DocumentCenter,
Granicus, etc.) so the polite crawl starts where the documents actually live.
"""

from __future__ import annotations

import re

from ..core import fetch

# platform -> (signature regex over html+headers, seed paths to enqueue)
_CMS = {
    "civicplus": (re.compile(r"civicplus|/AgendaCenter|/DocumentCenter|CivicPlus", re.I),
                  ["/AgendaCenter", "/DocumentCenter", "/Archive.aspx"]),
    "granicus":  (re.compile(r"granicus|legistar", re.I),
                  ["/ViewPublisher.php"]),
    "revize":    (re.compile(r"revize", re.I), ["/document-center", "/documents"]),
    "opengov":   (re.compile(r"opengov|viewpoint\.cloud", re.I), []),
    "civicengage": (re.compile(r"civicengage", re.I),
                    ["/DocumentCenter", "/AgendaCenter"]),
    "wordpress": (re.compile(r"wp-content|wp-json", re.I), ["/wp-sitemap.xml"]),
    "squarespace": (re.compile(r"squarespace", re.I), []),
}


def fingerprint(host: str) -> tuple[str, list[str]]:
    """Return (cms_name, seed_urls). ('', []) if homepage can't be fetched."""
    try:
        raw = fetch(f"https://{host}/", tries=2, timeout=25)
    except Exception:  # noqa: BLE001
        return ("", [])
    html = raw[:400_000].decode("utf-8", errors="replace")
    for name, (rx, paths) in _CMS.items():
        if rx.search(html):
            seeds = [f"https://{host}{p}" for p in paths]
            return (name, seeds)
    return ("unknown", [])
