"""West Tisbury's template counts the write-in names as if they were votes.

The clerk's spreadsheet runs each contest as candidate rows, then `Blanks`, then
a `Write-Ins` row whose figure sits in a narrow shaded cell to the LEFT of the
Total Votes column with 0 underneath it, then `Scattering`, whose figure is the
write-in VOTES, then `Total`. The parse added the write-in NAME COUNT to the
write-in VOTES and published the sum as `Others`.

So every affected contest overflows by exactly the name count, and the clerk's
own printed total is the arithmetic that recovers it:

    Others corrected = Others - (marks - ballots x seats)

2024's Planning Board holds Others 16 and overflows 404 by 8; the page prints
328 + 8 + 68 = 404. Board of Health holds 3 and overflows by 2, so one write-in
vote was cast and two people were written in.

## Why this is not the write-in subtotal fix

That one REMOVES a row that restates the itemised write-ins. This one CORRECTS a
row that is two different quantities added together. Same symptom, different
document, different remedy -- which is why the arithmetic is checked per contest
rather than assumed.

## Scope

Only the town-years using this template. A page carrying both "Overseas Count"
and "Scattering" returns West Tisbury 2022, 2024 and 2025 and nothing else in
the corpus, and the migration refuses any contest where the subtraction would go
negative or where no Others row exists -- neither of which should happen, and
both of which mean the diagnosis does not fit that contest.

    python -m src.fix_west_tisbury_scattering            # report
    python -m src.fix_west_tisbury_scattering --write
"""
import argparse
import glob
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402

OTHERS = re.compile(r"^\s*(?:others?|write[\s-]*ins?|scattering)\s*$", re.I)


def template_towns():
    """Town-years whose document uses the Overseas Count / Scattering template."""
    out = []
    for path in sorted(glob.glob(os.path.join(BASE, "data", "json", "*.json"))):
        stem = os.path.basename(path)[:-5]
        text, _ = layers.document_text(stem)
        if text and "Scattering" in text and "Overseas" in text:
            out.append(stem)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    stems = template_towns()
    print(f"town-years using the template: {stems}\n")
    fixed = 0
    touched = []
    for stem in stems:
        path = os.path.join(BASE, "data", "json", stem + ".json")
        with io.open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        ballots = record.get("ballots_cast")
        if not isinstance(ballots, int) or ballots <= 0:
            print(f"  {stem}: no ballot count; cannot check the arithmetic")
            continue
        changed = False
        for e in record.get("elections") or []:
            if layers.scope_of(e) == "regional_district":
                continue
            seats = e.get("num_winners") or 1
            cands = e.get("candidates") or []
            marks = sum(c.get("votes") or 0
                        for c in cands if isinstance(c.get("votes"), int))
            excess = marks - ballots * seats
            if excess <= 0:
                continue
            row = next((c for c in cands
                        if OTHERS.match(str(c.get("name_original") or ""))
                        and isinstance(c.get("votes"), int)), None)
            if row is None:
                print(f"  {stem} {str(e.get('office_original'))[:30]}: "
                      f"overflows by {excess} and has no Others row -- "
                      f"the diagnosis does not fit; left alone")
                continue
            if row["votes"] - excess < 0:
                print(f"  {stem} {str(e.get('office_original'))[:30]}: "
                      f"Others {row['votes']} is smaller than the overflow "
                      f"{excess}; left alone")
                continue
            print(f"  {stem:<16} {str(e.get('office_original'))[:30]:<30} "
                  f"Others {row['votes']} -> {row['votes'] - excess} "
                  f"({marks} -> {ballots * seats})")
            row["votes"] -= excess
            fixed += 1
            changed = True
        if changed:
            touched.append(stem)
            if args.write:
                with io.open(path, "w", encoding="utf-8") as fh:
                    json.dump(record, fh, ensure_ascii=False, indent=1)

    print(f"\n{fixed} contests corrected in {len(touched)} town-years")
    if args.write:
        with io.open(os.path.join(BASE, "src", "_west_tisbury.txt"),
                     "w", encoding="utf-8") as fh:
            fh.write("\n".join(touched))
    else:
        print("nothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
