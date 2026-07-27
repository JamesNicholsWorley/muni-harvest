"""Deterministic AgendaCenter minutes recovery.

In AgendaCenter, a meeting's agenda and minutes share the same date+meeting-id:
  /AgendaCenter/ViewFile/Agenda/_MMDDYYYY-{id}
  /AgendaCenter/ViewFile/Minutes/_MMDDYYYY-{id}
Wayback frequently snapshotted the Agenda ViewFile but not the Minutes ViewFile of the
same meeting, so the corpus has ~2x more agendas than minutes even though the town
publishes both. Because the Minutes URL is fully determined by the agenda's (date,id),
we can RECOVER the missing minutes with one GET per agenda-only meeting — no Wayback,
no browser, no guessing. A live probe of old meetings showed ~35% of "agenda-only"
meetings actually have a minutes file we can fetch this way.

Resumable (per-host done file) + shardable for GitHub Actions.
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

_AC = re.compile(r"/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{8})-(\d+)", re.I)
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _agenda_only_by_host() -> dict[str, dict]:
    """host -> {'muni': str, 'need': {meeting_id: (date, host_in_url)}}.
    `need` = agenda meeting-ids with NO minutes node in the corpus."""
    agendas: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    minutes: dict[str, set[str]] = defaultdict(set)
    muni: dict[str, str] = {}
    for n in iter_jsonl(data_dir() / "discover" / "nodes.jsonl"):
        u = n.get("url", "")
        if "/AgendaCenter/ViewFile/" not in u:
            continue
        m = _AC.search(u)
        if not m:
            continue
        host = n.get("seed_host") or re.sub(r"^https?://", "", u).split("/")[0]
        muni.setdefault(host, n.get("municipality", ""))
        typ, date, mid = m.group(1).lower(), m.group(2), m.group(3)
        # the real request host as it appears in the URL (may include www.)
        url_host = re.sub(r"^https?://", "", u).split("/")[0]
        if typ == "agenda":
            agendas[host].setdefault(mid, (date, url_host))
        else:
            minutes[host].add(mid)
    out: dict[str, dict] = {}
    for host, ag in agendas.items():
        need = {mid: dh for mid, dh in ag.items() if mid not in minutes[host]}
        if need:
            out[host] = {"muni": muni.get(host, ""), "need": need}
    return out


def _probe_minutes(url_host: str, date: str, mid: str, *, timeout: int = 20) -> bool:
    """GET the Minutes ViewFile; True iff it resolves to an actual file (PDF), not a 404
    HTML error page."""
    url = f"https://{url_host}/AgendaCenter/ViewFile/Minutes/_{date}-{mid}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "").lower()
            head = r.read(1024)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return False
    if "pdf" in ctype or head[:4] == b"%PDF":
        return True
    # some servers serve octet-stream / mislabel; accept non-HTML binary of real size
    return "html" not in ctype and len(head) >= 1024


def run(*, workers: int = 8, shard: str | None = None, limit: int | None = None) -> dict:
    work_map = _agenda_only_by_host()
    hosts = sorted(work_map)
    if shard:
        hosts = shard_hosts(hosts, shard)
    if limit:
        hosts = hosts[:limit]

    out_dir = data_dir() / "discover"
    out_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = out_dir / "nodes_minutes.jsonl"
    done_path = out_dir / "minutes_recover_done.txt"
    done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()
    todo = [h for h in hosts if h not in done]
    total_need = sum(len(work_map[h]["need"]) for h in todo)
    print(f"[*] minutes recovery: {len(todo)} hosts, {total_need:,} agenda-only meetings "
          f"to probe ({len(done)} hosts done); {workers} workers")

    limiter = RateLimiter(load_settings()["wayback"]["per_host_rpm"])
    lock = threading.Lock()
    totals = {"hosts": 0, "probed": 0, "recovered": 0}

    def work(host: str) -> None:
        info = work_map[host]
        muni = info["muni"]
        rows = []
        probed = 0
        for mid, (date, url_host) in info["need"].items():
            limiter.wait()
            probed += 1
            if _probe_minutes(url_host, date, mid):
                url = f"https://{url_host}/AgendaCenter/ViewFile/Minutes/_{date}-{mid}"
                rows.append({"seed_host": host, "municipality": muni, "url": url,
                             "urlkey": url.split("//", 1)[-1].lower(), "kind": "file",
                             "mimetype": "application/pdf", "doctype": "minutes",
                             "anchor": "", "depth": 1,
                             "parent_url": f"https://{url_host}/AgendaCenter",
                             "breadcrumb": "", "discovered_via": "minutes_recover",
                             "storage_host": ""})
        with lock:
            if rows:
                append_jsonl(nodes_path, rows)
            with done_path.open("a", encoding="utf-8") as fh:
                fh.write(host + "\n")
            totals["hosts"] += 1
            totals["probed"] += probed
            totals["recovered"] += len(rows)
        if rows:
            print(f"  [OK] {host:<32} recovered {len(rows):>4} / {probed:>4} probed "
                  f"({len(rows)/probed:.0%})")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for _ in as_completed([ex.submit(work, h) for h in todo]):
            pass
    print(f"\n[done] minutes recovery: {totals['recovered']:,} minutes recovered from "
          f"{totals['probed']:,} probes across {totals['hosts']} hosts -> {nodes_path}")
    return totals
