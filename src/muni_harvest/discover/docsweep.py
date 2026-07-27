"""Sitemap-seeded WHOLE-SITE document sweep — recover every publicly-linked document.

Why this exists: the CivicPlus DocumentCenter React API (`GetDocumentsForAFolder`) is
auth-walled, so the folder tree can't be fully enumerated via the backdoor. But every
document is still publicly served at `/DocumentCenter/View/{id}` (and `/ImageRepository`)
and is LINKED from the town's content pages (e.g. `/772/Election-Results`). Those content
pages are all listed in `/sitemap.xml`. So: fetch the sitemap -> fetch every content page
-> extract every document link (now including extension-less CMS routes, see
`model.is_doc_endpoint`) -> emit doc nodes + page nodes.

This is CMS-agnostic (works for DocumentCenter, Revize, WordPress, freeform), needs no
auth and no browser for T0 hosts, and — unlike the BFS crawl — is bounded by the sitemap
so it does not truncate at a page cap. Resumable + shardable for GitHub Actions.
"""

from __future__ import annotations

import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urldefrag, urljoin, urlsplit

from ..archive.wayback import load_hosts, load_hosts_file
from ..config import data_dir, load_settings, resolve_path
from ..core import RateLimiter, append_jsonl, fetch
from .crawl import AdaptiveDelay, _SKIP_SCHEMES
from .htmllinks import extract
from .model import is_file_url, make_node, norm_host, same_site, urlkey
from .pipeline import host_to_municipality
from .robots import RobotsPolicy
from .sitemaps import sitemap_urls
from .storage import resolve_download

# CivicPlus content-page ids are numeric (`/772/Election-Results`); also hit the common
# CMS section roots so a thin sitemap doesn't hide the document-heavy pages.
_EXTRA_SEEDS = ("/DocumentCenter", "/AgendaCenter", "/Archive.aspx", "/ArchiveCenter")


def _get(url: str, *, pool=None, use_browser: bool = False, timeout: int = 25) -> str:
    if use_browser and pool is not None:
        with pool.lease() as d:
            d.get(url)
            return (d.page_source or "")[:2_000_000]
    raw = fetch(url, tries=1, timeout=timeout)
    return raw[:2_000_000].decode("utf-8", errors="replace")


def sweep_host(host: str, municipality: str = "", *, pool=None,
               use_browser: bool = False, max_pages: int = 6000,
               base_delay: float = 1.0, max_consec_fail: int = 8) -> tuple[list[dict], dict]:
    """Fetch all sitemap content pages and harvest every linked document."""
    robots = RobotsPolicy(host).load()
    pacer = AdaptiveDelay(max(base_delay, float(getattr(robots, "crawl_delay", 0) or 0)))
    home = f"https://{host}/"

    # Partition sitemap output: files are nodes now; pages get fetched for their doc links.
    file_seeds: list[str] = []
    page_seeds: list[str] = [home] + [f"https://{host}{p}" for p in _EXTRA_SEEDS]
    for u in sitemap_urls(host, robots.sitemaps, max_urls=max_pages):
        (file_seeds if is_file_url(u) else page_seeds).append(u)

    nodes: list[dict] = []
    emitted: set[str] = set()
    fetched: set[str] = set()

    def emit(node: dict) -> None:
        k = node["urlkey"]
        if k not in emitted:
            emitted.add(k)
            nodes.append(node)

    for u in file_seeds:
        dl, shost = resolve_download(u)
        emit(make_node(seed_host=host, municipality=municipality, url=dl, kind="file",
                       discovered_via="sitemap", storage_host=shost))

    pages = docs = fails = 0
    for purl in dict.fromkeys(page_seeds):
        if pages >= max_pages:
            break
        k = urlkey(purl)
        if k in fetched:
            continue
        fetched.add(k)
        if not robots.allowed(purl):
            continue
        pacer.sleep()
        t0 = time.monotonic()
        try:
            html = _get(purl, pool=pool, use_browser=use_browser)
        except urllib.error.HTTPError as exc:
            fails += 1
            if exc.code in (429, 503):
                pacer.throttled()
                if fails >= max_consec_fail:
                    break
            continue
        except Exception:  # noqa: BLE001
            fails += 1
            pacer.throttled()
            if fails >= max_consec_fail:
                break
            continue
        fails = 0
        pacer.ok(time.monotonic() - t0)
        pages += 1

        page = extract(html)
        emit(make_node(seed_host=host, municipality=municipality, url=purl, kind="page",
                       mimetype="text/html", breadcrumb=page.breadcrumb or page.title,
                       discovered_via="docsweep"))
        for href, text in page.links:
            if not href or href.lower().startswith(_SKIP_SCHEMES):
                continue
            absu = urldefrag(urljoin(purl, href))[0]
            if not absu.lower().startswith("http"):
                continue
            if is_file_url(absu):
                dl, shost = resolve_download(absu)
                before = len(emitted)
                emit(make_node(seed_host=host, municipality=municipality, url=dl,
                               kind="file", anchor=text, parent_url=purl,
                               breadcrumb=page.breadcrumb or page.title,
                               discovered_via="docsweep", storage_host=shost))
                docs += len(emitted) - before

    stats = {"host": host, "municipality": municipality, "pages": pages,
             "docs": docs, "nodes": len(nodes),
             "files": sum(1 for n in nodes if n["kind"] == "file")}
    return nodes, stats


def run(*, workers: int = 8, hosts_file: str | None = None, shard: str | None = None,
        max_pages: int = 6000, limit: int | None = None) -> dict:
    cfg = load_settings()
    inv = resolve_path(cfg["paths"]["inventory_csv"])
    hosts = (load_hosts_file(resolve_path(hosts_file), limit=limit) if hosts_file
             else load_hosts(inv, limit=limit))
    if shard:
        from ..archive.wayback import shard_hosts
        hosts = shard_hosts(hosts, shard)
    muni = host_to_municipality(inv) if inv.exists() else {}

    out_dir = data_dir() / "discover"
    out_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = out_dir / "nodes_docsweep.jsonl"      # separate file; merge/dedup later
    stats_path = out_dir / "docsweep_stats.jsonl"
    done_path = out_dir / "docsweep_done.txt"
    done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()

    # tier map: browser-tier hosts crawl live pages via a warm pool
    from ..resolve.tier_cache import TierCache
    todo = [norm_host(h) for h in hosts if norm_host(h) not in done]
    tiers = {h: (TierCache().get(h) or {}).get("tier", "T0") for h in todo}
    n_browser = sum(1 for t in tiers.values() if t in ("T1", "T2"))
    pool = None
    if n_browser:
        try:
            from ..fetchers.browser_pool import BrowserPool
            pool = BrowserPool(size=3)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] browser tier unavailable ({exc}); {n_browser} hosts use stdlib")

    print(f"[*] docsweep: {len(todo)} hosts ({len(done)} done); {workers} workers; "
          f"{n_browser} via browser tier")
    lock = threading.Lock()
    totals = {"hosts": 0, "docs": 0, "nodes": 0}

    def work(host: str) -> None:
        use_browser = tiers.get(host) in ("T1", "T2") and pool is not None
        try:
            nodes, stats = sweep_host(host, muni.get(host, ""), pool=pool,
                                      use_browser=use_browser, max_pages=max_pages)
        except Exception as exc:  # noqa: BLE001
            with lock:
                with done_path.open("a", encoding="utf-8") as fh:
                    fh.write(host + "\n")
            print(f"  [ERR] {host}: {exc}")
            return
        with lock:
            if nodes:
                append_jsonl(nodes_path, nodes)
            append_jsonl(stats_path, [stats])
            with done_path.open("a", encoding="utf-8") as fh:
                fh.write(host + "\n")
            totals["hosts"] += 1
            totals["docs"] += stats["docs"]
            totals["nodes"] += len(nodes)
        print(f"  [OK] {host:<32} pages={stats['pages']:>4} files={stats['files']:>5} "
              f"tier={tiers.get(host,'T0')}")

    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for _ in as_completed([ex.submit(work, h) for h in todo]):
                pass
    finally:
        if pool:
            pool.close()
    print(f"\n[done] docsweep: hosts={totals['hosts']} nodes={totals['nodes']} "
          f"docs~={totals['docs']} -> {nodes_path}")
    return totals
