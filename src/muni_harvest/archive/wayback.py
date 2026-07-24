"""Parallelized Wayback CDX harvester — the free, deep, primary document source.

Wayback holds ~100-1000x the municipal-document depth of Common Crawl; its only
weakness is per-query latency (~13s median, ~33% first-try timeouts). That is
latency-bound, not rate-bound, so a bounded ThreadPoolExecutor collapses a ~94-min
serial sweep to ~5 min. Generalized from CivicAtlasMA/src/wayback_recover.py:
this enumerates ALL archived PDFs per host (not just election docs) and tags a
civic doctype for downstream routing, rather than filtering the corpus down.

Everything is stdlib-only and resumable:
  - results  -> data/wayback/docs.jsonl   (append-only, write-locked)
  - progress -> data/wayback/done.txt      (one host per completed domain)
Re-running skips hosts already in done.txt.
"""

from __future__ import annotations

import csv
import re
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from ..config import data_dir, load_settings, resolve_path
from ..core import AuditLog, RateLimiter, append_jsonl, fetch_json

CDX = "https://web.archive.org/cdx/search/cdx"

# Doctype tagging (classify, do NOT filter — we keep everything).
_DOCTYPE_RES = [
    ("election", re.compile(r"election|result|canvass|precinct|tally", re.I)),
    ("minutes",  re.compile(r"minutes|agenda|meeting", re.I)),
    ("planning", re.compile(r"zba|zoning|planning|variance|special[-_ ]?permit", re.I)),
    ("finance",  re.compile(r"budget|acfr|annual[-_ ]?report|warrant|bid|tabulation", re.I)),
    ("bylaw",    re.compile(r"by[-_ ]?law|charter|ordinance|regulation", re.I)),
]


def classify(url: str) -> str:
    for name, rx in _DOCTYPE_RES:
        if rx.search(url):
            return name
    return "other"


def host_of(url: str) -> str:
    net = urlparse(url if "//" in url else "//" + url).netloc.lower()
    return net[4:] if net.startswith("www.") else net


def load_hosts(inventory_csv: Path, limit: int | None = None) -> list[str]:
    """Unique hosts from the inventory's native_url column."""
    hosts: list[str] = []
    seen = set()
    with inventory_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            url = (row.get("native_url") or "").strip()
            if not url:
                continue
            h = host_of(url)
            if h and h not in seen:
                seen.add(h)
                hosts.append(h)
    hosts.sort()
    return hosts[:limit] if limit else hosts


def wayback_docs(host: str, *, limiter: RateLimiter | None = None,
                 mimetype: str = "application/pdf", max_pages: int = 12,
                 collapse: str = "urlkey", tries: int = 4,
                 timeout: int = 90) -> list[dict]:
    """All archived docs of `mimetype` under `host`, paginated via resumeKey.

    Returns [{host, url, timestamp, mimetype, doctype}]. Network errors bubble up
    so the caller can record the failure and retry the host later.
    """
    out: list[dict] = []
    resume: str | None = None
    seen: set[str] = set()
    for _ in range(max_pages):
        params = [
            ("url", host), ("matchType", "host"),
            ("filter", "statuscode:200"), ("filter", f"mimetype:{mimetype}"),
            ("collapse", collapse), ("output", "json"), ("limit", "2000"),
            ("showResumeKey", "true"), ("fl", "original,timestamp,mimetype"),
        ]
        if resume:
            params.append(("resumeKey", resume))
        # One shared limiter governs every worker's CDX call so we stay polite to
        # web.archive.org even with 20 threads in flight.
        if limiter:
            limiter.wait()
        rows = fetch_json(f"{CDX}?{urllib.parse.urlencode(params)}")
        if not rows or len(rows) < 2:
            break
        body = rows[1:]
        resume = None
        # A trailing blank/one-col row carries the resumeKey token.
        if body and (not body[-1] or len(body[-1]) == 1):
            if body[-1] and body[-1][0]:
                resume = body[-1][0]
            body = [r for r in body if r and len(r) >= 2]
        for r in body:
            orig, ts = r[0], r[1]
            mime = r[2] if len(r) > 2 else mimetype
            if orig in seen:
                continue
            seen.add(orig)
            out.append({"host": host, "url": orig, "timestamp": ts,
                        "mimetype": mime, "doctype": classify(orig)})
        if not resume:
            break
    return out


def harvest(*, limit: int | None = None, workers: int | None = None) -> dict:
    """Concurrent Wayback sweep over the inventory's unique hosts. Resumable."""
    cfg = load_settings()
    wb = cfg["wayback"]
    workers = workers or wb["workers"]
    inventory = resolve_path(cfg["paths"]["inventory_csv"])
    if not inventory.exists():
        raise SystemExit(f"[ERR] inventory not found: {inventory}")

    out_dir = data_dir() / "wayback"
    docs_path = out_dir / "docs.jsonl"
    done_path = out_dir / "done.txt"
    out_dir.mkdir(parents=True, exist_ok=True)

    done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()
    hosts = [h for h in load_hosts(inventory, limit=limit) if h not in done]
    print(f"[*] {len(hosts)} hosts to enumerate "
          f"({len(done)} already done); {workers} workers")
    if not hosts:
        return {"hosts": 0, "docs": 0}

    limiter = RateLimiter(wb["per_host_rpm"])
    write_lock = threading.Lock()
    audit = AuditLog(out_dir / "audit.log")
    counters = {"hosts_ok": 0, "hosts_err": 0, "docs": 0}

    def work(host: str) -> None:
        try:
            recs = wayback_docs(host, limiter=limiter, mimetype="application/pdf",
                                max_pages=wb["max_pages"], collapse=wb["collapse"],
                                tries=wb["tries"], timeout=wb["timeout_s"])
        except Exception as exc:  # noqa: BLE001 — record & continue; host retried next run
            audit.write(f"ERR\t{host}\t{exc}")
            counters["hosts_err"] += 1
            return
        with write_lock:
            if recs:
                append_jsonl(docs_path, recs)
            with done_path.open("a", encoding="utf-8") as fh:
                fh.write(host + "\n")
            counters["hosts_ok"] += 1
            counters["docs"] += len(recs)
        audit.write(f"OK\t{host}\t{len(recs)} docs")
        print(f"  [OK] {host:<38} {len(recs):>5} pdfs")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(work, h) for h in hosts]
        for _ in as_completed(futs):
            pass
    audit.close()

    print(f"\n[done] hosts ok={counters['hosts_ok']} err={counters['hosts_err']} "
          f"docs={counters['docs']} -> {docs_path}")
    return counters
