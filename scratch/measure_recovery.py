"""Before/after election-doc recall for specific hosts: old corpus (nodes.jsonl) vs
old + docsweep. Verified URLs used only as a yardstick (never ingested)."""
import csv, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import urlkey, norm_host
ROOT = Path(__file__).resolve().parents[1]
MASTER = Path(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv")
hosts = {norm_host(h) for h in sys.argv[1:]} or None
def ci(u): return urlkey(u).lower()

def load(path):
    keys=set()
    if not path.exists(): return keys
    for line in path.open(encoding="utf-8"):
        try: u=json.loads(line).get("url","")
        except Exception: continue
        if not u: continue
        h=re.match(r'https?://([^/]+)',u)
        if hosts and (not h or norm_host(h.group(1)) not in hosts): continue
        keys.add(ci(u))
    return keys

old = load(ROOT/"data/discover/nodes.jsonl")
sweep = load(ROOT/"data/discover/nodes_docsweep.jsonl")
both = old | sweep
print(f"hosts={sorted(hosts) if hosts else 'ALL'}")
print(f"old corpus urlkeys: {len(old)}  | +docsweep: {len(both)} (+{len(both)-len(old)})")

rows=[r for r in csv.DictReader(MASTER.open(encoding="utf-8"))
      if r["expected"]!="no" and r["provenance"].strip() in ("LEO","ATR")
      and r["native_url"].strip().startswith("http")]
if hosts:
    rows=[r for r in rows if norm_host(re.match(r'https?://([^/]+)',r["native_url"]).group(1)) in hosts]
def recall(keys): return sum(1 for r in rows if ci(r["native_url"]) in keys)
print(f"\nverified election docs on these hosts: {len(rows)}")
print(f"  recall BEFORE (nodes.jsonl):     {recall(old)}/{len(rows)} = {recall(old)/max(len(rows),1):.0%}")
print(f"  recall AFTER  (+docsweep):       {recall(both)}/{len(rows)} = {recall(both)/max(len(rows),1):.0%}")
newly=[r for r in rows if ci(r['native_url']) not in old and ci(r['native_url']) in sweep]
print(f"  newly recovered by docsweep: {len(newly)}")
for r in newly[:12]: print(f"     + {r['municipality']} {r['year']}: {r['native_url'][:75]}")
