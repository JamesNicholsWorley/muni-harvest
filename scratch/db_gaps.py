"""Find town-years COMPLETELY ABSENT from our election database (no row in CivicAtlas
master_urls at all) — the true blanks, across all 351 MA municipalities."""
import csv, re
from collections import defaultdict
from pathlib import Path

txt = Path(r"C:\Users\Owner\Downloads\election_results (3).sql").read_text(encoding="utf-8", errors="replace")
m = re.search(r"INSERT INTO `towns`[^;]*?VALUES\s*(.*?);", txt, re.S)
towns = [n.replace("\\'", "'") for _, n in re.findall(r"\((\d+),\s*'((?:[^'\\]|\\.)*)'\)", m.group(1))]
def norm(s): return re.sub(r"[^a-z]", "", s.lower())
allt = {norm(t): t for t in towns}
print("total MA municipalities:", len(towns))

rows = list(csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\master_urls.csv", encoding="utf-8")))
present = set(); years = set(); status = defaultdict(list); expected_no = set()
for r in rows:
    t = norm(r["municipality"]); y = r["year"].strip()
    if not y: continue
    present.add((t, y)); years.add(y); status[(t, y)].append(r.get("status", ""))
    if r.get("expected") == "no":
        expected_no.add((t, y))
years = sorted(y for y in years if y.isdigit())
print("election years in DB:", years)
print("town-year rows in DB:", len(present))

towns_in_db = {t for t, _ in present}
absent_towns = sorted(allt[t] for t in allt if t not in towns_in_db)
print(f"\nMunicipalities with ZERO rows in the election DB ({len(absent_towns)}):")
print("  " + ", ".join(absent_towns))

print("\nper-year coverage (of 351):")
for y in years:
    c = len({t for t, yy in present if yy == y})
    print(f"  {y}: {c}/351 have a row  ({351 - c} blank)")

# blanks: (town, year) NOT in DB at all, for the DB's year span (exclude the 351-absent towns? no, include)
blanks = []
for t, name in allt.items():
    for y in years:
        if (t, y) not in present:
            blanks.append((name, y))
print(f"\ntotal (town,year) BLANKS across {len(allt)} towns x {len(years)} years: {len(blanks)}")
# write full blank list
out = Path(__file__).resolve().parent / "db_blank_town_years.csv"
with out.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(["municipality", "year"])
    for name, y in sorted(blanks): w.writerow([name, y])
print("wrote", out.name)
# sample blanks from towns that DO appear other years (so town is real/active)
active = {t for t, _ in present}
partial = [(n, y) for n, y in sorted(blanks) if norm(n) in active]
print(f"\nblanks in towns that ARE in the DB other years (partial gaps, {len(partial)}): sample")
for n, y in partial[:25]: print(f"   {n} {y}")
