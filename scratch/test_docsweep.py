import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import is_file_url, is_doc_endpoint, urlkey

# --- unit: doc endpoints now recognized as files ---
cases = {
    "https://www.cityoflawrence.com/DocumentCenter/View/51303/OFFICIAL-RESULTS": True,
    "https://www.framinghamma.gov/DocumentCenter/View/44049/Official-Results-110221-v2?bidId=": True,
    "https://host/ImageRepository/Document?documentID=48816": True,
    "https://www.lynnma.gov/common/pages/GetFile.ashx?key=q38CAFaA": True,
    "https://host/1/Home": False,                       # content page, not a doc
    "https://host/departments/elections": False,
    "https://host/foo.pdf": True,
    "https://s3.amazonaws.com/bucket/x": True,
    "https://resources.finalsite.net/images/v1/x.pdf": True,
}
ok = True
for u, want in cases.items():
    got = is_file_url(u)
    flag = "OK" if got == want else "FAIL"
    if got != want: ok = False
    print(f"  [{flag}] is_file_url={got!s:<5} want={want!s:<5} {u[:70]}")
# path-case dedup
a = urlkey("https://x/DocumentCenter/View/51303/A")
b = urlkey("https://x/documentcenter/view/51303/A")
print(f"  [{'OK' if a==b else 'FAIL'}] path-case dedup: {a} == {b}")
print("UNIT:", "PASS" if ok and a==b else "FAIL")

# --- integration: sweep Lawrence, look for 51303 ---
print("\nsweeping www.cityoflawrence.com (max_pages 500)...")
from muni_harvest.discover.docsweep import sweep_host
nodes, stats = sweep_host("www.cityoflawrence.com", "Lawrence", max_pages=500)
print("stats:", stats)
ids = set()
import re
for n in nodes:
    m = re.search(r'/DocumentCenter/View/(\d+)|documentID=(\d+)', n["url"], re.I)
    if m: ids.add(m.group(1) or m.group(2))
print(f"distinct DocumentCenter doc ids captured: {len(ids)}")
print(f"target 51303 captured? {'YES' if '51303' in ids else 'NO'}")
print("sample high ids:", sorted(ids, key=lambda x:-int(x))[:12])
files = [n for n in nodes if n['kind']=='file']
print(f"total file nodes: {len(files)} ; page nodes: {sum(1 for n in nodes if n['kind']=='page')}")
