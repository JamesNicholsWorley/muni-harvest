"""Discovery orchestrator — union Wayback + sitemaps + live crawl + CMS per host.

For each host: load robots -> fingerprint CMS -> enumerate sitemaps -> polite crawl
-> fold in existing Wayback docs. Everything is deduped by urlkey into a single
manifest (data/discover/nodes.jsonl), with per-source contribution deltas logged so
coverage gaps are documented, never silently asserted. Resumable: hosts already in
done.txt are skipped. INDEX-ONLY — no document bytes are fetched here.
"""

from __future__ import annotations

import csv
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..archive.wayback import host_of
from ..config import data_dir, load_settings, resolve_path
from ..core import AuditLog, append_jsonl, iter_jsonl
from .cms import fingerprint
from .crawl import crawl_site
from .model import is_file_url, make_node, norm_host
from .robots import RobotsPolicy
from .sitemaps import sitemap_urls
from .storage import resolve_download


def host_to_municipality(inventory) -> dict[str, str]:
    from ..config import host_overrides
    overrides = host_overrides()
    m: dict[str, str] = {}
    with inventory.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            u = (row.get("native_url") or "").strip()
            if u:
                h = host_of(u)
                m.setdefault(overrides.get(h, h), row.get("municipality", ""))
    return m


def wayback_by_host() -> dict[str, list[dict]]:
    """Group the existing Wayback doc index by host (empty if not harvested yet)."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for rec in iter_jsonl(data_dir() / "wayback" / "docs.jsonl"):
        grouped[rec["host"]].append(rec)
    return grouped


def discover_host(host: str, municipality: str, cfg: dict,
                  wb_docs: list[dict], tier: str = "T0",
                  pool=None) -> tuple[list[dict], dict]:
    dc = cfg["discover"]
    # T1/T2 hosts block plain HTTP -> crawl their live pages through the browser.
    use_browser = tier in ("T1", "T2") and pool is not None
    robots = RobotsPolicy(host).load()
    cms_name, cms_seeds = fingerprint(host)

    # Sitemaps: files become nodes directly; pages seed the crawl frontier (capped).
    sm_nodes, sm_page_seeds = [], []
    for u in sitemap_urls(host, robots.sitemaps, max_urls=dc["sitemap_max_urls"]):
        if is_file_url(u):
            dl, shost = resolve_download(u)
            sm_nodes.append(make_node(seed_host=host, municipality=municipality,
                                      url=dl, kind="file", discovered_via="sitemap",
                                      storage_host=shost))
        else:
            sm_page_seeds.append(u)

    crawl_seeds = cms_seeds + sm_page_seeds[:dc["max_seed_pages"]]
    # T2 browser crawl is slow; cap its pages tighter than the T0 stdlib crawl.
    cap = dc.get("max_pages_browser", 60) if use_browser else dc["max_pages"]
    crawl_nodes = crawl_site(host, municipality=municipality, robots=robots,
                             seed_urls=crawl_seeds, max_depth=dc["max_depth"],
                             max_pages=cap, base_delay=dc["base_delay_s"],
                             pool=pool, use_browser=use_browser,
                             max_consec_429=dc.get("max_consec_429", 5))

    wb_nodes = [make_node(seed_host=host, municipality=municipality, url=r["url"],
                          kind="file", mimetype=r.get("mimetype", ""),
                          discovered_via="wayback") for r in wb_docs]

    # Union + dedup by urlkey; track which sources contributed each key.
    by_key: dict[str, dict] = {}
    src_keys: dict[str, set] = defaultdict(set)
    for n in wb_nodes + sm_nodes + crawl_nodes:
        src_keys[n["discovered_via"]].add(n["urlkey"])
        by_key.setdefault(n["urlkey"], n)
    nodes = list(by_key.values())

    all_keys = set(by_key)
    only_in = {}
    for src, keys in src_keys.items():
        others = set().union(*[v for s, v in src_keys.items() if s != src]) if len(src_keys) > 1 else set()
        only_in[src] = len(keys - others)

    stats = {
        "host": host, "municipality": municipality, "cms": cms_name,
        "total_nodes": len(nodes),
        "files": sum(1 for n in nodes if n["kind"] == "file"),
        "pages": sum(1 for n in nodes if n["kind"] == "page"),
        "by_source": {s: len(k) for s, k in src_keys.items()},
        "only_in_source": only_in,
        "unique_keys": len(all_keys),
    }
    return nodes, stats


def run(*, limit: int | None = None, workers: int | None = None,
        hosts_file: str | None = None, max_pages: int | None = None,
        max_depth: int | None = None, shard: str | None = None) -> dict:
    cfg = load_settings()
    if max_pages is not None:
        cfg["discover"]["max_pages"] = max_pages
    if max_depth is not None:
        cfg["discover"]["max_depth"] = max_depth
    workers = workers or cfg["discover"]["workers"]
    inventory = resolve_path(cfg["paths"]["inventory_csv"])

    if hosts_file:
        from ..archive.wayback import load_hosts_file
        hosts = load_hosts_file(resolve_path(hosts_file), limit=limit)
        muni_map = host_to_municipality(inventory) if inventory.exists() else {}
    else:
        from ..archive.wayback import load_hosts
        hosts = load_hosts(inventory, limit=limit)
        muni_map = host_to_municipality(inventory)
    if shard:
        from ..archive.wayback import shard_hosts
        hosts = shard_hosts(hosts, shard)

    out_dir = data_dir() / "discover"
    nodes_path = out_dir / "nodes.jsonl"
    stats_path = out_dir / "stats.jsonl"
    done_path = out_dir / "done.txt"
    out_dir.mkdir(parents=True, exist_ok=True)

    done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()
    todo = [h for h in hosts if norm_host(h) not in done]
    wb = wayback_by_host()

    # Tier map: T1/T2 hosts get a warm browser for their live crawl.
    from ..resolve.tier_cache import TierCache
    tiers = {h: (rec or {}).get("tier", "T0")
             for h, rec in ((x, TierCache().get(x)) for x in map(norm_host, todo))}
    n_browser = sum(1 for t in tiers.values() if t in ("T1", "T2"))
    browser_pool = None
    if n_browser:
        try:
            from ..fetchers.browser_pool import BrowserPool
            browser_pool = BrowserPool(size=3)
        except Exception as exc:  # noqa: BLE001 — no `live` extra: T2 falls back to stdlib
            print(f"[warn] browser tier unavailable ({exc}); {n_browser} T2 hosts "
                  f"will use stdlib crawl")

    print(f"[*] discover: {len(todo)} hosts ({len(done)} done); {workers} workers; "
          f"{n_browser} via browser tier")
    if not todo:
        return {"hosts": 0}

    lock = threading.Lock()
    audit = AuditLog(out_dir / "audit.log")
    totals = {"hosts": 0, "nodes": 0, "files": 0}

    def work(host: str) -> None:
        h = norm_host(host)
        try:
            nodes, stats = discover_host(h, muni_map.get(h, ""), cfg, wb.get(h, []),
                                         tier=tiers.get(h, "T0"), pool=browser_pool)
        except Exception as exc:  # noqa: BLE001
            audit.write(f"ERR\t{h}\t{exc}")
            return
        with lock:
            if nodes:
                append_jsonl(nodes_path, nodes)
            append_jsonl(stats_path, [stats])
            with done_path.open("a", encoding="utf-8") as fh:
                fh.write(h + "\n")
            totals["hosts"] += 1
            totals["nodes"] += len(nodes)
            totals["files"] += stats["files"]
        audit.write(f"OK\t{h}\t{stats['files']} files\t{stats['pages']} pages"
                    f"\tcms={stats['cms']}\ttier={tiers.get(h)}")
        print(f"  [OK] {h:<34} files={stats['files']:>5} pages={stats['pages']:>4} "
              f"tier={tiers.get(h,'T0'):<4} cms={stats['cms']}")

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for _ in as_completed([executor.submit(work, h) for h in todo]):
                pass
    finally:
        if browser_pool:
            browser_pool.close()
    audit.close()
    print(f"\n[done] hosts={totals['hosts']} nodes={totals['nodes']} "
          f"files={totals['files']} -> {nodes_path}")
    return totals
