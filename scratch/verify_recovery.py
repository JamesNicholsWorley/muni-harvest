"""Verify the sweep/fixes actually recover documents. Measures election-doc RECALL of the
combined corpus (nodes.jsonl + nodes_docsweep.jsonl + nodes_minutes.jsonl) against the
CivicAtlas VERIFIED urls — used purely as a yardstick (NOT ingested). Case-insensitive."""
import csv, json, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import urlkey, norm_host

ROOT = Path(__file__).resolve().parents[1]
MASTER = Path(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv")
CORPORA = [ROOT/"data/discover/nodes.jsonl", ROOT/"data/discover/nodes_docsweep.jsonl",
           ROOT/"data/discover/nodes_minutes.jsonl"]
ONLY_HOST = sys.argv[1] if len(sys.argv) > 1 else None   # optional: restrict to one host

def ci(u): return urlkey(u).lower()

keys = set()
for path in CORPORA:
    if not path.exists(): continue
    n=0
    for line in path.open(encoding="utf-8"):
        try: u=json.loads(line).get("url","")
        except Exception: continue
        if u: keys.add(ci(u)); n+=1
    print(f"loaded {n:,} urls from {path.name}")
print(f"combined distinct urlkeys: {len(keys):,}\n")

rows=[r for r in csv.DictReader(MASTER.open(encoding="utf-8"))
      if r["expected"]!="no" and r["provenance"].strip() in ("LEO","ATR")
      and r["native_url"].strip().startswith("http")]
if ONLY_HOST:
    rows=[r for r in rows if norm_host(re.match(r'https?://([^/]+)',r["native_url"]).group(1))==norm_host(ONLY_HOST)]
    print(f"restricted to host {ONLY_HOST}: {len(rows)} verified docs")

cap=sum(1 for r in rows if ci(r["native_url"]) in keys)
print(f"verified election docs: {len(rows)}")
print(f"RECALL (captured): {cap}/{len(rows)} = {cap/max(len(rows),1):.1%}")
miss=[r for r in rows if ci(r["native_url"]) not in keys]
print(f"missed: {len(miss)}")
for r in miss[:15]:
    print(f"   MISS {r['municipality']} {r['year']}: {r['native_url'][:80]}")
