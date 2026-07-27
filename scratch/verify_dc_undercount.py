import csv, re, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host
NODES = Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl"
img = set()   # (host, id)
for line in NODES.open(encoding="utf-8"):
    if "documentID=" not in line and "/DocumentCenter/View/" not in line:
        continue
    try: rec = json.loads(line)
    except Exception: continue
    u = rec.get("url", "")
    h = re.match(r"https?://([^/]+)", u)
    if not h: continue
    host = norm_host(h.group(1))
    m = re.search(r"documentID=(\d+)", u, re.I) or re.search(r"/DocumentCenter/View/(\d+)", u, re.I)
    if m: img.add((host, m.group(1)))
print("corpus (host,documentID) pairs:", len(img))
rows = [r for r in csv.DictReader(open(Path(__file__).resolve().parent/"election_leo_misses.csv", encoding="utf-8"))
        if r["status"] == "HOST_ONLY" and "/documentcenter/view/" in r["native_url"].lower()]
hit = miss = 0
for r in rows:
    m = re.search(r"/DocumentCenter/View/(\d+)", r["native_url"], re.I)
    if not m: continue
    key = (norm_host(r["host"]), m.group(1))
    if key in img: hit += 1
    else: miss += 1
tot = hit + miss
print(f"DocumentCenter/View election docs: {tot}")
print(f"  captured via ImageRepository (same host+ID): {hit} ({hit/tot:.0%})")
print(f"  truly not captured: {miss}")
