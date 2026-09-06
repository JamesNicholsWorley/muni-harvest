"""How often does a contest close exactly on ballots x k for an integer k that is
NOT the num_winners we hold?

Read-only. This is a lens, not a check: exact closure proves the digits, never the
record (docs/notes/civicatlas-arithmetic-is-merge-blind.md).  A contest whose
marks divide the ballot count exactly, at a k different from the seat count we
publish, is a place to LOOK -- five were opened by hand today and five were wrong.
"""
import collections, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import layers as L

rows = []
for path in sorted(glob.glob(os.path.join(L.BASE, "data/json/*.json"))):
    stem = os.path.basename(path)[:-5]
    try:
        rec = json.load(open(path))
    except Exception:
        continue
    ballots, _, _ = L.derive_ballots(rec)
    if not ballots:
        continue
    for e in rec.get("elections") or []:
        if L.scope_of(e) == "regional_district":
            continue
        seats = e.get("num_winners") or 1
        m = L.marks_in(e)
        if not m or not L.blanks_printed(e):
            continue
        if m % ballots:
            continue
        k = m // ballots
        if k != seats and 1 <= k <= 40:
            rows.append((stem, str(e.get("office_original") or e.get("office"))[:44],
                         seats, k, m, ballots))

print(f"{len(rows)} contests close exactly on ballots x k with k != num_winners")
towns = collections.Counter(r[0] for r in rows)
print(f"across {len(towns)} town-years\n")
print("direction: held TOO HIGH", sum(1 for r in rows if r[2] > r[3]),
      "| held TOO LOW", sum(1 for r in rows if r[2] < r[3]))
print()
for stem, count in towns.most_common(40):
    print(f"  {stem:22s} {count}")
print("\nfirst 60 rows:")
for r in rows[:60]:
    print(f"  {r[0]:20s} {r[1]:46s} held={r[2]:>3} closes_at={r[3]:>3}  {r[4]}/{r[5]}")
