"""Authoritative host audit: compare every town's official website (towns_websites.csv)
against config/muni_hosts.txt. Emit towns whose official domain is missing from the list,
with corpus node counts, so we add exactly the real gaps (no guessing)."""
import csv, re, json
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host

ROOT = Path(__file__).resolve().parents[1]
def norm(s): return re.sub(r"[^a-z]", "", s.lower())

tw = {}
for r in csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv", encoding="utf-8")):
    w = (r["Website"] or "").strip().lower()
    if w:
        w = re.sub(r"^https?://", "", w).strip("/").split("/")[0]
        tw[r["Municipality"]] = norm_host(w)
print(f"towns_websites.csv: {len(tw)} towns with a website")

hosts = {norm_host(h.strip()) for h in (ROOT/"config/muni_hosts.txt").read_text(encoding="utf-8").splitlines()
         if h.strip() and not h.startswith("#")}

# corpus counts
counts = defaultdict(int)
for line in (ROOT/"data/discover/nodes.jsonl").open(encoding="utf-8"):
    m = re.search(r'"municipality":\s*"([^"]*)"', line)
    if m and m.group(1): counts[norm(m.group(1))] += 1

# a town's official domain counts as present if it (or a www-variant) is in the list
missing = []
for name, dom in sorted(tw.items()):
    present = dom in hosts or ("www." + dom) in hosts or dom.replace("www.", "") in hosts
    if not present:
        missing.append((name, dom, counts.get(norm(name), 0)))
print(f"\ntowns whose OFFICIAL domain is NOT in muni_hosts.txt: {len(missing)}")
print(f"  of those with ZERO corpus nodes (true gaps): {sum(1 for _,_,c in missing if c==0)}\n")
for name, dom, c in sorted(missing, key=lambda x: x[2]):
    flag = "  <-- ZERO nodes (add)" if c == 0 else ""
    print(f"  {name:<18} {dom:<28} corpus_nodes={c}{flag}")

# write the add-list (official domains not in list) — those with 0 or few nodes
add = [(n, d) for n, d, c in missing if c < 100]
Path(__file__).resolve().parent.joinpath("hosts_to_add.txt").write_text(
    "\n".join(d for _, d in sorted(add)), encoding="utf-8")
print(f"\nwrote hosts_to_add.txt ({len(add)} domains with <100 nodes)")
# towns with NO website at all in the authoritative CSV
allrows = list(csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv", encoding="utf-8")))
nosite = [r["Municipality"] for r in allrows if not (r["Website"] or "").strip()]
print(f"towns with NO website in the authoritative CSV: {len(nosite)} -> {nosite}")
