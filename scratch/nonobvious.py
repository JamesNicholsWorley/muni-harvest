"""For still-missing town-years, hunt NON-OBVIOUS corpus files that likely CONTAIN the
election results even though they aren't named 'results': annual town reports (have an
elections section), town-meeting/town-clerk minutes, and packets. Reports how many
missing town-years have such a candidate already in our corpus."""
import csv, json, re
from collections import defaultdict, Counter
from pathlib import Path

def norm(s): return re.sub(r"[^a-z]", "", s.lower())
missing = {}
for r in csv.DictReader(open(Path(__file__).resolve().parent / "still_missing_final.csv", encoding="utf-8")):
    missing[(norm(r["municipality"]), r["year"])] = r["municipality"]
miss_towns = {t for t, _ in missing}

CATS = [
    ("annual_report", re.compile(r"annual.?report|town.?report|\bacfr\b|annual.?town.?rep", re.I)),
    ("townmeeting_min", re.compile(r"town.?meeting.*(min|result)|\batm\b|\bstm\b|meeting.?minutes", re.I)),
    ("clerk", re.compile(r"town.?clerk|/clerk/|city.?clerk", re.I)),
    ("minutes", re.compile(r"minutes|/minutes/", re.I)),
    ("election_page", re.compile(r"election|voting|/elections?/", re.I)),
]
cand = defaultdict(lambda: defaultdict(list))   # (town,year) -> cat -> [urls]
NODES = Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl"
for line in NODES.open(encoding="utf-8"):
    try: r = json.loads(line)
    except Exception: continue
    if r.get("kind") != "file": continue
    t = norm(r.get("municipality") or "")
    if t not in miss_towns: continue
    hay = r["url"] + " " + (r.get("anchor") or "")
    yrs = set(re.findall(r"(20[12]\d)", hay))
    for cat, rx in CATS:
        if rx.search(hay):
            for y in yrs:
                if (t, y) in missing:
                    cand[(t, y)][cat].append(r["url"])
            break

covered = Counter()
any_cand = set()
for k, cats in cand.items():
    any_cand.add(k)
    for c in cats: covered[c] += 1
print(f"still-missing town-years: {len(missing)}")
print(f"  have SOME non-obvious candidate file in corpus: {len(any_cand)} "
      f"({len(any_cand)/len(missing):.0%})")
print("  by candidate type (town-years with >=1):")
for c, n in covered.most_common():
    print(f"     {c:<18} {n}")
# the highest-value: annual reports (contain results section) for missing town-years
print("\nsample missing town-years with an ANNUAL REPORT in corpus (likely contains results):")
n = 0
for (t, y), cats in cand.items():
    if "annual_report" in cats:
        print(f"   {missing[(t,y)]} {y}: {cats['annual_report'][0][:85]}")
        n += 1
        if n >= 15: break
truly = [k for k in missing if k not in any_cand]
print(f"\nmissing town-years with NO candidate file of any kind: {len(truly)} "
      f"({len(truly)/len(missing):.0%})")
