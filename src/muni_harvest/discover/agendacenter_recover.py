"""AgendaCenter board recovery — attribute the ~217K 'unknown board' agenda/minutes.

AgendaCenter puts the board only in the link text (empty in our Wayback data), but the
LIVE /AgendaCenter page maps each meeting to its board via the category legend
(`<input ... value="{CID}"> {Board Name}`) + `id="cat{CID}"` listing sections. We
fetch each AgendaCenter town's live page and emit (town, meeting_id, board) so
coverage can fill in the board for meeting-ids that still exist in the current view.

Recovers the CURRENT view (recent meetings). Deep history would need year-param
fetches — noted as future work. Resumable; polite (shared RateLimiter).
"""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import data_dir, resolve_path, load_settings
from ..core import RateLimiter, append_jsonl, fetch, iter_jsonl
from .docclass import _match_board
from .pipeline import host_to_municipality

_CID_LABEL = re.compile(r'name="chkCategoryID"\s+value="(\d+)"[^>]*>\s*([^<]{3,60})')
_WALK = re.compile(r'id="cat(\d+)"|/AgendaCenter/ViewFile/(?:Agenda|Minutes)/_\d{8}-(\d+)')


def recover_boards(host: str, *, limiter=None, timeout: int = 30) -> dict[str, str]:
    """meeting_id -> board_key for `host` (empty dict if not an AgendaCenter site)."""
    if limiter:
        limiter.wait()
    try:
        html = fetch(f"https://{host}/AgendaCenter", tries=2, timeout=timeout).decode(
            "utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {}
    if "catAgendaRow" not in html and "ViewFile" not in html:
        return {}
    cid_board = {cid: _match_board(re.sub(r"\s+", " ", lbl))
                 for cid, lbl in _CID_LABEL.findall(html)}
    out: dict[str, str] = {}
    cur = None
    for m in _WALK.finditer(html):
        if m.group(1):
            cur = m.group(1)
        elif m.group(2) and cur:
            out.setdefault(m.group(2), cid_board.get(cur, ""))
    return {mid: b for mid, b in out.items() if b}


def _agendacenter_hosts() -> dict[str, str]:
    """seed_host -> municipality for hosts that have AgendaCenter docs in the corpus."""
    hosts: dict[str, str] = {}
    for n in iter_jsonl(data_dir() / "discover" / "nodes.jsonl"):
        if "/AgendaCenter/ViewFile/" in n.get("url", ""):
            hosts.setdefault(n["seed_host"], n.get("municipality", ""))
    return hosts


def run(*, workers: int = 8) -> dict:
    out_dir = data_dir() / "discover"
    out_path = out_dir / "ac_boards.jsonl"
    done_path = out_dir / "ac_boards_done.txt"
    done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()

    hosts = _agendacenter_hosts()
    todo = [(h, m) for h, m in hosts.items() if h not in done]
    print(f"[*] AgendaCenter board recovery: {len(todo)} towns ({len(done)} done)")
    if not todo:
        return {"towns": 0}

    limiter = RateLimiter(load_settings()["wayback"]["per_host_rpm"])
    lock = threading.Lock()
    totals = {"towns": 0, "mappings": 0}

    def work(item):
        host, muni = item
        mid_board = recover_boards(host, limiter=limiter)
        rows = [{"municipality": muni, "seed_host": host, "meeting_id": mid,
                 "board": b} for mid, b in mid_board.items()]
        with lock:
            if rows:
                append_jsonl(out_path, rows)
            with done_path.open("a", encoding="utf-8") as fh:
                fh.write(host + "\n")
            totals["towns"] += 1
            totals["mappings"] += len(rows)
        if rows:
            print(f"  [OK] {host:<34} {len(rows)} meeting->board")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for _ in as_completed([ex.submit(work, it) for it in todo]):
            pass
    print(f"\n[done] {totals['towns']} towns, {totals['mappings']} meeting->board "
          f"mappings -> {out_path}")
    return totals


def load_recovered() -> dict[tuple, str]:
    """(municipality, meeting_id) -> board_key, for coverage to fill AgendaCenter gaps."""
    m: dict[tuple, str] = {}
    for r in iter_jsonl(data_dir() / "discover" / "ac_boards.jsonl"):
        m[(r["municipality"], r["meeting_id"])] = r["board"]
    return m
