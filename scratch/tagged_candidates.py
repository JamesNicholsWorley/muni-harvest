"""Cleaner handoff: for the CivicAtlas-missing town-years, emit recovered election-doc
candidates with (a) obvious non-election 'results' noise pre-dropped and (b) an
election-TYPE tag (municipal / state_federal / primary / special / town_meeting) so the
verifier filters by type instead of hand-classifying. Mirrors the other agent's 25/57 split."""
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
    if w: host2town[norm_host(re.sub(r"^https?://","",w).strip("/").split("/")[0])] = r["Municipality"]
for h, t in {"pelhamma.gov":"Pelham","townofpetersham.gov":"Petersham","pittsfieldma.gov":"Pittsfield",
             "norwoodma.gov":"Norwood","weymouth.ma.us":"Weymouth","northandoverma.gov":"North Andover",
             "wbrookfield.com":"West Brookfield","townofsavoy.com":"Savoy","goshen-ma.us":"Goshen",
             "gosnold-ma.gov":"Gosnold","harwich-ma.gov":"Harwich","townofsouthampton.org":"Southampton",
             "townofwestspringfield.org":"West Springfield"}.items():
    host2town[h] = t

rows = list(csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv", encoding="utf-8")))
missing = {(norm(r["municipality"]), r["year"]): r["municipality"]
           for r in rows if r.get("status","") in {"missing","resource_exhausted"} and r.get("expected") != "no"}
mtowns = {t for t,_ in missing}

RESULTS = re.compile(r"result|canvass|precinct|tally|votes?[-_ ]?cast", re.I)
NOISE = re.compile(r"water|lead|copper|pfas|coli|bacteria|consumer.?confidence|quality|survey|monitor|"
                   r"sports?|miaa|athletic|lottery|raffle|\bbid\b|grant|budget|annual.?report|bacterial", re.I)
def etype(hay):
    h = hay.lower()
    if re.search(r"presidential|state.?(primary|election)|congress|senat|governor|u\.?s\.?", h): return "state_federal"
    if re.search(r"\bprimary\b", h): return "primary"
    if re.search(r"special.?(town.?)?election", h): return "special"
    if re.search(r"town.?meeting", h): return "town_meeting"
    if re.search(r"annual|town.?election|local.?election|municipal|\bate\b|selectman", h): return "municipal"
    return "election_unspecified"

cand = defaultdict(list)
for line in (Path(__file__).resolve().parents[1]/"data/discover/nodes.jsonl").open(encoding="utf-8"):
    if "esult" not in line and "anvass" not in line and "ally" not in line: continue
    try: r = json.loads(line)
    except Exception: continue
    if r.get("kind") != "file": continue
    t = norm(r.get("municipality") or "") or norm(host2town.get(norm_host(r.get("seed_host","")), ""))
    if t not in mtowns: continue
    hay = r["url"] + " " + (r.get("anchor") or "")
    if not RESULTS.search(hay) or NOISE.search(hay): continue
    for y in set(re.findall(r"(20[12]\d)", hay)):
        if (t, y) in missing:
            cand[(t, y)].append((etype(hay), r["url"], (r.get("anchor") or "")[:70]))

out = Path(__file__).resolve().parent / "recovered_candidates_tagged.csv"
from collections import Counter
tc = Counter()
with out.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(["municipality","year","election_type","url","title"])
    for (t,y),v in sorted(cand.items()):
        best = sorted(v, key=lambda x: {"municipal":0,"election_unspecified":1,"special":2,"primary":3,"town_meeting":4,"state_federal":5}[x[0]])[0]
        tc[best[0]] += 1
        w.writerow([host2town.get(next((h for h in host2town if norm(host2town[h])==t), ""), t.title()), y, best[0], best[1], best[2]])
print(f"CivicAtlas-missing town-years with a noise-filtered results candidate: {len(cand)}")
print("by best election_type:", dict(tc))
muni = tc.get("municipal",0) + tc.get("election_unspecified",0)
print(f"  likely MUNICIPAL (municipal + unspecified): {muni}")
print(f"  non-municipal (state/primary/special/TM): {sum(tc.values())-muni}")
print(f"wrote {out.name}")
