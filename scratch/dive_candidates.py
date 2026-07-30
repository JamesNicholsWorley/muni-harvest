"""Build the content-dive candidate list: for each still-missing town-year, the container
documents/pages we already hold that most likely CONTAIN its election results, prioritized:
  1 annual TOWN report (year Y)   2 town-meeting/election minutes (Y)   3 election HTML page
  4 town-clerk/board minutes (Y)  5 any file w/ Y + election word
Output: dive_candidates.csv (town,year,priority,kind,url,title)."""
import csv, json, re
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host

def norm(s): return re.sub(r"[^a-z]", "", s.lower())
host2town = {}
for r in csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv", encoding="utf-8")):
    w=(r["Website"] or "").strip().lower()
    if w: host2town[norm_host(re.sub(r"^https?://","",w).strip("/").split("/")[0])]=norm(r["Municipality"])
for h,t in {"pelhamma.gov":"Pelham","townofpetersham.gov":"Petersham","pittsfieldma.gov":"Pittsfield",
            "norwoodma.gov":"Norwood","weymouth.ma.us":"Weymouth","northandoverma.gov":"North Andover",
            "wbrookfield.com":"West Brookfield","townofsavoy.com":"Savoy","goshen-ma.us":"Goshen",
            "gosnold-ma.gov":"Gosnold","harwich-ma.gov":"Harwich","townofsouthampton.org":"Southampton",
            "townofwestspringfield.org":"West Springfield"}.items():
    host2town[h]=norm(t)

# current missing set (loose): expected - CivicAtlas pdf - corpus results doc
rows=list(csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv",encoding="utf-8")))
expected={}; ca_have=set()
for r in rows:
    if r.get("expected")=="no": continue
    y=r["year"].strip()
    if not y: continue
    expected[(norm(r["municipality"]),y)]=r["municipality"]
    if r.get("has_pdf")=="yes": ca_have.add((norm(r["municipality"]),y))
RES=re.compile(r"result|canvass|precinct|tally",re.I)
NOISE=re.compile(r"specimen|sample.?ballot|calendar|deadline|absentee|nomination|warrant|budget|annual.?report|water|lead|sports|survey|monitor|\bbid\b",re.I)
corpus_have=set()
NODES=Path(__file__).resolve().parents[1]/"data/discover/nodes.jsonl"
# also gather candidates in one pass
AR=re.compile(r"annual.?(town.?)?report|town.?report",re.I)
ACFR=re.compile(r"\bacfr\b|comprehensive.?annual|financial.?report",re.I)
TM=re.compile(r"town.?meeting|town.?election|\bate\b|election.?result",re.I)
MIN=re.compile(r"minutes",re.I)
ELP=re.compile(r"/elections?|election|voting|town.?clerk|/results?",re.I)
cand=defaultdict(list)
for line in NODES.open(encoding="utf-8"):
    try: r=json.loads(line)
    except: continue
    t=norm(r.get("municipality") or "") or host2town.get(norm_host(r.get("seed_host","")),"")
    if not t: continue
    hay=r["url"]+" "+(r.get("anchor") or "")
    yrs=set(re.findall(r"(20[12]\d)",hay))
    if r.get("kind")=="file" and RES.search(hay) and not NOISE.search(hay):
        for y in yrs: corpus_have.add((t,y))
    # candidates (files w/ year, or election pages)
    isfile=r.get("kind")=="file"
    for y in yrs:
        if (t,y) not in expected: continue
        if isfile and AR.search(hay) and not ACFR.search(hay): cand[(t,y)].append((1,"annual_report",r["url"],(r.get("anchor") or "")[:60]))
        elif isfile and TM.search(hay): cand[(t,y)].append((2,"townmtg_election",r["url"],(r.get("anchor") or "")[:60]))
        elif isfile and MIN.search(hay): cand[(t,y)].append((4,"minutes",r["url"],(r.get("anchor") or "")[:60]))
    if not isfile and ELP.search(hay):   # election HTML page (year rarely in url)
        cand[(t,"*")].append((3,"election_page",r["url"],(r.get("anchor") or "")[:60]))

missing=sorted(set(expected)-ca_have-(corpus_have&set(expected)))
print(f"still-missing town-years (loose): {len(missing)}")
# assign election_page candidates (town-level) to each missing year of that town
for (t,y) in missing:
    if (t,"*") in cand:
        for c in cand[(t,"*")][:3]: cand[(t,y)].append(c)
have_cand=[k for k in missing if cand.get(k)]
print(f"  with >=1 container candidate we hold: {len(have_cand)} ({len(have_cand)/len(missing):.0%})")
out=Path(__file__).resolve().parent/"dive_candidates.csv"
id2={norm(v):v for v in expected.values()}
with out.open("w",encoding="utf-8",newline="") as f:
    w=csv.writer(f); w.writerow(["municipality","year","priority","kind","url","title"])
    for (t,y) in missing:
        for pr,kind,url,title in sorted(set(cand.get((t,y),[])))[:4]:
            w.writerow([id2.get(t,t),y,pr,kind,url,title])
print(f"wrote {out.name}")
