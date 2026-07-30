"""Stage 4 (coverage accounting + audit) for the MBTA Communities Act 3A vote finder.

Aggregates scratch/mbtac_screen.csv per town: best screen verdict, whether a BOARD-level
candidate (planning_board/select_board) and a LEGISLATIVE-level candidate
(town_meeting/city_council) reached CONFIRMED/PROBABLE. Compares against the 175-town
denominator (config/mbtac_towns.csv) and, if present, the EOHLC ground-truth
(config/mbtac_groundtruth.csv). Writes an audit ledger with an explicit REASON bucket for
every town lacking a confirmed vote-bearing doc -- never a silent exclusion -- and emits
scratch/mbtac_gap_towns.txt (town_norms with nothing CONFIRMED/PROBABLE) for the live sweep.

Usage: mbtac_coverage.py
ASCII-only, explicit UTF-8 I/O.
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
from muni_harvest.discover.model import norm_host

TOWNS = ROOT / "config" / "mbtac_towns.csv"
GROUND = ROOT / "config" / "mbtac_groundtruth.csv"   # optional
TOWNS_WEB = Path(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv")
BROWSER = ROOT / "config" / "browser_hosts.txt"      # WAF/browser-tier hosts (run locally)
SCREEN = HERE / "mbtac_screen.csv"
AUDIT = HERE / "mbtac_audit.csv"
GAP = HERE / "mbtac_gap_towns.txt"
GAP_HOSTS = ROOT / "config" / "mbtac_gap_hosts.txt"          # for docsweep-shard.yml (Actions)
GAP_HOSTS_LOCAL = ROOT / "config" / "mbtac_gap_hosts_local.txt"  # browser-tier -> run locally


def _n(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def load_gap_hosts(gap_norms):
    """Map gap town_norms -> current website host; split browser-tier out for local runs."""
    host_by_norm = {}
    if TOWNS_WEB.exists():
        for r in csv.DictReader(TOWNS_WEB.open(encoding="utf-8")):
            w = (r.get("Website") or "").strip().lower()
            if w:
                host_by_norm[_n(r["Municipality"])] = norm_host(
                    re.sub(r"^https?://", "", w).strip("/").split("/")[0])
    browser = set()
    if BROWSER.exists():
        browser = {norm_host(h.strip()) for h in BROWSER.read_text(encoding="utf-8").splitlines()
                   if h.strip() and not h.startswith("#")}
    shard, local, nohost = [], [], []
    for tn in gap_norms:
        h = host_by_norm.get(tn)
        if not h:
            nohost.append(tn)
        elif h in browser:
            local.append(h)
        else:
            shard.append(h)
    return shard, local, nohost

BOARD_LEVEL = {"planning_board", "select_board"}
LEG_LEVEL = {"town_meeting", "city_council"}
GOOD = {"CONFIRMED", "PROBABLE"}


def main():
    towns = {r["town_norm"]: r for r in csv.DictReader(TOWNS.open(encoding="utf-8"))}

    ground = {}
    if GROUND.exists():
        for r in csv.DictReader(GROUND.open(encoding="utf-8")):
            ground[r.get("town_norm") or r.get("town", "").lower()] = r

    # Aggregate screen rows per town.
    best = defaultdict(lambda: "NO_CANDIDATE")
    board_hit = defaultdict(bool)
    leg_hit = defaultdict(bool)
    seen = set()
    any_fetch = defaultdict(bool)
    fetch_fail_only = defaultdict(lambda: True)
    rank = {"NO_CANDIDATE": 0, "FETCH_FAIL": 1, "NO": 2, "TOPIC_ONLY": 3,
            "PROBABLE": 4, "CONFIRMED": 5}

    if SCREEN.exists():
        for r in csv.DictReader(SCREEN.open(encoding="utf-8")):
            tn = r["town_norm"]
            seen.add(tn)
            v = r["verdict"]
            any_fetch[tn] = True
            if v != "FETCH_FAIL":
                fetch_fail_only[tn] = False
            if rank.get(v, 0) > rank.get(best[tn], 0):
                best[tn] = v
            if v in GOOD:
                if r["board"] in BOARD_LEVEL:
                    board_hit[tn] = True
                if r["board"] in LEG_LEVEL:
                    leg_hit[tn] = True

    # Build audit ledger + gap list.
    rows = []
    gap = []
    n_confirmed = n_probable = n_board = n_leg = 0
    for tn, meta in sorted(towns.items()):
        b = best[tn]
        if b in GOOD:
            reason = ""
        elif b == "TOPIC_ONLY":
            reason = "topic_no_vote_signal"
        elif b == "NO":
            reason = "fetched_no_signal"
        elif b == "FETCH_FAIL" or (any_fetch[tn] and fetch_fail_only[tn]):
            reason = "fetch_blocked"
        else:
            reason = "no_candidate_in_corpus"

        if b not in GOOD:
            gap.append(tn)
        if b == "CONFIRMED":
            n_confirmed += 1
        if b == "PROBABLE":
            n_probable += 1
        if board_hit[tn]:
            n_board += 1
        if leg_hit[tn]:
            n_leg += 1

        g = ground.get(tn, {})
        rows.append({
            "town": meta["town"], "town_norm": tn,
            "community_type": meta["community_type"],
            "governing_body": meta["governing_body"],
            "best_verdict": b,
            "board_vote_found": int(board_hit[tn]),
            "legislative_vote_found": int(leg_hit[tn]),
            "reason_if_missing": reason,
            "eohlc_status": g.get("status", ""),
            "eohlc_adoption_date": g.get("adoption_date", ""),
        })

    with AUDIT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    GAP.write_text("\n".join(gap) + ("\n" if gap else ""), encoding="utf-8")

    # Gap-town host lists for the sharded live sweep (docsweep-shard.yml) + local browser tier.
    shard_hosts, local_hosts, nohost = load_gap_hosts(gap)
    GAP_HOSTS.write_text("\n".join(shard_hosts) + ("\n" if shard_hosts else ""), encoding="utf-8")
    GAP_HOSTS_LOCAL.write_text("\n".join(local_hosts) + ("\n" if local_hosts else ""), encoding="utf-8")

    N = len(towns)
    print(f"MBTA-C vote coverage over {N} towns:")
    print(f"  CONFIRMED vote-bearing doc: {n_confirmed}  ({n_confirmed/N:.0%})")
    print(f"  PROBABLE (topic+one signal): {n_probable}")
    print(f"  board-level vote found:      {n_board}")
    print(f"  legislative-level vote found:{n_leg}")
    print(f"  gap towns (need live sweep): {len(gap)} -> {GAP.name}")
    print(f"    -> {GAP_HOSTS.name}: {len(shard_hosts)} hosts for docsweep-shard.yml (Actions)")
    print(f"    -> {GAP_HOSTS_LOCAL.name}: {len(local_hosts)} browser-tier hosts (run locally)")
    if nohost:
        print(f"    -> {len(nohost)} gap towns have NO website in towns_websites.csv "
              f"(audit only): {', '.join(nohost[:15])}")
    # Reason breakdown for the gap.
    rb = defaultdict(int)
    for r in rows:
        if r["reason_if_missing"]:
            rb[r["reason_if_missing"]] += 1
    print(f"  reason buckets: {dict(rb)}")
    print(f"wrote {AUDIT.name}")


if __name__ == "__main__":
    main()
