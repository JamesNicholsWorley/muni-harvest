"""Cross-reference CivicAtlasMA's VERIFIED election-doc URLs (master_urls.csv) against
the harvested corpus (nodes.jsonl). Question: for LEO-sourced election docs (i.e. on the
town's own election office site), did our deep live scrape capture the same URL/host?

LEO = Local Election Office (town site) -> SHOULD be in our corpus.
NEWS = news source -> out of scope (we exclude news hosts).
"""
from __future__ import annotations
import csv, json, re, sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import urlkey, norm_host

ROOT = Path(__file__).resolve().parents[1]
NODES = ROOT / "data" / "discover" / "nodes.jsonl"
MASTER = Path(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv")

def host_of(u):
    m = re.match(r"https?://([^/]+)", u)
    return norm_host(m.group(1)) if m else ""

# --- build corpus indexes ---
corpus_keys = set()
corpus_hosts = set()
corpus_host_paths = defaultdict(set)   # host -> set of path-tails (filename)
n=0
for line in NODES.open(encoding="utf-8"):
    try: rec = json.loads(line)
    except Exception: continue
    n+=1
    u = rec.get("url","")
    if not u: continue
    k = urlkey(u)
    corpus_keys.add(k)
    h = host_of(u)
    if h:
        corpus_hosts.add(h)
        tail = u.rstrip("/").split("/")[-1].lower()
        if tail: corpus_host_paths[h].add(tail)
print(f"corpus: {n:,} nodes | {len(corpus_keys):,} urlkeys | {len(corpus_hosts):,} hosts")

# --- load master election URLs ---
rows = list(csv.DictReader(MASTER.open(encoding="utf-8")))
# an actual election document with a real http(s) native_url we could have crawled
def real_url(u): return u.startswith("http")

cats = Counter()
results = []
for r in rows:
    prov = r["provenance"].strip()
    nu = r["native_url"].strip()
    hu = r["hosted_url"].strip()
    if r["expected"] == "no":       # town had no municipal election that year
        cats["no_election"] += 1; continue
    if not nu or not real_url(nu):
        cats[f"no_usable_native_url({prov or 'blank'})"] += 1
        results.append((r, prov, nu, "no_native_url", ""))
        continue
    key = urlkey(nu)
    h = host_of(nu)
    tail = nu.rstrip("/").split("/")[-1].lower()
    if key in corpus_keys:
        status = "EXACT"
    elif h in corpus_hosts and tail and tail in corpus_host_paths[h]:
        status = "FILE_ON_HOST"     # same file (by name) on same host, different path
    elif h in corpus_hosts:
        status = "HOST_ONLY"        # host crawled but this exact doc not captured
    else:
        status = "HOST_MISSING"     # host not in corpus at all
    cats[f"{prov or 'blank'}:{status}"] += 1
    results.append((r, prov, nu, status, h))

print("\n=== match categories ===")
for k,v in sorted(cats.items()): print(f"  {k:<40}{v:>5}")

# LEO focus
leo = [x for x in results if x[1]=="LEO" and x[3] not in ("no_native_url",)]
from collections import Counter as C
leo_status = C(x[3] for x in leo)
print(f"\n=== LEO election docs with a real URL: {len(leo)} ===")
for k in ("EXACT","FILE_ON_HOST","HOST_ONLY","HOST_MISSING"):
    v=leo_status.get(k,0)
    print(f"  {k:<14}{v:>5}  ({v/len(leo):.1%})")
captured = leo_status.get("EXACT",0)+leo_status.get("FILE_ON_HOST",0)
print(f"  -> CAPTURED (exact or same file on host): {captured}/{len(leo)} = {captured/len(leo):.1%}")
print(f"  -> host present but doc uncaptured (HOST_ONLY): {leo_status.get('HOST_ONLY',0)}")
print(f"  -> host entirely absent (HOST_MISSING): {leo_status.get('HOST_MISSING',0)}")

# dump misses for inspection
with (Path(__file__).resolve().parent / "election_leo_misses.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["municipality","year","status","host","native_url"])
    for r,prov,nu,st,h in leo:
        if st in ("HOST_ONLY","HOST_MISSING"):
            w.writerow([r["municipality"], r["year"], st, h, nu])
print("\nwrote election_leo_misses.csv")

# hosts that are entirely missing (host-level gap)
miss_hosts = Counter(h for r,prov,nu,st,h in leo if st=="HOST_MISSING")
print("\nTop HOST_MISSING hosts (LEO docs whose host we never crawled):")
for h,c in miss_hosts.most_common(20):
    print(f"  {c:>3}  {h}")
