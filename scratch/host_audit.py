"""Host-list audit: which of the 351 MA municipalities lack a proper municipal host in
config/muni_hosts.txt (or are represented only by a news/CDN/store host)? Cross-check the
corpus (towns with ~zero nodes). Emits candidates + guessed real domains to verify."""
import csv, json, re
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host, is_storage_host

ROOT = Path(__file__).resolve().parents[1]
def norm(s): return re.sub(r"[^a-z]", "", s.lower())

# all 351 towns
txt = Path(r"C:\Users\Owner\Downloads\election_results (3).sql").read_text(encoding="utf-8", errors="replace")
mm = re.search(r"INSERT INTO `towns`[^;]*?VALUES\s*(.*?);", txt, re.S)
towns = [n.replace("\\'", "'") for _, n in re.findall(r"\((\d+),\s*'((?:[^'\\]|\\.)*)'\)", mm.group(1))]
allt = {norm(t): t for t in towns}

# muni_hosts.txt
hosts = [h.strip() for h in (ROOT/"config/muni_hosts.txt").read_text(encoding="utf-8").splitlines()
         if h.strip() and not h.startswith("#")]
hostset = {norm_host(h) for h in hosts}

# town -> hosts (from inventory native_urls); classify municipal vs news/store
NEWS = re.compile(r"patch\.com|wickedlocal|masslive|\.news|gazette|eagle|telegram|globe|"
                  r"wcvb|whdh|boston\.com|capenews|sentinel|enterprise|register|reformer|"
                  r"itemlive|thereminder|turley|wgbh|wbur|youtube|facebook|twitter|wordpress\.com", re.I)
inv = csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv", encoding="utf-8"))
town_hosts = defaultdict(set)
for r in inv:
    for f in ("native_url", "hosted_url"):
        u = (r.get(f) or "").strip()
        m = re.match(r"https?://([^/]+)", u)
        if m:
            town_hosts[norm(r["municipality"])].add(norm_host(m.group(1)))

def is_muni_host(h, townnorm):
    if is_storage_host(h) or NEWS.search(h): return False
    if "github.io" in h or "documents-on-demand" in h or "sanity.io" in h: return False
    return True

# towns whose town-owned host is NOT in muni_hosts.txt
missing_from_list = []
for tn, name in allt.items():
    my = [h for h in town_hosts.get(tn, set()) if is_muni_host(h, tn)]
    in_list = [h for h in my if h in hostset]
    # also any muni_hosts entry that maps to this town (reverse) — covered if inventory host in list
    if not in_list:
        missing_from_list.append((name, sorted(my)))

# corpus node counts per town (are they actually harvested?)
counts = defaultdict(int)
for line in (ROOT/"data/discover/nodes.jsonl").open(encoding="utf-8"):
    i = line.find('"municipality":')
    if i < 0: continue
    m = re.search(r'"municipality":\s*"([^"]*)"', line)
    if m and m.group(1): counts[norm(m.group(1))] += 1

print(f"total towns: {len(allt)} | muni_hosts.txt entries: {len(hostset)}")
print(f"towns with NO municipal host in muni_hosts.txt: {len(missing_from_list)}\n")
for name, my in sorted(missing_from_list):
    tn = norm(name); nodes = counts.get(tn, 0)
    guess = f"{tn}-ma.gov / townof{tn}.org / {tn}ma.gov"
    inv_hosts = ", ".join(my) if my else "(none in inventory)"
    print(f"  {name:<18} corpus_nodes={nodes:<6} inv_hosts=[{inv_hosts[:60]}]")

# also: towns with very few corpus nodes (harvested poorly) even if host present
print("\ntowns with <50 corpus nodes (thin/failed harvest):")
thin = sorted([(counts.get(tn,0), name) for tn,name in allt.items() if counts.get(tn,0)<50])
for n,name in thin[:40]:
    print(f"   {name:<18} nodes={n}")
Path(__file__).resolve().parent.joinpath("host_audit_missing.csv").write_text(
    "municipality,corpus_nodes,inventory_hosts\n" +
    "\n".join(f"{name},{counts.get(norm(name),0)},{'|'.join(my)}" for name,my in sorted(missing_from_list)),
    encoding="utf-8")
print(f"\nwrote host_audit_missing.csv ({len(missing_from_list)} towns)")
