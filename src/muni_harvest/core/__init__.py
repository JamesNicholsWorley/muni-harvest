"""Stdlib-only politeness + I/O core (vendored from AbundanceHistory common.py).

Kept dependency-free so the free Wayback tier runs on a bare CI runner.
"""

from .rate_limit import RateLimiter
from .fetchio import (
    AuditLog,
    DEFAULT_UA,
    append_jsonl,
    cached_fetch,
    fetch,
    fetch_json,
    iter_jsonl,
    read_jsonl,
    safe_filename,
    sha1,
    slugify,
    write_jsonl,
)

__all__ = [
    "RateLimiter",
    "AuditLog",
    "DEFAULT_UA",
    "append_jsonl",
    "cached_fetch",
    "fetch",
    "fetch_json",
    "iter_jsonl",
    "read_jsonl",
    "safe_filename",
    "sha1",
    "slugify",
    "write_jsonl",
]
