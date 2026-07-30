"""Town-years CivicAtlas never got a document for (status=missing / resource_exhausted).
Cross-reference the consolidated muni-harvest corpus: did our sweep find an election doc
for any of them? Split into (a) our-sweep-now-fills-the-gap and (b) still absent."""
import csv, json, re
from collections import defaultdict
from pathlib import Path

def norm(s): return re.sub(r"[^a-z]", "", s.lower())
NO_DOC = {"missing", "resource_exhausted"}   # expected a result, no document obtained
rows = list(csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv", encoding="utf-8")))
missing = {}
for r in rows:
    if r.get("status", "") in NO_DOC and r.get("expected") != "no":
        missing[(norm(r["municipality"]), r["year"].strip())] = r["municipality"]
print(f"CivicAtlas town-years with NO document (status missing/exhausted): {len(missing)}")

# corpus: election-ish docs per (town, year) via URL/anchor
NODES = Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl"
ELECT = re.compile(r"election|canvass|precinct|tally|official.{0,20}result|result.{0,20}(official|election)|votecount|vote.?count", re.I)
BALLOT_ONLY = re.compile(r"specimen|sample.?ballot|ballot.?question|calendar|deadline|absentee|early.?voting|voter.?reg|nomination|warrant", re.I)
found = defaultdict(list)
miss_towns = {t for t, _ in missing}
for line in NODES.open(encoding="utf-8"):
    if "lection" not in line and "esult" not in line and "anvass" not in line:
        continue
    try: r = json.loads(line)
    except Exception: continue
    if r.get("kind") != "file": continue
    t = norm(r.get("municipality") or "")
    if t not in miss_towns: continue
    hay = r["url"] + " " + (r.get("anchor") or "")
    if not ELECT.search(hay): continue
    strong = ("result" in hay.lower() or "canvass" in hay.lower() or "precinct" in hay.lower()
              or "tally" in hay.lower())
    for y in set(re.findall(r"(20[12]\d)", hay)):
        if (t, y) in missing:
            found[(t, y)].append((strong and not BALLOT_ONLY.search(hay), r["url"], (r.get("anchor") or "")[:70]))

filled = {k: v for k, v in found.items() if any(s for s, _, _ in v)}   # has a strong results doc
weak = {k for k in found if k not in filled}
still = [missing[k] + " " + k[1] for k in missing if k not in found]
print(f"\n(A) our sweep now has a RESULTS doc for a CivicAtlas-missing town-year: {len(filled)}")
for (t, y), v in sorted(filled.items())[:30]:
    s, u, a = next(x for x in v if x[0])
    print(f"   {missing[(t,y)]} {y}: {a or u[:70]}")
    print(f"        {u[:98]}")
print(f"\n(B) only weak/ballot-type doc found (not results): {len(weak)}")
print(f"(C) still no election doc at all in corpus: {len(still)}")
Path(__file__).resolve().parent.joinpath("still_missing.txt").write_text(
    "\n".join(sorted(still)), encoding="utf-8")
print("   sample still-missing:", sorted(still)[:15])
