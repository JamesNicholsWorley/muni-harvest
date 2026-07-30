"""Grep-verify: fetch a sample of the container docs (annual reports / minutes / HTML
election pages) found for still-missing town-years and check they actually contain
election-results content. Confirms they are valid FINDS (the town-year's results live
inside a document we already have)."""
import csv, json, re, ssl, sys, io, urllib.request
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

def norm(s): return re.sub(r"[^a-z]", "", s.lower())
missing = {(norm(r["municipality"]), r["year"]): r["municipality"]
           for r in csv.DictReader(open(Path(__file__).resolve().parent/"still_missing_final.csv", encoding="utf-8"))}
miss_towns = {t for t, _ in missing}

# collect candidate container URLs by type for missing town-years
AR = re.compile(r"annual.?report|town.?report|\bacfr\b", re.I)
MIN = re.compile(r"minutes|town.?meeting", re.I)
cand = defaultdict(list)   # (town,year,type) -> url
for line in open(Path(__file__).resolve().parents[1]/"data/discover/nodes.jsonl", encoding="utf-8"):
    try: r = json.loads(line)
    except Exception: continue
    if r.get("kind") != "file": continue
    t = norm(r.get("municipality") or "")
    if t not in miss_towns: continue
    hay = r["url"] + " " + (r.get("anchor") or "")
    typ = "annual_report" if AR.search(hay) else ("minutes" if MIN.search(hay) else None)
    if not typ: continue
    for y in set(re.findall(r"(20[12]\d)", hay)):
        if (t, y) in missing and r["url"].lower().endswith(".pdf"):
            cand[(t, y, typ)].append(r["url"])

# sample: spread across towns
by_type = defaultdict(list)
seen_t = set()
for (t, y, typ), urls in cand.items():
    if (t, typ) in seen_t: continue        # one per town per type for spread
    seen_t.add((t, typ)); by_type[typ].append((missing[(t, y)], y, urls[0]))
sample = by_type["annual_report"][:16] + by_type["minutes"][:8]
print(f"annual_report candidates: {len(by_type['annual_report'])}, minutes: {len(by_type['minutes'])}")
print(f"probing {len(sample)} container PDFs for election-results content...\n")

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (research; polite)"}
import fitz
ELECT = re.compile(r"annual town election|town election|election results|for selectman|"
                   r"board of selectmen.{0,40}\d|moderator.{0,30}\d|blanks\b|write-?in", re.I)
hit = miss = err = 0
for town, y, url in sample:
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40, context=ctx).read()
        doc = fitz.open(stream=raw, filetype="pdf")
        txt = "".join(doc[i].get_text() for i in range(min(len(doc), 60)))
        m = ELECT.findall(txt)
        # look for a vote-count pattern near 'election'
        has = bool(m) and (y in txt)
        tag = f"HAS election content ({len(m)} signals)" if has else ("election words but no yr" if m else "no election content")
        if has: hit += 1
        else: miss += 1
        print(f"  [{'OK ' if has else '?? '}] {town} {y} ({len(doc)}pp): {tag}")
    except Exception as e:
        err += 1
        print(f"  [ERR] {town} {y}: {type(e).__name__}")
print(f"\ncontainers confirmed to hold election content: {hit}/{hit+miss} probed ({err} errors)")
