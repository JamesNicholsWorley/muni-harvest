"""Node model, URL normalization, doctype classification, and the cross-domain
document policy (same-site pages, but off-host files from a storage allowlist).
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

# --- file detection -----------------------------------------------------------
FILE_EXTS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "csv", "txt", "rtf", "zip", "tif", "tiff",
}
_EXT_RE = re.compile(r"\.([a-z0-9]{2,5})$", re.I)

# Known third-party document stores. A link to any of these is treated as a FILE
# (the town's document living off-host), NOT a page to crawl. This is what lets us
# follow a PDF onto S3 / Google Drive without wandering onto unrelated websites.
STORAGE_HOST_RES = [
    re.compile(r"(^|\.)s3[.-][\w-]*\.amazonaws\.com$", re.I),
    re.compile(r"(^|\.)s3\.amazonaws\.com$", re.I),
    re.compile(r"(^|\.)blob\.core\.windows\.net$", re.I),
    re.compile(r"(^|\.)drive\.google\.com$", re.I),
    re.compile(r"(^|\.)docs\.google\.com$", re.I),
    re.compile(r"(^|\.)dropbox\.com$", re.I),
    re.compile(r"(^|\.)box\.com$", re.I),
    re.compile(r"(^|\.)civicplus\.com$", re.I),
    re.compile(r"(^|\.)revize\.com$", re.I),
    re.compile(r"(^|\.)granicus\.com$", re.I),
    re.compile(r"(^|\.)cloudfront\.net$", re.I),
    re.compile(r"(^|\.)squarespace\.com$", re.I),
]


def norm_host(host: str) -> str:
    host = host.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def is_storage_host(host: str) -> bool:
    h = host.lower()
    return any(rx.search(h) for rx in STORAGE_HOST_RES)


def file_ext(url: str) -> str | None:
    path = urlsplit(url).path
    m = _EXT_RE.search(path)
    if m and m.group(1).lower() in FILE_EXTS:
        return m.group(1).lower()
    return None


def is_file_url(url: str) -> bool:
    """A link points at a document if it has a known file extension OR lives on a
    storage host (Drive/S3/Dropbox links have no extension but are files)."""
    if file_ext(url):
        return True
    return is_storage_host(urlsplit(url).netloc)


def urlkey(url: str) -> str:
    """Canonical dedup key: scheme-less, www-less, fragment-less, no trailing slash.
    Query IS kept — it matters for CMS endpoints (?id=) and Drive (?id=)."""
    p = urlsplit(url)
    host = norm_host(p.netloc)
    path = re.sub(r"/+$", "", p.path) or "/"
    key = host + path
    if p.query:
        key += "?" + p.query
    return key


def same_site(host: str, seed_host: str) -> bool:
    """True if `host` is the seed host or a subdomain of it (after www-stripping).
    Keeps page-crawling on the municipality's own domain."""
    h, s = norm_host(host), norm_host(seed_host)
    return h == s or h.endswith("." + s)


# --- doctype classification (URL + anchor text) -------------------------------
_DOC_RES = [
    ("agenda",   re.compile(r"agenda", re.I)),
    ("minutes",  re.compile(r"\bminutes\b|meeting[-_ ]?minutes", re.I)),
    ("election", re.compile(r"election|canvass|precinct|tally|ballot|"
                            r"result(s)?\b", re.I)),
    ("budget",   re.compile(r"budget|acfr|annual[-_ ]?report|appropriat", re.I)),
    ("warrant",  re.compile(r"warrant|town[-_ ]?meeting", re.I)),
    ("bylaw",    re.compile(r"by[-_ ]?law|charter|ordinance|zoning[-_ ]?bylaw", re.I)),
    ("planning", re.compile(r"\bzba\b|zoning|planning|variance|special[-_ ]?permit", re.I)),
]


def classify_doc(url: str, anchor: str = "") -> str:
    hay = f"{url} {anchor}"
    for name, rx in _DOC_RES:
        if rx.search(hay):
            return name
    return "other"


# --- node record --------------------------------------------------------------
def make_node(*, seed_host: str, url: str, kind: str, municipality: str = "",
              mimetype: str = "", anchor: str = "", depth: int = 0,
              parent_url: str = "", breadcrumb: str = "",
              discovered_via: str = "crawl", storage_host: str = "") -> dict:
    """One manifest record. `kind` is 'page' or 'file'. The nav-tree is encoded by
    (parent_url, depth, breadcrumb, anchor)."""
    return {
        "seed_host": seed_host,
        "municipality": municipality,
        "url": url,
        "urlkey": urlkey(url),
        "kind": kind,
        "mimetype": mimetype,
        "doctype": classify_doc(url, anchor) if kind == "file" else "",
        "anchor": anchor[:200],
        "depth": depth,
        "parent_url": parent_url,
        "breadcrumb": breadcrumb[:300],
        "discovered_via": discovered_via,
        "storage_host": storage_host,
    }
