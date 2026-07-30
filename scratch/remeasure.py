"""Re-measure still-missing, attributing docs to towns via BOTH the corpus municipality
tag AND the authoritative towns_websites.csv (host->town) — fixes the new hosts that
CivicAtlas never mapped (pelhamma.gov, etc.)."""
import csv, json, re
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host

def norm(s): return re.sub(r"[^a-z]", "", s.lower())
# host -> town from towns_websites.csv (authoritative)
host2town = {}
for r in csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv", encoding="utf-8")):
    w = (r["Website"] or "").strip().lower()
    if w:
        h = norm_host(re.sub(r"^https?://", "", w).strip("/").split("/")[0])
        host2town[h] = norm(r["Municipality"])
        host2town["www." + h] = norm(r["Municipality"])

# explicit canonical hosts I added to muni_hosts.txt (redirect targets not in towns_websites)
for h, town in {"goshen-ma.us": "Goshen", "gosnold-ma.gov": "Gosnold", "harwich-ma.gov": "Harwich",
                "northandoverma.gov": "North Andover", "norwoodma.gov": "Norwood",
                "pelhamma.gov": "Pelham", "townofpetersham.gov": "Petersham",
                "pittsfieldma.gov": "Pittsfield", "townofsavoy.com": "Savoy",
                "townofsouthampton.org": "Southampton", "wbrookfield.com": "West Brookfield",
                "townofwestspringfield.org": "West Springfield", "weymouth.ma.us": "Weymouth"}.items():
    host2town[h] = norm(town); host2town["www." + h] = norm(town)

rows = list(csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv", encoding="utf-8")))
expected = {}; ca_have = set()
for r in rows:
    if r.get("expected") == "no": continue
    y = r["year"].strip()
    if not y: continue
    k = (norm(r["municipality"]), y); expected[k] = r
    if r.get("has_pdf") == "yes": ca_have.add(k)

ELECT = re.compile(r"result|canvass|precinct|tally|votecount|vote.?count", re.I)
NOT = re.compile(r"specimen|sample.?ballot|ballot.?question|calendar|deadline|absentee|"
                 r"early.?voting|voter.?reg|nomination|warrant|lottery|\bbid\b|budget|"
                 r"annual.?report|finance|service.?delivery|survey", re.I)
corpus_have = set()
for line in (Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl").open(encoding="utf-8"):
    if "esult" not in line and "anvass" not in line and "recinct" not in line and "ally" not in line:
        continue
    try: r = json.loads(line)
    except Exception: continue
    if r.get("kind") != "file": continue
    t = norm(r.get("municipality") or "")
    if not t:                       # attribute by seed_host via authoritative map
        t = host2town.get(norm_host(r.get("seed_host", "")), "")
    if not t: continue
    hay = r["url"] + " " + (r.get("anchor") or "")
    if not ELECT.search(hay) or NOT.search(hay): continue
    for y in set(re.findall(r"(20[12]\d)", hay)):
        corpus_have.add((t, y))

covered = ca_have | (corpus_have & set(expected))
missing = sorted(set(expected) - covered)
print(f"expected town-years: {len(expected)}")
print(f"  CivicAtlas pdf: {len(ca_have)} | corpus results doc: {len(corpus_have & set(expected))}")
print(f"  covered (union): {len(covered)}")
print(f"STILL MISSING: {len(missing)}  ({len(missing)/len(expected):.0%})   [was 412]")
# what the re-sweep towns contributed
newhosts = [norm(x) for x in ["Goshen","Gosnold","Harwich","North Andover","Norwood","Pelham",
            "Petersham","Pittsfield","Savoy","Southampton","West Brookfield","West Springfield","Weymouth"]]
gained = [(t,y) for (t,y) in expected if t in newhosts and (t,y) in corpus_have and (t,y) not in ca_have]
print(f"\nnewly-covered town-years from the re-swept towns: {len(gained)}")
id2 = {norm(r['municipality']): r['municipality'] for r in rows}
for t,y in sorted(gained): print(f"   {id2.get(t,t)} {y}")
