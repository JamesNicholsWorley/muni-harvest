"""Holyoke 2021, re-parsed from the document. The held record was invented.

The document is five landscape pages inside portrait sheets, with `Page rot: 0`,
so nothing turns them and both held readings are transposed nonsense. Rendered
at 200dpi with pymupdf's `prerotate(270)` every page is crisp.

What the held record contained:

  * `City Councilor Ward 1A: Israel Rivera 185`. Israel Rivera is an AT-LARGE
    candidate with 3,525 votes citywide, and 185 is his Ward 1B COLUMN figure
    from the at-large table. Every one of the eighteen ward contests was built
    this way -- an at-large candidate, holding one of his own precinct numbers,
    under a ward heading he never stood in. The document's Ward 1 contest is
    Victor M. Machado 186 against Jenny Rivera 398, and neither name appears in
    the record at all.
  * Every `Others` and `Blanks` a round number: 400, 1400, 100, 50, 80, 40, 60.
    Fifty-nine of its sixty-two tally figures were multiples of five against a
    corpus median of eighteen per cent, which is how the fabrication was first
    noticed.
  * Mayor: Garcia 3,562 -- which is Sullivan's number. The page prints Garcia
    4,577 and Sullivan 3,562, and 4577+3562+34+64 = 8237 exactly.
  * City Clerk and City Treasurer swapped: the page has Brenna Murphy McGee as
    Clerk with 6,093 and Katherine M. Jackowski as Treasurer with 5,828.

So this is not a patch. Every contest is replaced with what the page prints.

## Named write-ins

The template lists a write-in who was named -- Diosdado Lopez 3 under Mayor,
Rebecca Lisi 10 at-large -- as a row of its own AND inside `Total number of
write-ins`. Keeping both double-counts; dropping the name loses a person, which
is the error the arithmetic can never see. So the name is kept and the aggregate
carries the REMAINDER, which is subtraction of two printed figures rather than
an invention, and the contest then closes on the ballots exactly.

Mayor: 4577 + 3562 + 3 + 31 + 64 = 8237, against Total Ballots 8237.

## Seats

Six at-large councillors and seven by ward is Holyoke's thirteen-member council,
and the at-large marks divide by 8,237 into six rather than any other number.
Every ward seat is one.

    python -m src.reparse_holyoke_2021            # report
    python -m src.reparse_holyoke_2021 --write
"""
import argparse
import io
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEM = "Holyoke2021"
DATE = "2021-11-02"
SHA = "941b40f2a92c4d6d95b7e70bd935bb4d2b91d16a265bf87b5ffcb5120d660f06"


def contest(office, seats, cands, scope="at_large", district=""):
    return {
        "municipality": "Holyoke", "date": DATE,
        "office_original": office, "district_original": district,
        "stage": "General", "type": "Regular",
        "num_winners": seats, "scope": scope, "blanks_printed": True,
        "candidates": [
            ({"name_original": n, "votes": v, "tally_row": True}
             if n in ("Total number of write-ins", "Times Blank Voted")
             else {"name_original": n, "votes": v})
            for n, v in cands
        ],
    }


W = "Total number of write-ins"
B = "Times Blank Voted"

ELECTIONS = [
    contest("MAYOR", 1, [
        ("JOSHUA A. GARCIA", 4577), ("MICHAEL J. SULLIVAN", 3562),
        ("Diosdado Lopez", 3), (W, 31), (B, 64)]),
    contest("CITY CLERK", 1, [
        ("BRENNA MURPHY McGEE", 6093), (W, 87), (B, 2054)]),
    contest("CITY TREASURER", 1, [
        ("KATHERINE M. JACKOWSKI", 5828), (W, 78), (B, 2327)]),
    contest("CITY COUNCILOR AT-LARGE", 6, [
        ("JOSE MALDONADO VELEZ", 3183), ("KEVIN JOURDAIN", 3544),
        ("PETER R. TALLMAN", 3519), ("ISRAEL RIVERA", 3525),
        ("JAMES LEAHY", 2983), ("JOSEPH McGIVERIN", 3281),
        ("TESSA R. MURPHY-ROMBOLETTI", 3248), ("HOWARD B. GREANEY JR.", 2906),
        ("MARK D. CHATEL", 1353), ("PAOLA FERRARIO", 2158),
        ("JENNIFER M. KEITT", 2361), ("Rebecca Lisi", 10),
        (W, 69), (B, 17250)]),

    contest("CITY COUNCILOR WARD 1", 1, [
        ("VICTOR M. MACHADO", 186), ("JENNY RIVERA", 398),
        (W, 3), (B, 71)], "sub_town", "Ward 1"),
    contest("CITY COUNCILOR WARD 2", 1, [
        ("WILL PUELLO", 394), (W, 6), (B, 137)], "sub_town", "Ward 2"),
    contest("CITY COUNCILOR WARD 3", 1, [
        ("ANNE N. THALHEIMER", 584), ("DAVID K. BARTLEY", 769),
        (W, 2), (B, 85)], "sub_town", "Ward 3"),
    contest("CITY COUNCILOR WARD 4", 1, [
        ("KOCAYNE S. GIVNER", 341), ("MICHAEL THOMAS SICILIANO", 301),
        (W, 4), (B, 63)], "sub_town", "Ward 4"),
    contest("CITY COUNCILOR WARD 5", 1, [
        ("GUY R. O'DONNELL", 836), ("LINDA VACON", 854),
        (W, 2), (B, 71)], "sub_town", "Ward 5"),
    contest("CITY COUNCILOR WARD 6", 1, [
        ("JUAN C. ANDERSON-BURGOS", 800), ("PRESTON R. MACY", 274),
        (W, 5), (B, 82)], "sub_town", "Ward 6"),
    contest("CITY COUNCILOR WARD 7", 1, [
        ("TODD A. McGEE", 1347), (W, 36), (B, 580)], "sub_town", "Ward 7"),

    # Romero and Lefebvre are write-in candidates named inside the 128, not
    # names on the ballot: 128 + 530 = 658, the Total Ballots the page prints,
    # and adding them on top overshoots by exactly 45 = 25 + 20. Same treatment
    # as Lopez under Mayor -- keep the names, aggregate carries the remainder.
    contest("SCHOOL COMMITTEE WARD 1", 1, [
        ("Gustavo Romero", 25), ("Mildred Lefebvre", 20),
        (W, 83), (B, 530)], "sub_town", "Ward 1"),
    contest("SCHOOL COMMITTEE WARD 2", 1, [
        ("ROSALEE TENSLEY WILLIAMS", 394), (W, 5), (B, 138)],
        "sub_town", "Ward 2"),
    contest("SCHOOL COMMITTEE WARD 3", 1, [
        ("REBECCA BIRKS", 1004), (W, 10), (B, 425)], "sub_town", "Ward 3"),
    contest("SCHOOL COMMITTEE WARD 4", 1, [
        ("FAIZUL SIBDHANNY JR.", 144), ("IRENE FELICIANO-SIMS", 445),
        (W, 5), (B, 115)], "sub_town", "Ward 4"),
    contest("SCHOOL COMMITTEE WARD 5", 1, [
        ("JOHN G. WHELIHAN", 1275), (W, 15), (B, 473)], "sub_town", "Ward 5"),
    contest("SCHOOL COMMITTEE WARD 6", 1, [
        ("WILLIAM R. COLLAMORE", 840), (W, 15), (B, 305)], "sub_town", "Ward 6"),
    contest("SCHOOL COMMITTEE WARD 7", 1, [
        ("COLLEEN CHESMORE", 732), ("ELEANOR M. WILSON", 1038),
        (W, 4), (B, 193)], "sub_town", "Ward 7"),
    contest("SCHOOL COMMITTEE AT-LARGE", 1, [
        ("MILDRED LEFEBVRE", 4183), ("MARC HICKEY", 2481),
        (W, 34), (B, 1534)]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    path = os.path.join(BASE, "data", "json", STEM + ".json")
    with io.open(path, encoding="utf-8") as fh:
        old = json.load(fh)

    record = {
        "document": {
            "heading_verbatim": "BIENNIAL MUNICIPAL ELECTION   OFFICIAL RESULTS   2-Nov-21",
            "election_type": "Regular",
            "election_type_evidence": "BIENNIAL MUNICIPAL ELECTION",
            "date_verbatim": "2-Nov-21",
            "is_sample_ballot": False,
            "offices_on_ballot": len(ELECTIONS),
            "uncontested_remainder": False,
            "uncontested_remainder_evidence": "",
            "registered_voters": 27354,
            "source_note": (
                "five landscape pages inside portrait sheets, 'Page rot: 0', "
                "rendered at 200dpi with pymupdf prerotate(270). Page 1 header "
                "'Registered voters 27354 / Voters 8237' across fourteen ward "
                "columns. A named write-in is printed both as its own row and "
                "inside 'Total number of write-ins'; the name is kept and the "
                "aggregate carries the remainder, so Mayor closes "
                "4577+3562+3+31+64 = 8237."),
        },
        "_source_stem": STEM,
        "_source_pdf": (
            "https://jamesnicholsworley.github.io/civicatlasma/pdfs/"
            "Holyoke2021_d0.pdf"),
        "_source_sha256": SHA,
        "ballots_cast": 8237,
        "ballots_cast_source": "stated_in_record",
        "elections": ELECTIONS,
    }

    print(f"  contests {len(old.get('elections') or [])} -> {len(ELECTIONS)}")
    bad = 0
    for e in ELECTIONS:
        marks = sum(c["votes"] for c in e["candidates"])
        if e["scope"] == "at_large":
            room = 8237 * e["num_winners"]
            flag = "" if marks <= room else "   <-- OVER"
            if marks > room:
                bad += 1
            print(f"  {e['office_original']:<30} seats={e['num_winners']} "
                  f"marks={marks:<6} room={room}{flag}")
        else:
            print(f"  {e['office_original']:<30} seats={e['num_winners']} "
                  f"marks={marks:<6} ({e['district_original']})")
    print(f"\n{bad} at-large contests exceed the ballots")
    if args.write:
        with io.open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=1)
        print("written")
    else:
        print("nothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
