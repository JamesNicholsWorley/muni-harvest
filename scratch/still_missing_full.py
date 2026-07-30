"""Definitive still-missing accounting: expected town-years (expected!=no) covered by
NEITHER CivicAtlas (has_pdf=yes) NOR our corpus (a real results doc for that town-year).
Categorize the residual."""
import csv, json, re
from collections import defaultdict, Counter
from pathlib import Path

def norm(s): return re.sub(r"[^a-z]", "", s.lower())
rows = list(csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv", encoding="utf-8")))
expected = {}      # (town,year) -> row  (expected an election)
ca_have = set()    # CivicAtlas downloaded
for r in rows:
    if r.get("expected") == "no": continue
    y = r["year"].strip()
    if not y: continue
    k = (norm(r["municipality"]), y)
    expected[k] = r
    if r.get("has_pdf") == "yes":
        ca_have.add(k)
print(f"expected town-years (election happened): {len(expected)}")
print(f"  CivicAtlas has a downloaded pdf:        {len(ca_have)}")

# corpus: real results doc per town-year (strong signal, exclude ballots/budgets/etc.)
ELECT = re.compile(r"result|canvass|precinct|tally|votecount|vote.?count", re.I)
NOT = re.compile(r"specimen|sample.?ballot|ballot.?question|calendar|deadline|absentee|"
                 r"early.?voting|voter.?reg|nomination|warrant|lottery|\bbid\b|budget|"
                 r"annual.?report|finance|service.?delivery|survey", re.I)
corpus_have = set()
NODES = Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl"
for line in NODES.open(encoding="utf-8"):
    if "esult" not in line and "anvass" not in line and "recinct" not in line and "ally" not in line:
        continue
    try: r = json.loads(line)
    except Exception: continue
    if r.get("kind") != "file": continue
    t = norm(r.get("municipality") or "")
    if not t: continue
    hay = r["url"] + " " + (r.get("anchor") or "")
    if not ELECT.search(hay) or NOT.search(hay): continue
    for y in set(re.findall(r"(20[12]\d)", hay)):
        corpus_have.add((t, y))
print(f"  our corpus has a results doc:           {len(corpus_have & set(expected))}")

covered = ca_have | (corpus_have & set(expected))
missing = sorted(set(expected) - covered)
print(f"\nSTILL MISSING (neither source): {len(missing)}  of {len(expected)} expected "
      f"= {len(missing)/len(expected):.0%} gap")
by_year = Counter(y for _, y in missing)
print("by year:", dict(sorted(by_year.items())))

# id2name
id2name = {norm(r["municipality"]): r["municipality"] for r in rows}
# how many missing towns are entirely absent from corpus (never crawled well)
out = Path(__file__).resolve().parent / "still_missing_final.csv"
with out.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(["municipality", "year", "civicatlas_status", "native_url"])
    for k in missing:
        r = expected[k]
        w.writerow([id2name.get(k[0], k[0]), k[1], r.get("status", ""), r.get("native_url", "")])
print(f"wrote {out.name}")
# towns with the most missing years (systemic gaps)
tc = Counter(k[0] for k in missing)
print("\ntowns with the most missing years:")
for t, c in tc.most_common(15):
    print(f"   {id2name.get(t,t):<20} {c} years missing")
