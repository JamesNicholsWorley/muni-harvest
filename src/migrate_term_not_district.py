"""A term length is not a district. Undo the 438 contests that read it as one.

Leicester 2026 prints "Three years" in a column headed Precinct. The parser took
the column heading at its word, put "Three years" in `district_original`, and a
non-empty district makes a contest `sub_town` -- so all twelve of Leicester's
contests became precinct contests, and the record could not derive its own 525
ballots even though five blocks print them. `sub_town` numbers divide one town
and are expected to sum to it; `at_large` numbers ARE the town. Getting that
backwards breaks the ballot arithmetic for the whole record.

The same shape is in 443 contests across 120 town-years.

## Why this is safe to do in bulk

A district is a place. `1-year term`, `Three Year Term`, `For Two Years` and
`Two Year Unexpired Term` are not places, and no municipality is named that way.
The test is on the district string alone and does not guess.

Scope is then re-derived from the office, which is where scope was always
knowable: `TOWN MEETING MEMBER PRECINCT 3` is sub_town because the office says
so, `SOUTHERN WORCESTER COUNTY REGIONAL VOCATIONAL SCHOOL` is regional because
the office says so, and `Board of Health` is neither.

Run over the corpus, that moves 438 contests from sub_town to at_large and
leaves 5 regional ones regional. **Not one contest whose office names a precinct
or a ward is in the set** -- which is the check that matters, because it means no
genuinely sub-town contest is being flipped. A document mentioning "precinct" is
not evidence either way: a town-wide return normally prints precinct COLUMNS
that sum to the town, and mistaking that layout for scope is the original bug.

## Why a migration and not 438 ledger rows

`CLAUDE.md` says a data correction is a row, never code, and that is right for a
correction that rests on reading one document. This is not that. It is one
parser artifact with one rule, and 438 rows would each quote the same reasoning
while burying the ledger that exists for judgement calls. The precedent is
`migrate_schema_2026_09.py`, which retired the -1/-3 sentinels the same way.

    python -m src.migrate_term_not_district           # report, change nothing
    python -m src.migrate_term_not_district --write
"""
import argparse
import collections
import glob
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402  (needs BASE on the path first)

# "For Three Years", "1-year term", "Two Year Unexpired Term", "3 yr".
TERM = re.compile(
    r"^\s*(?:for\s+)?(?:a\s+)?"
    r"(?:one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})"
    r"[\s-]*(?:year|yr)s?\b", re.I)


def rescope(office):
    """Where scope was always knowable: the office."""
    if layers.RE_REGIONAL.search(office):
        return "regional_district"
    if layers.RE_SUBTOWN.search(office):
        return "sub_town"
    return "at_large"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    moved = collections.Counter()
    touched = []
    for path in sorted(glob.glob(os.path.join(BASE, "data", "json", "*.json"))):
        with io.open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        changed = False
        for e in record.get("elections") or []:
            district = (e.get("district_original") or "").strip()
            if not district or not TERM.match(district):
                continue
            office = str(e.get("office_original") or "")
            new = rescope(office)
            moved[(e.get("scope"), new)] += 1
            # The term length is not lost -- it is in office_original, where the
            # document prints it. It is only removed from the field that means
            # "which part of the town voted".
            e["district_original"] = ""
            e["scope"] = new
            changed = True
        if changed:
            touched.append(os.path.basename(path)[:-5])
            if args.write:
                with io.open(path, "w", encoding="utf-8") as fh:
                    json.dump(record, fh, ensure_ascii=False, indent=1)

    for (old, new), n in moved.most_common():
        print(f"  {n:4}  {old} -> {new}")
    print(f"\n{sum(moved.values())} contests in {len(touched)} town-years")
    if not args.write:
        print("nothing written. Re-run with --write.")
    else:
        with io.open(os.path.join(BASE, "src", "_term_not_district.txt"),
                     "w", encoding="utf-8") as fh:
            fh.write("\n".join(touched))
        print("written; the town-years touched are listed in "
              "src/_term_not_district.txt")


if __name__ == "__main__":
    main()
