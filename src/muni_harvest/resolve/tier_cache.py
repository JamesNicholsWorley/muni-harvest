"""Resumable domain -> tier cache (probe each of the 429 domains once, not per page).

Backed by an append-only JSONL; last-write-wins on re-probe. Tiers:
  T0        cheap stdlib/threaded HTTP works
  blocked   T0 refused (WAF/challenge) -> needs the browser tier (T1/T2) or unblocker
  live_none no archive coverage; must be fetched live
"""

from __future__ import annotations

import time
from pathlib import Path

from ..config import data_dir
from ..core import append_jsonl, iter_jsonl


class TierCache:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "tier_cache.jsonl")
        self._map: dict[str, dict] = {}
        for rec in iter_jsonl(self.path):
            self._map[rec["host"]] = rec  # later records override earlier

    def get(self, host: str) -> dict | None:
        return self._map.get(host)

    def has(self, host: str) -> bool:
        return host in self._map

    def set(self, host: str, tier: str, **extra) -> dict:
        rec = {"host": host, "tier": tier,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **extra}
        append_jsonl(self.path, [rec])
        self._map[host] = rec
        return rec

    def histogram(self) -> dict[str, int]:
        hist: dict[str, int] = {}
        for rec in self._map.values():
            hist[rec["tier"]] = hist.get(rec["tier"], 0) + 1
        return hist
