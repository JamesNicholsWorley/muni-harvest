"""Re-count recovered/missing using a TIGHT 'genuine municipal election results' filter,
matching the other agent's verification bar. Excludes the noise categories they flagged:
water-quality/lead/copper/PFAS/survey/sports/monitoring 'results', state/federal elections,
and primaries/special/town-meeting (keep annual/local town election results)."""
import csv, json, re
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host

def norm(s): return re.sub(r"[^a-z]", "", s.lower())
host2town = {}
for r in csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv", encoding="utf-8")):
    w = (r["Website"] or "").strip().lower()
    if w:
        host2town[norm_host(re.sub(r"^https?://", "", w).strip("/").split("/")[0])] = norm(r["Municipality"])
for h, t in {"goshen-ma.us":"Goshen","gosnold-ma.gov":"Gosnold","harwich-ma.gov":"Harwich",
             "northandoverma.gov":"North Andover","norwoodma.gov":"Norwood","pelhamma.gov":"Pelham",
             "townofpetersham.gov":"Petersham","pittsfieldma.gov":"Pittsfield","townofsavoy.com":"Savoy",
             "townofsouthampton.org":"Southampton","wbrookfield.com":"West Brookfield",
             "townofwestspringfield.org":"West Springfield","weymouth.ma.us":"Weymouth"}.items():
    host2town[h] = norm(t)

# tight filters
RESULTS = re.compile(r"result|canvass|precinct|tally|votes?[-_ ]?cast|official.{0,15}count", re.I)
ELECTION = re.compile(r"town.?election|local.?election|annual.?(town.?)?election|municipal.?election|\bate\b|selectman|select.?board.?election", re.I)
# noise: non-election "results" + non-municipal election types
NOISE = re.compile(r"water|lead|copper|pfas|coli|bacteria|consumer.?confidence|quality|"
                   r"survey|monitor|sports?|miaa|athletic|lottery|raffle|"           # non-election "results"
                   r"presidential|state.?(primary|election)|congress|senat|governor|"  # state/federal
                   r"specimen|sample.?ballot|ballot.?question|primary|special.?election|"
                   r"town.?meeting|warrant|budget|annual.?report|finance|calendar|deadline|"
                   r"absentee|nomination|voter.?reg", re.I)

def is_muni_result(hay):
    if NOISE.search(hay): return False
    if not RESULTS.search(hay): return False
    # require an election context word (avoid "bid results", "grant results")
    return bool(ELECTION.search(hay) or re.search(r"election", hay, re.I))

rows = list(csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv", encoding="utf-8")))
expected = {}; ca_have = set()
for r in rows:
    if r.get("expected") == "no": continue
    y = r["year"].strip()
    if not y: continue
    expected[(norm(r["municipality"]), y)] = r
    if r.get("has_pdf") == "yes": ca_have.add((norm(r["municipality"]), y))

corpus_have = set()
for line in (Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl").open(encoding="utf-8"):
    if "esult" not in line and "anvass" not in line and "ally" not in line: continue
    try: r = json.loads(line)
    except Exception: continue
    if r.get("kind") != "file": continue
    t = norm(r.get("municipality") or "") or host2town.get(norm_host(r.get("seed_host","")), "")
    if not t: continue
    hay = r["url"] + " " + (r.get("anchor") or "")
    if not is_muni_result(hay): continue
    for y in set(re.findall(r"(20[12]\d)", hay)):
        corpus_have.add((t, y))

covered = ca_have | (corpus_have & set(expected))
missing = sorted(set(expected) - covered)
print("=== TIGHT genuine-municipal-results filter ===")
print(f"expected: {len(expected)} | CivicAtlas pdf: {len(ca_have)} | "
      f"corpus genuine-muni result: {len(corpus_have & set(expected))}")
print(f"covered (union): {len(covered)} | STILL MISSING: {len(missing)}  ({len(missing)/len(expected):.0%})")
print(f"   [loose filter had: corpus 1006, missing 401]")
