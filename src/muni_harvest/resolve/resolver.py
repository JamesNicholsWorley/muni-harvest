"""Cheapest-source-wins resolver.

Given the free-tier evidence already on disk (the Wayback doc index + the tier
cache), emit a per-host routing decision so downstream fetching sends the fewest,
politest requests:

  wayback   host has archived docs        -> pull from Wayback (never touch host)
  live      no archive coverage, T0 works -> cheap live fetch
  browser   T0 blocked                    -> browser tier / unblocker (the paid lever)

This is deliberately host-granular for now; per-URL resolution (exact snapshot vs
live) is layered on with the live fetcher after the probe sizes the browser tier.
"""

from __future__ import annotations

from ..config import data_dir
from ..core import iter_jsonl
from .tier_cache import TierCache


def _hosts_with_wayback() -> set[str]:
    path = data_dir() / "wayback" / "docs.jsonl"
    return {rec["host"] for rec in iter_jsonl(path)}


def resolve_all() -> dict[str, str]:
    """Return {host: source} across every host we have any evidence for."""
    wb = _hosts_with_wayback()
    cache = TierCache()
    decisions: dict[str, str] = {}
    hosts = set(wb) | set(cache._map)
    for host in hosts:
        if host in wb:
            decisions[host] = "wayback"
        else:
            tier = (cache.get(host) or {}).get("tier")
            decisions[host] = "browser" if tier == "blocked" else "live"
    return decisions


def summary() -> dict[str, int]:
    decisions = resolve_all()
    counts: dict[str, int] = {}
    for src in decisions.values():
        counts[src] = counts.get(src, 0) + 1
    total = sum(counts.values()) or 1
    print(f"\n  cheapest-source-wins routing over {total} hosts:")
    for src in ("wayback", "live", "browser"):
        n = counts.get(src, 0)
        print(f"    {src:<9} {n:>4}  ({100 * n / total:.1f}%)")
    print()
    return counts
