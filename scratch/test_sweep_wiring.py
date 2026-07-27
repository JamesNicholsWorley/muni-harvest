"""Fast, deterministic end-to-end test of sweep_host wiring: point the sitemap at the
known election/clerk pages and confirm the sweep emits the election PDF (id 51303) as a
FILE node (proving sitemap -> fetch page -> extract -> is_file_url -> emit doc)."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import muni_harvest.discover.docsweep as ds

ELECTION_PAGES = [
    "https://www.cityoflawrence.com/772/Election-Results",
    "https://www.cityoflawrence.com/324/City-Clerk",
    "https://www.cityoflawrence.com/235/Voting-Elections",
]
# monkeypatch sitemap_urls to return just these pages (fast + deterministic)
ds.sitemap_urls = lambda host, declared=None, max_urls=6000: ELECTION_PAGES

nodes, stats = ds.sweep_host("www.cityoflawrence.com", "Lawrence", max_pages=10)
print("stats:", stats)
files = [n for n in nodes if n["kind"] == "file"]
ids = set()
for n in files:
    m = re.search(r'/DocumentCenter/View/(\d+)|documentID=(\d+)', n["url"], re.I)
    if m: ids.add(m.group(1) or m.group(2))
print(f"file nodes: {len(files)}; distinct doc ids: {len(ids)}")
print(f"target 51303 emitted as a FILE node? {'YES' if '51303' in ids else 'NO'}")
print("sample recent ids:", sorted(ids, key=lambda x:-int(x))[:10])
# show the actual 51303 node
for n in files:
    if "51303" in n["url"]:
        print("node:", {k: n[k] for k in ("url","kind","doctype","discovered_via","anchor")})
        break
print("RESULT:", "PASS" if "51303" in ids and len(files) > 20 else "FAIL")
