"""Body-split coverage: for towns WITH a Select Board vs City Council (per the
municipalstructure SQL table), do we actually have that body's agendas AND minutes?

Unlike coverage.py (which counts board=X across all 351 towns regardless of whether
that town HAS board X), this intersects the corpus with each town's real governing body.
"""
from __future__ import annotations
import re, sys, json
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.docclass import classify_document
from muni_harvest.discover.agendacenter_recover import load_recovered

SQL = Path(r"C:\Users\Owner\Downloads\election_results (3).sql")
NODES = Path(__file__).resolve().parents[1] / "data" / "discover" / "nodes.jsonl"

def norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())

# --- parse SQL: towns (id->name) and municipalstructure (id->body) ---
txt = SQL.read_text(encoding="utf-8", errors="replace")

def grab_insert(table: str) -> str:
    m = re.search(r"INSERT INTO `%s`[^;]*?VALUES\s*(.*?);" % re.escape(table), txt, re.S)
    return m.group(1) if m else ""

town_name = {}
for tid, name in re.findall(r"\((\d+),\s*'((?:[^'\\]|\\.)*)'\)", grab_insert("towns")):
    town_name[int(tid)] = name.replace("\\'", "'")

body_of = {}
for tid, body in re.findall(r"\((\d+),\s*'(Select Board|City Council)'", grab_insert("municipalstructure")):
    body_of[int(tid)] = body

# town name -> body
town_body = {}
for tid, body in body_of.items():
    if tid in town_name:
        town_body[norm(town_name[tid])] = body

n_sb = sum(1 for b in town_body.values() if b == "Select Board")
n_cc = sum(1 for b in town_body.values() if b == "City Council")
print(f"municipalstructure: {len(town_body)} towns  |  Select Board={n_sb}  City Council={n_cc}")

# --- load AgendaCenter recovered board map (town, meeting_id)->board ---
ac_map = load_recovered()
print(f"AgendaCenter recovered board mappings: {len(ac_map)}")

# --- scan corpus ---
# per town: sets of doctypes present for the town's OWN body
BODY_KEY = {"Select Board": "select_board", "City Council": "city_council"}

# For each town, track: does it have agenda / minutes attributable to its governing body?
has_ag = defaultdict(bool)    # normname -> bool  (own-body agenda)
has_min = defaultdict(bool)
cnt_ag = Counter()            # own-body agenda doc count
cnt_min = Counter()
# also track ANY agenda/minutes (any board incl unknown) so we can see corpus presence
any_ag = defaultdict(bool)
any_min = defaultdict(bool)
towns_seen = set()
n = 0
for line in NODES.open(encoding="utf-8"):
    n += 1
    try:
        rec = json.loads(line)
    except Exception:
        continue
    if rec.get("kind") != "file":
        continue
    town = rec.get("municipality") or ""
    if not town:
        continue
    nn = norm(town)
    towns_seen.add(nn)
    body = town_body.get(nn)
    if not body:
        continue
    want = BODY_KEY[body]
    c = classify_document(rec["url"], rec.get("anchor", ""))
    dt, bd = c["doctype"], c["board"]
    if not bd and c["agendacenter"] and c["meeting_id"]:
        bd = ac_map.get((town, c["meeting_id"]), "")
    if dt == "agenda":
        any_ag[nn] = True
        if bd == want:
            has_ag[nn] = True; cnt_ag[nn] += 1
    elif dt == "minutes":
        any_min[nn] = True
        if bd == want:
            has_min[nn] = True; cnt_min[nn] += 1

print(f"scanned {n:,} lines; towns with any municipality tag in corpus: {len(towns_seen)}")

# --- aggregate per body ---
def report(body):
    towns = [nn for nn, b in town_body.items() if b == body]
    incorpus = [t for t in towns if t in towns_seen]
    ag = [t for t in towns if has_ag[t]]
    mn = [t for t in towns if has_min[t]]
    both = [t for t in towns if has_ag[t] and has_min[t]]
    anyag = [t for t in towns if any_ag[t]]
    anymin = [t for t in towns if any_min[t]]
    print(f"\n=== {body} ({len(towns)} towns) ===")
    print(f"  in corpus (any file w/ muni tag):     {len(incorpus)}")
    print(f"  OWN-BODY agendas present:             {len(ag)}")
    print(f"  OWN-BODY minutes present:             {len(mn)}")
    print(f"  OWN-BODY both agendas+minutes:        {len(both)}")
    print(f"  ANY-board agendas present:            {len(anyag)}")
    print(f"  ANY-board minutes present:            {len(anymin)}")
    missing_body_ag = [t for t in incorpus if not has_ag[t]]
    return {
        "body": body, "towns": towns, "incorpus": incorpus,
        "own_ag": ag, "own_min": mn, "own_both": both,
        "missing_own_ag": [t for t in incorpus if not has_ag[t]],
        "missing_own_min": [t for t in incorpus if not has_min[t]],
        "have_ag_missing_min": [t for t in ag if not has_min[t]],
    }

res = {b: report(b) for b in ("Select Board", "City Council")}

# dump per-town detail
out = Path(__file__).resolve().parent / "body_coverage_detail.csv"
with out.open("w", encoding="utf-8") as f:
    f.write("town,body,in_corpus,own_agenda,own_minutes,any_agenda,any_minutes,n_own_ag,n_own_min\n")
    id2name = {norm(v): v for v in town_name.values()}
    for nn, body in sorted(town_body.items()):
        f.write(f"{id2name.get(nn,nn)},{body},{nn in towns_seen},{has_ag[nn]},{has_min[nn]},"
                f"{any_ag[nn]},{any_min[nn]},{cnt_ag[nn]},{cnt_min[nn]}\n")
print(f"\nwrote {out}")

# save summary json
summ = {b: {k: (len(v) if isinstance(v, list) else v) for k, v in r.items() if k != "towns"}
        for b, r in res.items()}
# keep the missing lists (names) for follow-up
id2name = {norm(v): v for v in town_name.values()}
summ["_have_ag_missing_min_select"] = sorted(id2name.get(t, t) for t in res["Select Board"]["have_ag_missing_min"])
summ["_have_ag_missing_min_council"] = sorted(id2name.get(t, t) for t in res["City Council"]["have_ag_missing_min"])
summ["_missing_own_ag_select"] = sorted(id2name.get(t, t) for t in res["Select Board"]["missing_own_ag"])
(Path(__file__).resolve().parent / "body_coverage_summary.json").write_text(
    json.dumps(summ, indent=2), encoding="utf-8")
print("wrote body_coverage_summary.json")
