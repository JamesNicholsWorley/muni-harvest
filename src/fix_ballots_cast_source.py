"""Fifty records that hold a ballot count and still say they could not derive one.

`ballots_cast` and `ballots_cast_source` are one statement in two fields: the
figure, and how it was arrived at. Fifty records had them disagreeing outright --
a count, beside `cannot_derive`, which says a derivation was attempted and
failed.

That is not a parse error. Every one of the fifty counts was read off a document
by a session and filed in `qa/reference/adjudications.csv` with the quote, and
`qa.apply` wrote the figure. It has no route to the provenance field: it
addresses a field by searching the record for the value being replaced, and
nothing in the ledger row names `ballots_cast_source`. So the figure landed and
the provenance did not, fifty times, and several of the rows said so at the time
-- "NOTE: ballots_cast_source still reads 'cannot_derive' and the applier has no
route to that field."

Left alone the corpus says something false about itself, and says it in the one
field that exists to be honest about where a number came from. `cannot_derive`
is a real answer with a real meaning -- fewer than two qualifying contests, or
no two agree -- and using it as the residue of a tool's blind spot destroys it
for the 560 records where it is true.

## How each was classified

By its own ledger row's recorded reading, not by a rule about the whole set.

    stated_in_record        45  the document prints a ballot or turnout count
                                and the session read it: "TOTAL BALLOTS CAST
                                563", "209 Ballots were cast in this Town
                                Election", "VOTERS: 217".

    derived_from_contests    5  the document prints no such count, and the
                                figure comes from contests on it that agree.
                                Named individually below, because five is few
                                enough to name and a rule nobody can check is
                                worse than a list.

The five: Beverly 2021 (MAYOR totals 8,442 and COUNCILOR AT LARGE 25,326 =
8,442 x 3, and the six ward totals sum to 8,442); Eastham 2025 (every block
prints TOTAL 569 or TOTAL 1138); North Brookfield 2021 (eleven single-seat
blocks each sum to 630); North Brookfield 2023 (ten each sum to 662); Wales 2026
(nine each sum to 64). Each of those five readings opens with the words "No
ballot count is printed", which is what put it in this list rather than the
other.

Idempotent: it only ever moves a record OUT of `cannot_derive`, and only when
`ballots_cast` is not null. Run twice and the second run reports nothing.

    python -m src.fix_ballots_cast_source            # report
    python -m src.fix_ballots_cast_source --write
"""
import argparse
import io
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The document prints no ballot count; the figure comes from contests that agree.
DERIVED = {
    "Beverly2021", "Eastham2025", "NorthBrookfield2021", "NorthBrookfield2023",
    "Wales2026",
}

# Every town-year whose count was read off its document and filed in the ledger,
# and whose provenance field qa.apply could not reach.
STEMS = [
    "Abington2022", "Acushnet2024", "Alford2021", "Alford2025", "Attleboro2021",
    "Bernardston2025", "Beverly2021", "Billerica2021", "Billerica2025",
    "Blandford2022", "Blandford2025", "Brimfield2024", "Chicopee2025",
    "EastBrookfield2023", "Eastham2025", "Gill2026", "Harvard2026",
    "Harwich2023", "Hinsdale2021", "Hinsdale2023", "Hinsdale2025",
    "Hubbardston2021", "Littleton2021", "Methuen2021", "Nahant2024",
    "Nahant2025", "Nahant2026", "NewAshford2021", "NewAshford2022",
    "NewAshford2024", "NewAshford2025", "NewAshford2026", "NewMarlborough2021",
    "NewMarlborough2022", "NewMarlborough2023", "NewMarlborough2024",
    "NewMarlborough2026", "NorthBrookfield2021", "NorthBrookfield2023",
    "Northampton2023", "Norton2026", "Palmer2025", "Petersham2021",
    "Provincetown2026", "Southampton2022", "Wales2022", "Wales2026",
    "Wilmington2022", "Worcester2021", "Worthington2021",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    changed = skipped = 0
    for stem in STEMS:
        path = os.path.join(BASE, "data", "json", stem + ".json")
        if not os.path.exists(path):
            print(f"  {stem:<20} no record held")
            continue
        with io.open(path, encoding="utf-8") as fh:
            record = json.load(fh)

        # Only ever move a record out of cannot_derive, and only where there is
        # a figure for the provenance to be about.  Anything else is a record
        # this file has already done, or one it was never about.
        if record.get("ballots_cast") is None:
            print(f"  {stem:<20} ballots_cast is null; nothing to describe")
            skipped += 1
            continue
        if record.get("ballots_cast_source") != "cannot_derive":
            skipped += 1
            continue

        want = "derived_from_contests" if stem in DERIVED else "stated_in_record"
        record["ballots_cast_source"] = want
        changed += 1
        print(f"  {stem:<20} {record['ballots_cast']:>7}  cannot_derive -> {want}")
        if args.write:
            with io.open(path, "w", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False, indent=1)

    print()
    print(f"{changed} to change, {skipped} already right")
    if changed and not args.write:
        print("nothing was written. Re-run with --write.")


if __name__ == "__main__":
    main()
