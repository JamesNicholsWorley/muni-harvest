"""Link-rot analysis: town-years where CivicAtlas RECORDED a native_url (found the doc)
but never obtained it (status missing/exhausted, has_pdf!=yes). Are those specific docs
represented elsewhere? Check (1) our consolidated corpus (same urlkey OR same host+docID
OR same town-year election doc), and later (2) Wayback."""
import csv, json, re
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import urlkey, norm_host

def norm(s): return re.sub(r"[^a-z]", "", s.lower())
def ci(u): return urlkey(u).lower()

rows = list(csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv", encoding="utf-8")))
rotted = []
for r in rows:
    if r.get("expected") == "no": continue
    if r.get("has_pdf") == "yes": continue                 # they got it in time
    nu = (r.get("native_url") or "").strip()
    if not nu.startswith("http"): continue                 # must have located a URL
    if r.get("status", "") not in {"missing", "resource_exhausted", "oversized_deferred", "needs_md_html"}:
        continue
    rotted.append(r)
print(f"town-years with a located native_url but NO downloaded pdf (rot candidates): {len(rotted)}")

# corpus indexes
keys = set(); docid = set(); elect_ty = defaultdict(list)  # (town,year)->urls (election docs)
ELECT = re.compile(r"election|canvass|precinct|tally|official.{0,15}result|result", re.I)
for line in open(Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl", encoding="utf-8"):
    try: r = json.loads(line)
    except Exception: continue
    u = r.get("url", "")
    if not u: continue
    keys.add(ci(u))
    h = re.match(r"https?://([^/]+)", u)
    if h:
        host = norm_host(h.group(1))
        m = re.search(r"/DocumentCenter/View/(\d+)", u, re.I) or re.search(r"documentID=(\d+)", u, re.I)
        if m: docid.add((host, m.group(1)))
    if ELECT.search(line):
        t = norm(r.get("municipality") or "")
        if t:
            hay = u + " " + (r.get("anchor") or "")
            for y in set(re.findall(r"(20[12]\d)", hay)):
                if "result" in hay.lower() or "canvass" in hay.lower():
                    elect_ty[(t, y)].append(u)

exact = samehost = samety = none = 0
still = []
for r in rotted:
    nu = r["native_url"].strip(); t = norm(r["municipality"]); y = r["year"].strip()
    h = re.match(r"https?://([^/]+)", nu); host = norm_host(h.group(1)) if h else ""
    m = re.search(r"/DocumentCenter/View/(\d+)", nu, re.I) or re.search(r"documentID=(\d+)", nu, re.I)
    if ci(nu) in keys or (m and (host, m.group(1)) in docid):
        exact += 1
    elif elect_ty.get((t, y)):
        samety += 1
    else:
        none += 1; still.append(r)
print(f"\n  recovered — EXACT doc now in corpus (same url/docID):   {exact}")
print(f"  recovered — a RESULTS doc for that town-year in corpus: {samety}")
print(f"  still NOT represented in corpus:                        {none}")
# save the still-missing rotted native_urls for a Wayback check
Path(__file__).resolve().parent.joinpath("rotted_still.jsonl").write_text(
    "\n".join(json.dumps({"municipality": r["municipality"], "year": r["year"],
                          "native_url": r["native_url"]}) for r in still), encoding="utf-8")
print(f"\n  wrote {len(still)} still-missing rotted URLs -> rotted_still.jsonl (for Wayback check)")
print("  sample still-missing native_urls:")
for r in still[:12]: print(f"     {r['municipality']} {r['year']}: {r['native_url'][:80]}")
