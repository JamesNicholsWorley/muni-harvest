"""Two regional contests a town printed and the corpus does not hold.

A missing contest is the failure the ballot arithmetic cannot see. Closure is a
statement about the marks that ARE in the record, so a whole block that never
made it in leaves every remaining contest closing perfectly -- which is the same
blindness that hid a candidate in Needham Precinct D.

## Montague 2026

Page 6 carries a boxed table under a blue banner reading, verbatim:

    ** These Totals Need to be Combined with the Town of Gill's Election
    Results **   GILL-MONTAGUE REGIONAL SCHOOL COMMITTEE

and inside it TWO separately headed contests. The corpus holds neither the
heading nor the first of them:

    REPRESENTING THE TOWN OF GILL / SCHOOL COMMITTEE For Three Years
    Vote for not more than ONE
    William C. Tomb  161 68 78 81 64 57 | 509
    WRITE-IN'S ... 1 | 1
    BLANKS  54 26 22 37 29 27 | 195
    TOTALS  215 94 100 118 94 84 | 705

Montague's own precincts, voting on the seat that represents Gill, which is why
the banner says the totals have to be combined with Gill's. That spans towns, so
it is `regional_district` and exempt from Montague's ballot arithmetic.

## West Brookfield 2025

Page 2 prints one section headed QUABOAG REGIONAL DISTRICT SCHOOL COMMITTEE
containing two sub-headed groups and ONE shared set of tally rows:

    WARREN (3 YEARS)            MEGAN E. SEARS 118
    WEST BROOKFIELD (3 YEARS)   CRAIG R. BURGESS 153 / BRYAN S. GRIFFING 142
                                CHRISTINE M. LUSZCZ 139
    WRITE IN 2 / BLANK 374 / TOTAL 928

The corpus holds the West Brookfield group with both tally rows and does not
hold Megan Sears at all. 153+142+139+2+374 = 810, and +118 = 928, which is the
total the page prints -- so the missing candidate is exactly the difference.

The Warren contest is added with her figure and NO tally rows. The write-ins and
blanks at the foot serve both groups and the document does not divide them;
splitting them would be inventing an allocation the clerk never made. A contest
that legitimately holds no tally rows is a fact about the page, and saying so is
better than distributing 374 blanks on a guess.

    python -m src.add_missing_regional_contests            # report
    python -m src.add_missing_regional_contests --write
"""
import argparse
import io
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ADDITIONS = {
    "Montague2026": {
        "municipality": "Montague",
        "date": "2026-05-18",
        "office_original": ("GILL-MONTAGUE REGIONAL SCHOOL COMMITTEE - "
                            "REPRESENTING THE TOWN OF GILL"),
        "district_original": "",
        "stage": "General",
        "type": "Regular",
        "num_winners": 1,
        "scope": "regional_district",
        "blanks_printed": True,
        "candidates": [
            {"name_original": "William C. Tomb", "votes": 509},
            {"name_original": "WRITE-IN'S", "votes": 1, "tally_row": True},
            {"name_original": "BLANKS", "votes": 195, "tally_row": True},
        ],
        "source_note": ("page 6, under the banner '** These Totals Need to be "
                        "Combined with the Town of Gill's Election Results **'; "
                        "the page prints TOTALS 705"),
    },
    "WestBrookfield2025": {
        "municipality": "West Brookfield",
        "date": "2025-05-07",
        "office_original": ("QUABOAG REGIONAL DISTRICT SCHOOL COMMITTEE - "
                            "WARREN (3 YEARS)"),
        "district_original": "",
        "stage": "General",
        "type": "Regular",
        "num_winners": 1,
        "scope": "regional_district",
        "blanks_printed": False,
        "candidates": [
            {"name_original": "MEGAN E. SEARS", "votes": 118},
        ],
        "source_note": ("page 2; this group shares its WRITE IN, BLANK and "
                        "TOTAL rows with the WEST BROOKFIELD group beneath it, "
                        "so it carries none of its own. 153+142+139+2+374+118 "
                        "= 928, the total the page prints"),
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    for stem, contest in ADDITIONS.items():
        path = os.path.join(BASE, "data", "json", stem + ".json")
        with io.open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        held = {str(e.get("office_original")) for e in record.get("elections") or []}
        if contest["office_original"] in held:
            print(f"  {stem}: already held; nothing to add")
            continue
        # Date it the way its neighbours are dated rather than by assumption.
        dates = {e.get("date") for e in record.get("elections") or [] if e.get("date")}
        if len(dates) == 1:
            contest["date"] = dates.pop()
        record.setdefault("elections", []).append(contest)
        names = ", ".join(f"{c['name_original']} {c['votes']}"
                          for c in contest["candidates"])
        print(f"  {stem:<20} + {contest['office_original']}")
        print(f"  {'':<20}   {names}  (date {contest['date']})")
        if args.write:
            with io.open(path, "w", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False, indent=1)

    if not args.write:
        print("\nnothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
