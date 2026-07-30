"""Feasibility: can the scraper capture HTML/other result pages? Quantify how many
still-missing town-years have an election-related PAGE (kind=page) already captured in the
corpus, and how many of the 106 no-file-candidate cases have a page node."""
import csv, json, re
from collections import defaultdict, Counter
from pathlib import Path

def norm(s): return re.sub(r"[^a-z]", "", s.lower())
missing = {}
for r in csv.DictReader(open(Path(__file__).resolve().parent / "still_missing_final.csv", encoding="utf-8")):
    missing[(norm(r["municipality"]), r["year"])] = r
miss_towns = {t for t, _ in missing}

# from nonobvious.py we know which have a FILE candidate; recompute quickly for split
FILE_ELECT = re.compile(r"result|canvass|precinct|tally|annual.?report|town.?report|minutes|"
                        r"town.?meeting|clerk|election|voting", re.I)
has_file_cand = set()
# page nodes: election-related pages per missing town (any year, since pages rarely carry year)
page_by_town = defaultdict(list)     # town -> [page urls]
page_ty = defaultdict(list)          # (town,year) -> [page urls]
PELECT = re.compile(r"election|/elections?/|voting|town.?clerk|/results?/|canvass", re.I)
NODES = Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl"
for line in NODES.open(encoding="utf-8"):
    try: r = json.loads(line)
    except Exception: continue
    t = norm(r.get("municipality") or "")
    if t not in miss_towns: continue
    hay = r["url"] + " " + (r.get("anchor") or "")
    if r.get("kind") == "file":
        if FILE_ELECT.search(hay):
            for y in set(re.findall(r"(20[12]\d)", hay)):
                if (t, y) in missing: has_file_cand.add((t, y))
    else:  # page
        if PELECT.search(hay):
            page_by_town[t].append(r["url"])
            for y in set(re.findall(r"(20[12]\d)", hay)):
                if (t, y) in missing: page_ty[(t, y)].append(r["url"])

no_file = [k for k in missing if k not in has_file_cand]
# of the no-file cases, how many have an election PAGE for the town (HTML-results candidate)
page_town_cover = [k for k in no_file if page_by_town.get(k[0])]
page_ty_cover = [k for k in no_file if page_ty.get(k)]
print(f"still-missing: {len(missing)}")
print(f"  no FILE candidate (from #14): {len(no_file)}")
print(f"    of those, town HAS an election/clerk PAGE captured: {len(page_town_cover)} "
      f"({len(page_town_cover)/max(len(no_file),1):.0%})")
print(f"    of those, a page with the YEAR captured:            {len(page_ty_cover)}")
truly_dark = [k for k in no_file if not page_by_town.get(k[0])]
print(f"  NO file AND NO election page (truly dark): {len(truly_dark)}")
id2 = {norm(r['municipality']): r['municipality'] for r in missing.values()}
print("   sample truly-dark town-years:", [f"{id2[t]} {y}" for t,y in truly_dark][:12])

# overall page-node stats: does docsweep/crawl capture pages at all?
kinds = Counter()
for line in NODES.open(encoding="utf-8"):
    try: r = json.loads(line)
    except Exception: continue
    kinds[r.get("kind","?")] += 1
print(f"\ncorpus node kinds: {dict(kinds)}")
