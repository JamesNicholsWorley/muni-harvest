"""For the missing election town-years, loose-match the consolidated corpus: any file
from that town whose URL/anchor mentions election/results/canvass AND the year. Reveals
docs we actually HAVE but groundtruth didn't credit (strict doctype/year-in-URL)."""
from __future__ import annotations
import json, re, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

NODES = Path(__file__).resolve().parents[1] / "data" / "discover" / "nodes.jsonl"
def norm(s): return re.sub(r"[^a-z]", "", s.lower())

miss = [(r["municipality"], r["year"]) for r in
        (json.loads(l) for l in open(Path(__file__).resolve().parents[1]/"data/discover/groundtruth.jsonl", encoding="utf-8"))
        if not r["found"] and r["year"] < "2025"]
miss_by_town = defaultdict(set)
for m, y in miss:
    miss_by_town[norm(m)].add(y)

ELECT = re.compile(r"election|canvass|result|precinct|tally|ballot|town.?clerk", re.I)
# candidate docs per (town,year)
cand = defaultdict(list)
for line in NODES.open(encoding="utf-8"):
    if not ELECT.search(line):   # fast prefilter
        continue
    try: r = json.loads(line)
    except Exception: continue
    if r.get("kind") != "file": continue
    town = norm(r.get("municipality") or "")
    if town not in miss_by_town: continue
    hay = r["url"] + " " + (r.get("anchor") or "")
    if not ELECT.search(hay): continue
    yrs = set(re.findall(r"(20[12]\d)", hay))
    for y in (yrs & miss_by_town[town]):
        cand[(town, y)].append((r["url"], r.get("anchor", "")[:60]))

have = sorted(cand)
print(f"missing older town-years: {len(miss)}")
print(f"of those, a plausible election doc IS in the corpus for: {len(have)}\n")
for (town, y) in have[:25]:
    u, a = cand[(town, y)][0]
    print(f"  {town} {y}: {a or u[:70]}")
    print(f"       {u[:95]}")
# the genuinely-absent set (no candidate anywhere in corpus)
absent = sorted(set(miss) - {(t, y) for (t, y) in [(tt, yy) for tt, yy in [(norm(m), y) for m, y in miss]]} )  # placeholder
truly = [(m, y) for m, y in miss if (norm(m), y) not in cand]
print(f"\nno corpus candidate at all (web-hunt targets): {len(truly)}")
for m, y in truly[:20]: print(f"   {m} {y}")
