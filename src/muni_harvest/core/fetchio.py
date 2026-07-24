"""Stdlib-only fetch + JSONL I/O + audit log.

Vendored from AbundanceHistory/harvesters/common.py so this repo deploys to a bare
CI runner / VM with zero pip installs for the free tier. UTF-8 everywhere; ASCII
status markers. Only the User-Agent is changed (project + contact per polite-crawl norms).
"""

from __future__ import annotations

import gzip
import hashlib
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.parse  # noqa: F401  (re-exported convenience for callers building CDX URLs)
import urllib.request
from pathlib import Path
from typing import Iterable, Iterator

DEFAULT_UA = (
    "muni-harvest civic-document research crawler "
    "(personal academic use; contact jamesnicholsworley@gmail.com)"
)


def fetch(url: str, limiter=None, tries: int = 4,
          headers: dict | None = None, timeout: int = 60) -> bytes:
    """GET with UA, optional rate limit, gzip, and backoff on 429/5xx."""
    hdrs = {"User-Agent": DEFAULT_UA, "Accept-Encoding": "gzip"}
    if headers:
        hdrs.update(headers)
    for attempt in range(1, tries + 1):
        if limiter:
            limiter.wait()
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < tries:
                # Honour Retry-After when the server offers one, else exp backoff.
                back = int(exc.headers.get("Retry-After") or 0) or 2 ** attempt
                print(f"[WARN] HTTP {exc.code} on {url[:70]}... "
                      f"backoff {back}s (try {attempt})", file=sys.stderr)
                time.sleep(back)
                continue
            raise
        except (urllib.error.URLError, http.client.IncompleteRead,
                TimeoutError) as exc:
            if attempt < tries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"network error on {url}: {exc}") from exc
    raise RuntimeError(f"exhausted retries: {url}")


def fetch_json(url: str, limiter=None, headers: dict | None = None):
    """Fetch and json-decode. Returns whatever the endpoint yields (dict OR list;
    Wayback CDX returns a list-of-lists)."""
    return json.loads(fetch(url, limiter, headers=headers).decode(
        "utf-8", errors="replace"))


def cached_fetch(url: str, cache_dir: Path, limiter=None,
                 headers: dict | None = None, suffix: str = ".html") -> str:
    """Fetch `url`, caching the decoded body under cache_dir/<sha1>. Resumable:
    a cached response is returned without a network call."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    path = cache_dir / f"{key}{suffix}"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    body = fetch(url, limiter, headers=headers).decode("utf-8", errors="replace")
    path.write_text(body, encoding="utf-8")
    return body


# --- filenames / slugs --------------------------------------------------------
_WIN_BAD = re.compile(r'[<>:"/\\|?*]')
_NONWORD = re.compile(r"[^\w\s-]")
_SPACES = re.compile(r"[\s_-]+")


def slugify(text: str, maxlen: int = 80) -> str:
    """Lowercase hyphenated slug for ids/filenames (canonical entity keys)."""
    text = _NONWORD.sub("", text.strip().lower())
    text = _SPACES.sub("-", text).strip("-")
    return text[:maxlen].strip("-")


def safe_filename(text: str, maxlen: int = 120) -> str:
    """Strip Windows-illegal chars for a cache/note filename (keeps case)."""
    text = _WIN_BAD.sub("", text).strip()
    return text[:maxlen].rstrip(". ")


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


# --- JSONL i/o ----------------------------------------------------------------
def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_jsonl(path: Path, records: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


def append_jsonl(path: Path, records: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


def iter_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


# --- audit logging ------------------------------------------------------------
class AuditLog:
    """Tab-separated, timestamped, flushed audit trail (per harvester)."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("a", encoding="utf-8")

    def write(self, msg: str) -> None:
        self._fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{msg}\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
