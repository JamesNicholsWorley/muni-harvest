"""Summary statistics for Select Board / City Council / Planning Board agendas & minutes,
on the consolidated corpus. SB/CC are split by the municipalstructure SQL (which towns
actually have each body); Planning Board is town-universal (all 351). Reports town-level
coverage AND meeting-level agenda<->minutes completion per board."""
from __future__ import annotations
import json, re, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.docclass import classify_document
from muni_harvest.discover.agendacenter_recover import load_recovered

SQL = Path(r"C:\Users\Owner\Downloads\election_results (3).sql")
NODES = Path(__file__).resolve().parents[1] / "data" / "discover" / "nodes.jsonl"

def norm(s): return re.sub(r"[^a-z]", "", s.lower())

# --- town -> governing body from municipalstructure ---
txt = SQL.read_text(encoding="utf-8", errors="replace")
def grab(table):
    m = re.search(r"INSERT INTO `%s`[^;]*?VALUES\s*(.*?);" % table, txt, re.S)
    return m.group(1) if m else ""
town_name = {int(i): n for i, n in re.findall(r"\((\d+),\s*'((?:[^'\\]|\\.)*)'\)", grab("towns"))}
body_of = {int(i): b for i, b in re.findall(r"\((\d+),\s*'(Select Board|City Council)'", grab("municipalstructure"))}
town_body = {norm(town_name[i]): b for i, b in body_of.items() if i in town_name}
SB = {t for t, b in town_body.items() if b == "Select Board"}
CC = {t for t, b in town_body.items() if b == "City Council"}
ALL = set(town_body)  # all 351

ac_map = load_recovered()

# --- classify corpus; track per-board per-town doctypes + meeting-level linkage ---
BODIES = {"select_board": "Select Board", "city_council": "City / Town Council",
          "planning_board": "Planning Board"}
town_has = {b: {"agenda": set(), "minutes": set()} for b in BODIES}   # board -> doctype -> {town}
# meeting-level: per board, agenda/minutes keys (AgendaCenter meeting-id or freeform board+date)
mtg_ag = {b: defaultdict(set) for b in BODIES}   # board -> town -> {key}
mtg_mn = {b: defaultdict(set) for b in BODIES}
seen_towns = set()

for line in NODES.open(encoding="utf-8"):
    try: r = json.loads(line)
    except Exception: continue
    if r.get("kind") != "file": continue
    town = r.get("municipality") or ""
    if not town: continue
    nn = norm(town); seen_towns.add(nn)
    c = classify_document(r["url"], r.get("anchor", ""))
    dt, bd = c["doctype"], c["board"]
    if not bd and c["agendacenter"] and c["meeting_id"] and town:
        bd = ac_map.get((town, c["meeting_id"]), "")
    if bd not in BODIES or dt not in ("agenda", "minutes"): continue
    town_has[bd][dt].add(nn)
    if c["agendacenter"] and c["meeting_id"]:
        key = ("ac", c["meeting_id"])
    elif c["date"]:
        key = ("ff", c["date"])
    else:
        continue
    (mtg_ag if dt == "agenda" else mtg_mn)[bd][nn].add(key)

def report(board_key, universe, label, universe_label):
    a = town_has[board_key]["agenda"] & universe
    m = town_has[board_key]["minutes"] & universe
    both = a & m
    incorp = universe & seen_towns
    # meeting-level completion across this board's towns
    tot_a = tot_both = 0
    for t in universe:
        A, M = mtg_ag[board_key][t], mtg_mn[board_key][t]
        tot_a += len(A); tot_both += len(A & M)
    print(f"\n=== {label}  ({len(universe)} {universe_label}) ===")
    print(f"  towns in corpus:                {len(incorp):>4} ({len(incorp)/len(universe):.0%})")
    print(f"  towns w/ agendas:               {len(a):>4} ({len(a)/len(universe):.0%})")
    print(f"  towns w/ minutes:               {len(m):>4} ({len(m)/len(universe):.0%})")
    print(f"  towns w/ BOTH:                  {len(both):>4} ({len(both)/len(universe):.0%})")
    if tot_a:
        print(f"  meetings with an agenda:        {tot_a:>7,}")
        print(f"  of those, minutes also present: {tot_both:>7,} ({tot_both/tot_a:.0%})")

print(f"corpus towns tagged: {len(seen_towns)}/351")
report("select_board", SB, "SELECT BOARD", "Select-Board towns")
report("city_council", CC, "CITY / TOWN COUNCIL", "City-Council towns")
report("planning_board", ALL, "PLANNING BOARD", "towns (all have one)")
