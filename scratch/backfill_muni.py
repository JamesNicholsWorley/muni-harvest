"""Backfill municipality on nodes.jsonl using authoritative towns_websites.csv (host->town)
+ the explicit canonical-host map for the newly-added towns. Fixes attribution for docs on
hosts CivicAtlas never mapped (pelhamma.gov etc.). Rewrites nodes.jsonl in place (backup once)."""
import csv, json, re, shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host

DISC = Path(__file__).resolve().parents[1] / "data" / "discover"
def norm(s): return re.sub(r"[^a-z]", "", s.lower())

host2town = {}
for r in csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv", encoding="utf-8")):
    w = (r["Website"] or "").strip().lower()
    if w:
        h = norm_host(re.sub(r"^https?://", "", w).strip("/").split("/")[0])
        host2town[h] = r["Municipality"]
for h, town in {"goshen-ma.us": "Goshen", "gosnold-ma.gov": "Gosnold", "harwich-ma.gov": "Harwich",
                "northandoverma.gov": "North Andover", "norwoodma.gov": "Norwood",
                "pelhamma.gov": "Pelham", "townofpetersham.gov": "Petersham",
                "pittsfieldma.gov": "Pittsfield", "townofsavoy.com": "Savoy",
                "townofsouthampton.org": "Southampton", "wbrookfield.com": "West Brookfield",
                "townofwestspringfield.org": "West Springfield", "weymouth.ma.us": "Weymouth"}.items():
    host2town[h] = town

src = DISC / "nodes.jsonl"
bak = DISC / "nodes.pre_backfill.jsonl"
if not bak.exists():
    shutil.copy2(src, bak)
tmp = DISC / "nodes.backfill.tmp"
filled = total = 0
with tmp.open("w", encoding="utf-8") as w:
    for line in src.open(encoding="utf-8"):
        try: r = json.loads(line)
        except Exception:
            w.write(line); continue
        total += 1
        if not r.get("municipality"):
            t = host2town.get(norm_host(r.get("seed_host", "")))
            if t:
                r["municipality"] = t; filled += 1
                w.write(json.dumps(r) + "\n"); continue
        w.write(line)
shutil.move(str(tmp), str(src))
print(f"backfilled municipality on {filled:,} / {total:,} nodes")
