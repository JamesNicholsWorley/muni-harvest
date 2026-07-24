"""Common Crawl — discovery ONLY (homepage / CMS fingerprint).

Measured 100-1000x shallower than Wayback for municipal documents, so CC is used
purely to confirm domain presence and grab the homepage capture for CMS
fingerprinting. Always the HTTPS CDN index — never the s3:// path, which silently
bills (requester-pays).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse

from ..core import fetch


def cc_lookup(host: str, index: str, endpoint: str, limiter=None) -> list[dict]:
    """Rows CC has for `host` in one monthly index. [] if absent (404) or error."""
    q = urllib.parse.urlencode({"url": host, "output": "json"})
    url = f"{endpoint}/{index}-index?{q}"
    if limiter:
        limiter.wait()
    try:
        body = fetch(url, tries=2, timeout=30).decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, RuntimeError):
        return []
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def present(host: str, index: str, endpoint: str, limiter=None) -> bool:
    return bool(cc_lookup(host, index, endpoint, limiter=limiter))
