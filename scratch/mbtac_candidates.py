"""Stage 1 (candidate assembly) for the MBTA Communities Act 3A vote finder.

Streams the corpus (data/discover/nodes.jsonl) and selects, for each of the 175
MBTA-Communities towns, the minutes / warrant / report container docs that could hold
a 3A zoning vote, plus any dedicated "MBTA Communities" HTML pages. Classifies with
classify_document; fills AgendaCenter unknown-board docs from ac_boards.jsonl.

Filters:
  town      in the 175 MBTA-C towns (config/mbtac_towns.csv)
  doctype   in {minutes, warrant, report, decision}  (report/decision low priority)
  board     in {planning_board, select_board, city_council, town_meeting}  OR the
            doc URL/anchor carries an explicit MBTA/3A topic hint (topic-first pages)
  year      >= 2022 or unknown (3A votes are 2022-2025; nodes carry no fetch timestamp)

Priority (lower = try first): town_meeting 1, city_council 2, planning_board 3,
select_board 4, other-board-but-topic-hint 5, report/decision 6.

Output: scratch/mbtac_candidates.csv (town, town_norm, community_type, priority,
board, doctype, year, kind, url, anchor). ASCII-only, explicit UTF-8 I/O.
"""
import csv
import json
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
from muni_harvest.discover.model import norm_host
from muni_harvest.discover.docclass import classify_document

NODES = ROOT / "data" / "discover" / "nodes.jsonl"
# Any live-sweep output (local browser sweep + Actions docsweep gap-fill).
LIVE_GLOB = sorted((ROOT / "data" / "discover").glob("nodes_mbtac_*.jsonl"))
ACB = ROOT / "data" / "discover" / "ac_boards.jsonl"
TOWNS = ROOT / "config" / "mbtac_towns.csv"
TOWNS_WEB = Path(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv")
OUT = HERE / "mbtac_candidates.csv"

WANT_BOARDS = {"planning_board", "select_board", "city_council", "town_meeting"}
WANT_DOCTYPES = {"minutes", "warrant", "report", "decision"}
PRIORITY = {"town_meeting": 1, "city_council": 2, "planning_board": 3, "select_board": 4}

# Topic hint in the URL/anchor itself (dedicated 3A pages / files).
TOPIC = re.compile(r"mbta[ _-]?communit|section[ _-]?3a|(?<![\w])40a[ _-]?3a|"
                   r"\b3a[ _-]?(district|zoning|overlay)|multi[ _-]?family[ _-]?(overlay|zoning|district)",
                   re.I)


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def load_target_towns():
    meta = {}
    for r in csv.DictReader(TOWNS.open(encoding="utf-8")):
        meta[r["town_norm"]] = r
    return meta


def load_host2town():
    h2t = {}
    if TOWNS_WEB.exists():
        for r in csv.DictReader(TOWNS_WEB.open(encoding="utf-8")):
            w = (r.get("Website") or "").strip().lower()
            if w:
                host = norm_host(re.sub(r"^https?://", "", w).strip("/").split("/")[0])
                h2t[host] = norm(r["Municipality"])
    return h2t


def load_ac_boards():
    m = {}
    if ACB.exists():
        for line in ACB.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            m[(norm(r.get("municipality", "")), str(r.get("meeting_id", "")))] = r.get("board", "")
    return m


def iter_nodes():
    for src in [NODES, *LIVE_GLOB]:
        if not src.exists():
            continue
        for line in src.open(encoding="utf-8"):
            try:
                yield json.loads(line)
            except Exception:
                continue


def main():
    targets = load_target_towns()
    h2t = load_host2town()
    acb = load_ac_boards()
    target_norms = set(targets)

    cand = defaultdict(dict)   # town_norm -> {urlkey: rowtuple}  (dedup by urlkey)
    stats = Counter()

    for r in iter_nodes():
        t = norm(r.get("municipality") or "")
        if t not in target_norms:
            t = h2t.get(norm_host(r.get("seed_host", "")), "")
        if t not in target_norms:
            continue

        url = r.get("url", "")
        anchor = r.get("anchor") or ""
        c = classify_document(url, anchor)
        board, doctype, year = c["board"], c["doctype"], c["year"]

        # AgendaCenter board fill.
        if not board and c.get("agendacenter") and c.get("meeting_id"):
            board = acb.get((t, str(c["meeting_id"])), "")

        topic_hint = bool(TOPIC.search(url + " " + anchor))

        # Keep rule: a wanted doctype on a wanted board, OR any doc/page with a topic hint.
        board_ok = board in WANT_BOARDS
        doc_ok = doctype in WANT_DOCTYPES
        if not ((board_ok and doc_ok) or topic_hint):
            continue

        # Recency filter (votes are 2022-2025); keep unknown-year (no date in URL).
        if year and year.isdigit() and int(year) < 2022:
            continue

        if topic_hint and not (board_ok and doc_ok):
            pri = 5            # dedicated topic page / off-board topic file
        elif doctype in ("report", "decision"):
            pri = 6
        else:
            pri = PRIORITY.get(board, 5)

        key = r.get("urlkey") or url
        prev = cand[t].get(key)
        if prev is None or pri < prev[0]:
            cand[t][key] = (pri, board, doctype, year, r.get("kind", ""), url, anchor[:80], topic_hint)
        stats[doctype] += 1

    # Write, sorted by town then priority.
    rows_out = 0
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["town", "town_norm", "community_type", "priority", "board",
                    "doctype", "year", "kind", "topic_hint", "url", "anchor"])
        for tn in sorted(cand):
            meta = targets[tn]
            for (pri, board, doctype, year, kind, url, anchor, hint) in sorted(cand[tn].values()):
                w.writerow([meta["town"], tn, meta["community_type"], pri, board,
                            doctype, year, kind, int(bool(hint)), url, anchor])
                rows_out += 1

    towns_with = len(cand)
    topic_pages = sum(1 for tn in cand for v in cand[tn].values() if v[7])
    print(f"wrote {OUT.name}: {rows_out} candidate docs across {towns_with}/175 towns")
    print(f"  towns with >=1 candidate: {towns_with}  (missing: {175 - towns_with})")
    print(f"  topic-hint candidates (dedicated 3A pages/files): {topic_pages}")
    print(f"  kept-doc doctype mix: {dict(stats)}")
    missing = sorted(set(targets) - set(cand))
    if missing:
        print(f"  NO-CANDIDATE towns ({len(missing)}): "
              + ", ".join(targets[m]["town"] for m in missing[:40])
              + (" ..." if len(missing) > 40 else ""))


if __name__ == "__main__":
    main()
