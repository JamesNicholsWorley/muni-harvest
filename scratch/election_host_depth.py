"""Test the user's claim: 'we crawled the whole site, we should have collected every URL.'
For missed election docs, how deeply did we actually crawl the host? Do we have its
DocumentCenter tree? Is the election doc's neighborhood present at all?"""
from __future__ import annotations
import csv, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host

ROOT = Path(__file__).resolve().parents[1]
NODES = ROOT / "data/discover/nodes.jsonl"
seed = [r for r in csv.DictReader(open(Path(__file__).resolve().parent/"election_seed_verified.csv", encoding="utf-8"))
        if r["capture_status"].startswith("MISS")]

# pick a spread of missed hosts (dedupe by host, keep those with a real crawlable town host)
byhost = defaultdict(list)
for r in seed: byhost[r["host"]].append(r)
targets = [h for h in byhost if h and "amazonaws" not in h and "finalsite" not in h
           and "revize" not in h and "googleapis" not in h][:14]

# per host: total nodes, pages vs files, has documentcenter, discovered_via mix, max depth
stat = {h: {"nodes":0,"files":0,"pages":0,"dc":0,"via":Counter(),"depth":0,"paths":set()} for h in targets}
tset = set(targets)
for line in NODES.open(encoding="utf-8"):
    try: rec = json.loads(line)
    except Exception: continue
    u = rec.get("url","")
    m = re.match(r"https?://([^/]+)", u)
    if not m: continue
    h = norm_host(m.group(1))
    if h not in tset: continue
    s = stat[h]; s["nodes"]+=1
    if rec.get("kind")=="file": s["files"]+=1
    else: s["pages"]+=1
    if "documentcenter" in u.lower() or "imagerepository" in u.lower(): s["dc"]+=1
    s["via"][rec.get("discovered_via","")]+=1
    s["depth"]=max(s["depth"], rec.get("depth",0) or 0)
    # collect election-ish path presence
    if re.search(r"elect|clerk|result|vote", u, re.I): s["paths"].add(u.lower()[:120])

print(f"{'host':<26}{'nodes':>7}{'pages':>7}{'files':>7}{'DC':>6}{'maxD':>5}  top via")
for h in targets:
    s=stat[h]
    via=",".join(f"{k}:{v}" for k,v in s["via"].most_common(3))
    print(f"{h:<26}{s['nodes']:>7}{s['pages']:>7}{s['files']:>7}{s['dc']:>6}{s['depth']:>5}  {via}")
    miss=byhost[h]
    print(f"      missed election docs here: {len(miss)}; e.g. {miss[0]['native_url'][:80]}")
    if s['paths']:
        print(f"      election-ish URLs we DID capture on this host: {len(s['paths'])}")
        for p in list(s['paths'])[:3]: print(f"         {p}")
    else:
        print(f"      *** ZERO election/clerk/result URLs captured on this host ***")
