"""Of missed DocumentCenter/View election docs: did our DC enumerator even run on that
host, and did it just not reach the election folder / recent IDs?"""
import csv, json, re, sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host
ROOT = Path(__file__).resolve().parents[1]
NODES = ROOT / "data/discover/nodes.jsonl"

# corpus: per host, set of documentIDs we captured + max id + whether DC enumerator ran
dc_ids = defaultdict(set)
for line in NODES.open(encoding="utf-8"):
    if "documentID=" not in line and "/DocumentCenter/View/" not in line and "/documentcenter/view/" not in line:
        continue
    try: rec = json.loads(line)
    except Exception: continue
    u = rec.get("url",""); m = re.match(r"https?://([^/]+)", u)
    if not m: continue
    h = norm_host(m.group(1))
    mm = re.search(r"documentID=(\d+)", u, re.I) or re.search(r"/DocumentCenter/View/(\d+)", u, re.I)
    if mm: dc_ids[h].add(int(mm.group(1)))

seed = [r for r in csv.DictReader(open(Path(__file__).resolve().parent/"election_seed_verified.csv", encoding="utf-8"))
        if r["capture_status"].startswith("MISS")]
dcmiss = [r for r in seed if "/documentcenter/view/" in r["native_url"].lower()]
print(f"Missed election docs total: {len(seed)}; of which DocumentCenter/View: {len(dcmiss)}")

cat = Counter()
examples = defaultdict(list)
for r in dcmiss:
    h = norm_host(r["host"]); m = re.search(r"/DocumentCenter/View/(\d+)", r["native_url"], re.I)
    if not m: continue
    wid = int(m.group(1)); ids = dc_ids.get(h, set())
    if not ids:
        c = "enumerator NEVER ran on host"
    elif wid in ids:
        c = "we HAVE this id (matched)"
    elif wid > max(ids):
        c = f"id newer than our harvest (ours max<{wid})"
    else:
        c = "id in our range but not captured (folder missed)"
    cat[c]+=1; examples[c].append((h,wid,max(ids) if ids else 0))
print("\nWhy DocumentCenter election docs were missed:")
for c,v in cat.most_common():
    print(f"  {v:>4} ({v/len(dcmiss):.0%})  {c}")
    for h,wid,mx in examples[c][:3]:
        print(f"          e.g. {h} wants id {wid} (our max id there: {mx})")
