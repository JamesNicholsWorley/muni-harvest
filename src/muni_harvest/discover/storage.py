"""Resolve a link on a document-storage host to its true download URL.

Index-only: we compute the resolvable URL and record it; we do NOT fetch bytes.
The actual download (and Drive's large-file confirm-token dance) happens in the
later gated fetch stage.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from .model import norm_host

_DRIVE_ID_RES = [
    re.compile(r"/file/d/([\w-]+)"),
    re.compile(r"/document/d/([\w-]+)"),
    re.compile(r"/spreadsheets/d/([\w-]+)"),
    re.compile(r"/presentation/d/([\w-]+)"),
    re.compile(r"[?&]id=([\w-]+)"),
]


def resolve_download(url: str) -> tuple[str, str]:
    """Return (download_url, storage_host). For non-storage URLs, pass through."""
    host = norm_host(urlsplit(url).netloc)

    if host in ("drive.google.com", "docs.google.com"):
        for rx in _DRIVE_ID_RES:
            m = rx.search(url)
            if m:
                fid = m.group(1)
                return (f"https://drive.google.com/uc?export=download&id={fid}", host)
        return (url, host)

    if host == "dropbox.com" or host.endswith(".dropbox.com"):
        # Force direct download rather than the preview page.
        base = url.split("?")[0]
        return (base + "?dl=1", host)

    # S3 / Azure blob / CloudFront / CivicPlus / Granicus / Revize: already direct.
    from .model import is_storage_host
    if is_storage_host(host):
        return (url, host)

    return (url, "")


def storage_host_of(url: str) -> str:
    return resolve_download(url)[1]
