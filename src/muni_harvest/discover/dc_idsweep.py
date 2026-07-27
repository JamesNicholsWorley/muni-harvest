"""DocumentCenter ID-sweep — the last-resort recovery for DE-LINKED archives.

`docsweep` recovers every document CURRENTLY linked on a site; Wayback recovers docs that
were linked HISTORICALLY. A document that has been de-linked from every page AND never
snapshotted by Wayback (e.g. an old election-results PDF the town replaced with a newer
one) is invisible to both. But CivicPlus serves every document deterministically at
`/DocumentCenter/View/{id}` with a globally-sequential per-site id, so we can find the
survivors by probing the id space.

Gap-aware: only ids NOT already in the corpus are probed (docsweep + Wayback + crawl
already cover the bulk), so the volume is a fraction of the full range. HEAD requests
(cheap, no file body). Resumable per host (cursor = highest id swept), shardable by host,
rate-limited. Never truncates silently — a hit ceiling is logged.
"""

from __future__ import annotations

import re
import threading
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..archive.wayback import shard_hosts
from ..config import data_dir, load_settings
from ..core import RateLimiter, append_jsonl, iter_jsonl

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_VIEW = re.compile(r"/DocumentCenter/View/(\d+)", re.I)
_IMG = re.compile(r"documentID=(\d+)", re.I)


def _known_ids_by_host() -> dict[str, dict]:
    """host -> {'url_host': str, 'ids': set[int]} from all corpus node files."""
    out: dict[str, dict] = defaultdict(lambda: {"url_host": "", "ids": set()})
    disc = data_dir() / "discover"
    for name in ("nodes.jsonl", "nodes_docsweep.jsonl", "nodes_minutes.jsonl"):
        p = disc / name
        if not p.exists():
            continue
        for n in iter_jsonl(p):
            u = n.get("url", "")
            m = _VIEW.search(u) or _IMG.search(u)
            if not m:
                continue
            host = n.get("seed_host") or re.sub(r"^https?://", "", u).split("/")[0]
            rec = out[host]
            rec["ids"].add(int(m.group(1)))
            if not rec["url_host"]:
                rec["url_host"] = re.sub(r"^https?://", "", u).split("/")[0].split(":")[0]
    return out


def _probe(url_host: str, doc_id: int, *, timeout: int = 15) -> tuple[bool, str]:
    """Probe /DocumentCenter/View/{id}; return (exists, final_url).

    NOTE: CivicPlus IIS returns 404 to HEAD requests but 200 to GET for the very same
    valid document — so we must GET. We send `Range: bytes=0-0` and read only a tiny
    chunk to avoid downloading the whole PDF; existence = HTTP 200/206 with a
    non-HTML content-type (an invalid id redirects to an HTML 'not found' page)."""
    url = f"https://{url_host}/DocumentCenter/View/{doc_id}"
    req = urllib.request.Request(
        url, method="GET",
        headers={"User-Agent": _UA, "Range": "bytes=0-1023",
                 "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "").lower()
            final = r.geturl()
            r.read(64)  # touch the stream, then close early
            return ("html" not in ctype and r.status in (200, 206)), final
    except urllib.error.HTTPError:
        return False, url        # 404 for a nonexistent/deleted id
    except Exception:  # noqa: BLE001
        return False, url


def _ceiling(url_host: str, start: int, limiter, *, run: int = 60, cap: int = 200000) -> int:
    """Extend past the known max to catch docs newer than our harvest: walk upward until
    `run` consecutive misses. Returns the highest id worth sweeping to."""
    cid = start
    misses = 0
    probe_at = start + 1
    while misses < run and probe_at <= cap:
        limiter.wait()
        ok, _ = _probe(url_host, probe_at)
        if ok:
            cid = probe_at
            misses = 0
        else:
            misses += 1
        probe_at += 1
    return cid


def run(*, workers: int = 8, shard: str | None = None, limit: int | None = None,
        max_id: int = 200000, extend: bool = True) -> dict:
    from .recover_manifest import load_dc
    known = load_dc()          # committed manifest (works on Actions, no corpus needed)
    if known is None:          # local fallback: scan the full corpus
        known = _known_ids_by_host()
    hosts = sorted(known)
    if shard:
        hosts = shard_hosts(hosts, shard)
    if limit:
        hosts = hosts[:limit]

    out_dir = data_dir() / "discover"
    out_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = out_dir / "nodes_idsweep.jsonl"
    done_path = out_dir / "idsweep_done.txt"
    done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()
    todo = [h for h in hosts if h not in done]
    print(f"[*] DocumentCenter id-sweep: {len(todo)} hosts ({len(done)} done); {workers} workers")

    limiter = RateLimiter(load_settings()["wayback"]["per_host_rpm"])
    lock = threading.Lock()
    totals = {"hosts": 0, "probed": 0, "recovered": 0, "capped": 0}

    def work(host: str) -> None:
        rec = known[host]
        url_host, ids = rec["url_host"] or host, rec["ids"]
        if not ids:
            with lock:
                done_path.open("a", encoding="utf-8").write(host + "\n")
            return
        top = max(ids)
        if extend:
            top = _ceiling(url_host, top, limiter, cap=max_id)
        capped = top >= max_id
        gaps = [i for i in range(1, top + 1) if i not in ids]
        rows, probed = [], 0
        for i in gaps:
            limiter.wait()
            probed += 1
            ok, final = _probe(url_host, i)
            if ok:
                slug = final.split("/View/")[-1]
                name = slug.split("/", 1)[1] if "/" in slug else ""
                url = f"https://{url_host}/DocumentCenter/View/{i}"
                rows.append({"seed_host": host, "municipality": "", "url": url,
                             "urlkey": url.split("//", 1)[-1].lower(), "kind": "file",
                             "mimetype": "application/pdf", "doctype": "",
                             "anchor": name.replace("-", " ")[:200], "depth": 2,
                             "parent_url": f"https://{url_host}/DocumentCenter",
                             "breadcrumb": "", "discovered_via": "dc_idsweep",
                             "storage_host": ""})
        with lock:
            if rows:
                append_jsonl(nodes_path, rows)
            done_path.open("a", encoding="utf-8").write(host + "\n")
            totals["hosts"] += 1
            totals["probed"] += probed
            totals["recovered"] += len(rows)
            totals["capped"] += int(capped)
        note = "  [CAP HIT - rerun w/ higher --max-id]" if capped else ""
        print(f"  [OK] {host:<30} known={len(ids):>5} gaps={len(gaps):>6} "
              f"recovered={len(rows):>5}{note}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for _ in as_completed([ex.submit(work, h) for h in todo]):
            pass
    print(f"\n[done] id-sweep: recovered {totals['recovered']:,} de-linked docs from "
          f"{totals['probed']:,} probes across {totals['hosts']} hosts"
          + (f"; {totals['capped']} hosts hit the id cap" if totals['capped'] else "")
          + f" -> {nodes_path}")
    return totals
