"""Build a reusable VERIFIED election-doc seed from CivicAtlasMA/master_urls.csv,
tagged with whether the muni-harvest corpus already captured it. Output feeds the
targeted fetch stage directly (no rediscovery-by-crawl needed)."""
from __future__ import annotations
import csv, json, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import urlkey, norm_host

ROOT = Path(__file__).resolve().parents[1]
NODES = ROOT / "data" / "discover" / "nodes.jsonl"
MASTER = Path(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv")
OUT = Path(__file__).resolve().parent / "election_seed_verified.csv"

def host_of(u):
    m = re.match(r"https?://([^/]+)", u); return norm_host(m.group(1)) if m else ""

keys, hosts, docid = set(), set(), set()
for line in NODES.open(encoding="utf-8"):
    try: rec = json.loads(line)
    except Exception: continue
    u = rec.get("url","")
    if not u: continue
    keys.add(urlkey(u)); h = host_of(u)
    if h: hosts.add(h)
    m = re.search(r"documentID=(\d+)", u, re.I) or re.search(r"/DocumentCenter/View/(\d+)", u, re.I)
    if m and h: docid.add((h, m.group(1)))

rows = list(csv.DictReader(MASTER.open(encoding="utf-8")))
cap = Counter(); out = []
for r in rows:
    if r["expected"] == "no": continue
    prov = r["provenance"].strip()
    nu = r["native_url"].strip()
    if prov not in ("LEO","ATR") or not nu.startswith("http"): continue
    h = host_of(nu); k = urlkey(nu)
    m = re.search(r"/DocumentCenter/View/(\d+)", nu, re.I)
    if k in keys: st = "captured_exact"
    elif m and (h, m.group(1)) in docid: st = "captured_docid"
    elif h in hosts: st = "MISS_host_crawled"
    else: st = "MISS_host_absent"
    cap[st] += 1
    out.append({"municipality": r["municipality"], "year": r["year"],
                "provenance": prov, "capture_status": st, "host": h,
                "native_url": nu, "hosted_url": r.get("hosted_url","")})

with OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["municipality","year","provenance","capture_status","host","native_url","hosted_url"])
    w.writeheader(); w.writerows(out)

tot = len(out)
print(f"verified LEO/ATR election docs (expected, real URL): {tot}")
for k in ("captured_exact","captured_docid","MISS_host_crawled","MISS_host_absent"):
    v = cap[k]; print(f"  {k:<20}{v:>5}  ({v/tot:.1%})")
capd = cap["captured_exact"]+cap["captured_docid"]
print(f"  => CAPTURED total: {capd}/{tot} = {capd/tot:.1%}")
print(f"  => MISSED (directly fetchable from verified URL): {tot-capd}")
print(f"\nwrote {OUT}")
