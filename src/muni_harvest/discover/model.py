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
    re.compile(r"(^|\.)finalsite\.net$", re.I),       # Medford et al.
    re.compile(r"(^|\.)storage\.googleapis\.com$", re.I),
    re.compile(r"(^|\.)googleapis\.com$", re.I),
    re.compile(r"(^|\.)sanity\.io$", re.I),            # Sanity headless CMS asset CDN (Florida)
    re.compile(r"(^|\.)aptuitivcdn\.com$", re.I),      # Aptuitiv MA municipal-site vendor CDN
    re.compile(r"(^|\.)documents-on-demand\.com$", re.I),  # Laserfiche/GovQA doc portal (Easton)
]

# Extension-LESS document endpoints: CMS routes that serve a file but carry no
# .pdf/.doc suffix, so file_ext() misses them and the crawler wrongly treats them as
# pages (fetching the PDF bytes, recording it as a page). These are the single biggest
# blind spot for election results / recent uploads. Matched on the full URL (path+query).
_DOC_ENDPOINT_RE = re.compile(
    r"/DocumentCenter/View/\d+"                 # CivicPlus DocumentCenter (public route)
    r"|/DocumentCenter/Home/View/\d+"
    r"|/ImageRepository/Document\?[^ ]*documentID="  # CivicPlus React file route
    r"|/common/pages/GetFile\.ash?x"           # CivicLive/Vision GetFile.ashx?key=
    r"|/civicax/filebank/documents/\d+"        # CivicPlus legacy filebank
    r"|/files/serve/\d+"                        # some election archives
    r"|[?&]bidId="                             # DocumentCenter bid attachments
    # Granicus/Vision GovAccess "friendly" document alias: /<section>/files/<slug> with
    # no extension, which 302-redirects to /sites/g/files/vyhlif.../f/uploads/<name>.pdf.
    # Measured 2026-08-04: Hadley's entire election-results archive (2013-2026, incl. the
    # 2025 town-year we still lack) is published this way. file_ext() saw no suffix, so the
    # crawler queued each results PDF as a PAGE, fetched the bytes as HTML, found no links,
    # and never emitted a file node -- it VISITED the document and recorded nothing. The
    # `/pages/` namespace (real HTML) is deliberately excluded so listing pages still crawl.
    r"|/[^/]+/(?:files|documents)/[^/?#.]+/?(?:[?#]|$)"
    r"|/DocView\.aspx\?[^ ]*\bid=\d+",         # Laserfiche portal direct document view
    re.I)


def is_doc_endpoint(url: str) -> bool:
    """True for extension-less CMS document-serving routes (DocumentCenter/View, etc.)."""
    return bool(_DOC_ENDPOINT_RE.search(url))


def norm_host(host: str) -> str:
    host = host.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def is_storage_host(host: str) -> bool:
    h = host.lower()
    return any(rx.search(h) for rx in STORAGE_HOST_RES)


# Off-site document PORTALS: JS-rendered folder/document viewers that a town links to
# instead of hosting the files on its own domain. same_site() drops these, so the
# archive behind them is never reached. Brewster's election results & Town Reports live
# in a Laserfiche portal (portal.laserfiche.com/Portal/Browse.aspx?id=18618) linked from
# the clerk page. A Browse.aspx FOLDER is a listing, not a file, so it must be CRAWLED
# (rendered) rather than recorded as a document -- unlike a storage host, whose links are
# already direct files. is_doc_portal marks the host; crawl.py lets it through same_site.
DOC_PORTAL_HOST_RES = [
    re.compile(r"(^|\.)laserfiche\.com$", re.I),
    re.compile(r"(^|\.)laserfiche\.cloud$", re.I),
]


def is_doc_portal(host: str) -> bool:
    h = host.lower()
    return any(rx.search(h) for rx in DOC_PORTAL_HOST_RES)


def file_ext(url: str) -> str | None:
    path = urlsplit(url).path
    m = _EXT_RE.search(path)
    if m and m.group(1).lower() in FILE_EXTS:
        return m.group(1).lower()
    return None


def is_file_url(url: str) -> bool:
    """A link points at a document if it has a known file extension, lives on a storage
    host (Drive/S3/Dropbox links have no extension but are files), OR is an extension-less
    CMS document endpoint (DocumentCenter/View, ImageRepository, GetFile.ashx)."""
    if file_ext(url):
        return True
    if is_doc_endpoint(url):
        return True
    return is_storage_host(urlsplit(url).netloc)


def serving_host(host: str, timeout: int = 8) -> str:
    """Return the host variant (bare vs www) that actually answers on https. Many MA muni
    sites serve only ONE of `town.gov` / `www.town.gov` and REFUSE the other at the
    connection level (e.g. norwoodma.gov refuses; www.norwoodma.gov serves). Since
    norm_host strips www, the crawler would otherwise always hit the bare (dead) variant.
    Any HTTP response (even 403/404) counts as serving; only connection/DNS failure
    triggers the fallback. Returns the input unchanged if neither answers."""
    import urllib.request
    import urllib.error
    alt = host[4:] if host.startswith("www.") else "www." + host
    for h in (host, alt):
        try:
            req = urllib.request.Request(
                f"https://{h}/", method="GET",
                headers={"User-Agent": "Mozilla/5.0 (research)", "Range": "bytes=0-0"})
            urllib.request.urlopen(req, timeout=timeout).close()
            return h
        except urllib.error.HTTPError:
            return h                      # answered with an HTTP status => serving
        except Exception:                 # noqa: BLE001 — refused / DNS / TLS: try the alt
            continue
    return host


def urlkey(url: str) -> str:
    """Canonical dedup key: scheme-less, www-less, fragment-less, no trailing slash.
    Query IS kept — it matters for CMS endpoints (?id=) and Drive (?id=).

    The PATH is lowercased (host already is): MA muni sites run on case-insensitive
    stacks (IIS/ASP.NET DocumentCenter, Windows Apache), and CivicPlus emits the same
    file as both `/DocumentCenter/View/` and `/documentcenter/view/`. Without this,
    those dedup as two docs and cross-source matching misses them. The QUERY keeps its
    case — Drive/Dropbox/CMS ids there are case-SENSITIVE (`?documentID=`, `?id=`)."""
    p = urlsplit(url)
    host = norm_host(p.netloc)
    path = re.sub(r"/+$", "", p.path).lower() or "/"
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
