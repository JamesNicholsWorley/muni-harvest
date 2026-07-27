"""Requantify election capture (1) case-insensitively, and (2) measure how many missed
hosts were under-crawled (few pages) => the miss is a crawl-coverage failure, not absence."""
from __future__ import annotations
import csv, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import urlkey, norm_host

ROOT = Path(__file__).resolve().parents[1]
NODES = ROOT / "data/discover/nodes.jsonl"
MASTER = Path(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv")

def ukey_ci(u):        # case-insensitive urlkey
    return urlkey(u).lower()

keys_ci = set()
host_pages = Counter(); host_nodes = Counter()
for line in NODES.open(encoding="utf-8"):
    try: rec = json.loads(line)
    except Exception: continue
    u = rec.get("url","")
    if not u: continue
    keys_ci.add(ukey_ci(u))
    m = re.match(r"https?://([^/]+)", u)
    if m:
        h = norm_host(m.group(1)); host_nodes[h]+=1
        if rec.get("kind")!="file": host_pages[h]+=1

rows = [r for r in csv.DictReader(MASTER.open(encoding="utf-8"))
        if r["expected"]!="no" and r["provenance"].strip() in ("LEO","ATR")
        and r["native_url"].strip().startswith("http")]

cap_ci = 0; misses = []
for r in rows:
    nu = r["native_url"].strip()
    if ukey_ci(nu) in keys_ci:
        cap_ci += 1
    else:
        h = norm_host(re.match(r"https?://([^/]+)", nu).group(1))
        misses.append((r["municipality"], r["year"], h, nu))
tot = len(rows)
print(f"verified LEO/ATR election docs: {tot}")
print(f"CASE-INSENSITIVE capture: {cap_ci} ({cap_ci/tot:.1%})   (was {int(0.402*tot)} case-sensitive)")
print(f"still-missed: {len(misses)}")

# of the misses, how many are on hosts we barely crawled?
buckets = Counter()
hostmiss = defaultdict(int)
for muni,yr,h,nu in misses:
    hostmiss[h]+=1
for muni,yr,h,nu in misses:
    p = host_pages.get(h,0)
    if h not in host_nodes: b="host_absent"
    elif p==0: b="0 pages crawled (wayback-only)"
    elif p<100: b="<100 pages (shallow crawl)"
    elif p<400: b="100-400 pages"
    else: b=">=400 pages (deep crawl)"
    buckets[b]+=1
print("\nMissed election docs by how well we crawled their host:")
for b in ["host_absent","0 pages crawled (wayback-only)","<100 pages (shallow crawl)","100-400 pages",">=400 pages (deep crawl)"]:
    v=buckets.get(b,0); print(f"  {b:<34}{v:>4} ({v/len(misses):.0%})")

# hosts with the most missed docs AND shallow crawl = highest-value re-crawl targets
print("\nTop miss hosts (missed_docs, pages_crawled, total_nodes):")
for h,c in sorted(hostmiss.items(), key=lambda x:-x[1])[:20]:
    print(f"  {c:>3} missed | {host_pages.get(h,0):>4} pages | {host_nodes.get(h,0):>6} nodes | {h}")
