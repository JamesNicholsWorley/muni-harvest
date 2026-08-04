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
    # Granicus/Vision GovAccess: the `sites/g/files/vyhlif...` asset path is its
    # fingerprint. Its election records hang off the clerk section under /pages/, and the
    # documents themselves are the /<section>/files/<slug> aliases model.py now reads.
    "govaccess": (re.compile(r"sites/g/files/vyhlif|Vision Internet|GovAccess", re.I),
                  ["/town-clerk", "/town-clerk/pages/election-results",
                   "/town-clerk/pages/town-election-results",
                   "/town-clerk/pages/elections"]),
    "wordpress": (re.compile(r"wp-content|wp-json", re.I), ["/wp-sitemap.xml"]),
    "squarespace": (re.compile(r"squarespace", re.I), []),
}

# Tried on EVERY host regardless of CMS. Election results are consistently one or two hops
# below a clerk/elections landing page, and the retry run showed those pages being lost to
# the page cap before the crawl reached them. Seeding them puts the clerk section at the
# FRONT of the BFS frontier (seeds are processed before homepage-discovered links), so the
# results archive is crawled early instead of after the budget runs out. A path that does
# not exist just 404s -- one cheap fetch -- so the list stays short and high-probability.
_COMMON_ELECTION_SEEDS = [
    "/town-clerk", "/clerk", "/elections", "/election-results",
]


def fingerprint(host: str) -> tuple[str, list[str]]:
    """Return (cms_name, seed_urls). ('', [common seeds]) if homepage can't be fetched."""
    common = [f"https://{host}{p}" for p in _COMMON_ELECTION_SEEDS]
    try:
        raw = fetch(f"https://{host}/", tries=2, timeout=25)
    except Exception:  # noqa: BLE001
        return ("", common)
    html = raw[:400_000].decode("utf-8", errors="replace")
    for name, (rx, paths) in _CMS.items():
        if rx.search(html):
            seeds = [f"https://{host}{p}" for p in paths]
            # Dedup while preserving order; CMS-specific seeds first, then the clerk guesses.
            seen = set(seeds)
            seeds += [u for u in common if u not in seen]
            return (name, seeds)
    return ("unknown", common)
