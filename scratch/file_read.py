"""Rows read off rendered pages in this run, one document at a time.

Every `read` below is what the page prints, taken from a render at the dpi
named, and every arithmetic claim in `why` is computed from the record rather
than asserted.  Nothing here was decided from an OCR: the OCR is the thing that
failed, which is why these figures did not ground in the first place.
"""

import csv
import datetime
import hashlib
import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")


def pdf_sha(stem):
    p = os.path.join(BASE, "data", "pdfs", stem + ".pdf")
    if not os.path.exists(p):
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


ROWS = [
    dict(
        stem="Scituate2021",
        field="elections[LIBRARY TRUSTEE FOR THREE YEARS]"
              ".candidates[Blanks].votes",
        was="792", should_be="793", status="verified",
        read="READ the single page of data/pdfs/Scituate2021.pdf (no text "
             "layer, /Rotate honoured by pymupdf) at 150dpi. 'OFFICIAL "
             "RESULTS / Town of Scituate / Annual Town Election / MAY 22, "
             "2021'. The LIBRARY TRUSTEE (TWO) FOR THREE YEARS block reads, "
             "verbatim, across its six precinct columns and TOTAL: 'CAROL A. "
             "SULLIVAN-HANLEY 252 206 199 182 169 202 1210 / SHEILA L. "
             "KUKSTIS 253 200 193 184 168 196 1194 / ALL OTHERS 3 1 0 0 0 1 5 "
             "/ BLANKS 150 111 118 150 137 127 793 / TOTALS 658 518 510 516 "
             "474 526 3202'.",
        why="The blanks row's own six precinct cells sum to 793, not the 792 "
            "the record holds, and at 793 the block totals 3,202 = 1,601 x 2 "
            "exactly, which is the TOTALS row the clerk prints and the ballot "
            "count every other contest on the sheet closes on. At 792 it is "
            "3,201, one mark short. Two independent checks on one digit: the "
            "row's own columns and the column's own total. This is also why "
            "the figure did not ground -- 792 is nowhere on the page.",
    ),
    dict(
        stem="Ashland2021",
        field="elections[SELECT BOARD].candidates[Blanks].votes",
        was="226", should_be="225", status="verified",
        read="READ page 1 of data/pdfs/Ashland2021.pdf (2pp, no text layer) at "
             "150dpi. 'ASHLAND ANNUAL TOWN ELECTION, MAY 18, 2021 / OFFICIAL "
             "RESULTS / CERTIFIED MAY 19, 2021'. The SELECT BOARD block reads, "
             "verbatim, across its five precinct columns and TOTALS: 'BLANKS "
             "41 55 45 36 48 225 / YOLANDA GREAVES 127 138 109 95 108 577 / "
             "ROBERT K. SCHERER 129 147 116 107 116 615 / PAMELA CJ MCQUILLAN "
             "81 84 56 62 58 341 / WRITE IN 0 0 0 0 0 0 / TOTAL # OF VOTES 378 "
             "424 326 300 330 1758'.",
        why="41+55+45+36+48 = 225, the figure the page prints, and at 225 the "
            "block totals 1,758 = 879 x 2 exactly -- the TOTAL # OF VOTES row "
            "the clerk prints, and 879 is the ballot count the ASSESSOR and "
            "BOARD OF HEALTH - 2 YRS blocks each total. At the recorded 226 it "
            "is 1,759, one mark more than there are ballots in a two-seat "
            "contest, which is impossible.",
    ),
    dict(
        stem="NorthAttleborough2024",
        field="ballots_cast",
        was="None", should_be="1243", status="verified",
        read="READ the single page of data/pdfs/NorthAttleborough2024.pdf at "
             "170dpi. 'April 2, 2024 ANNUAL TOWN ELECTION RESULTS' over a "
             "nine-precinct header printing three rows: 'Total Voters 2383 "
             "2688 2660 2678 2553 2629 2839 2534 2522 23486', '# who voted 89 "
             "175 166 50 104 171 166 203 119 1243' and '% who voted ... "
             "5.29%'.",
        why="The record holds ballots_cast null. 1,243 is printed as its own "
            "labelled row and its nine precinct cells sum to it exactly; "
            "1,243/23,486 = 5.29%, the percentage the same header prints. The "
            "Board of Public Works (1 YEAR) block totals 1,243 independently.",
    ),
    dict(
        stem="NorthAttleborough2024",
        field="elections[Park Commission].num_winners",
        was="2", should_be="needs your reading -- the page prints 1 and its "
                           "own total row implies 2",
        status="",
        read="READ the single page at 170dpi. The Park Commission block is "
             "headed by a VOTE FOR column reading 1, and prints: 'Mark Michael "
             "Giansante 906 / Write in #1 (candidate disqualified) 5 / Write "
             "in #2 Andrew Hinckley 4 / Write in #3 Aiden Harding 3 / Write in "
             "All Others(2 votes or less) 7 / Blank 1561 / Total 2486'. The "
             "Board of Public Works (1 YEAR) block immediately above it also "
             "reads VOTE FOR 1 and totals 1,243.",
        why="CONTRADICTION worth your time rather than a shrug. The printed "
            "seat count is 1 and outranks the arithmetic by the project's own "
            "rule, but the clerk's own Total row for this block is 2,486 = "
            "1,243 x 2, and 906+5+4+3+7+1561 = 2486 confirms the rows sum to "
            "it. The block above, also VOTE FOR 1, totals 1,243. So either the "
            "VOTE FOR cell is wrong or the Total cell carries the two-seat "
            "formula from the blocks above it. num_winners decides who won and "
            "no size-based diff can see it, so this is not a guess to make "
            "unattended.",
    ),
]

# The two figures that are correct as recorded and simply do not appear on the
# page.  Filed so the reading is not lost, with no change proposed.
NOTES = [
    dict(
        stem="NorthAttleborough2024",
        field="elections[Park Commission].candidates['Others'].votes -- NO "
              "CHANGE, filed as a reading",
        was="12", should_be="12 (unchanged)", status="needs-owner",
        read="READ at 170dpi: the block prints FOUR write-in rows -- 'Write in "
             "#1 (candidate disqualified) 5', 'Write in #2 Andrew Hinckley 4', "
             "'Write in #3 Aiden Harding 3', 'Write in All Others(2 votes or "
             "less) 7'.",
        why="The record keeps the two named write-ins as candidates and holds "
            "Others 12, which is 5 + 7: the disqualified candidate's row and "
            "the All Others row summed. That is the documented convention -- "
            "keep the name, give the aggregate the remainder -- and it closes: "
            "906+4+3+12+1561 = 2486, the printed Total. Filed only so the "
            "reason figures_grounded fails here is on the record; nothing to "
            "change.",
    ),
    dict(
        stem="Seekonk2021",
        field="elections[BOARD OF ASSESSORS (Vote for ONE) 2 YR TERM]"
              ".candidates[Blanks].votes -- NO CHANGE, filed as a reading",
        was="1108", should_be="1108 (unchanged)", status="needs-owner",
        read="READ the single page of data/pdfs/Seekonk2021.pdf at 170dpi and "
             "the block re-cropped at 500dpi. 'Town of Seekonk / Total Tally "
             "Sheet / April 5, 2021 Annual Town Election / UNOFFICIAL', "
             "'Total Votes Cast = 1236'. The BOARD OF ASSESSORS (Vote for ONE) "
             "2 YR TERM block prints: 'Write-In's 15 36 22 29 102' and "
             "'Blanks 210 320 286 292 1'. At 500dpi that last cell is a clean, "
             "isolated 1 -- not a truncated figure.",
        why="210+320+286+292 = 1,108, which is what the record holds, so the "
            "record is the sum of the clerk's own precinct cells and the "
            "clerk's own TOTAL cell for that row is the thing that is wrong. "
            "figures_grounded fails because 1,108 is printed nowhere. Note "
            "that the precinct columns do not all close either: 15+210 = 225 "
            "and 29+292 = 321 match their Total Votes Cast, while 36+320 = 356 "
            "against 380 and 22+286 = 308 against 310.",
    ),
]


def main():
    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    have = {(r["stem"], r["field"]) for r in rows}
    added = 0
    for spec in ROWS + NOTES:
        if (spec["stem"], spec["field"]) in have:
            print("already filed:", spec["stem"])
            continue
        row = {k: "" for k in fields}
        row.update(spec)
        row["source_sha256"] = pdf_sha(spec["stem"])
        row["decided_by"] = "civicatlas-qa (unattended run)"
        row["decided_on"] = datetime.date.today().isoformat()
        rows.append(row)
        added += 1
        print(f"filed: {spec['stem']:<22} {spec['field'][:52]}")
    if "--write" in sys.argv and added:
        with io.open(LEDGER, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})
        print(f"\n{added} rows appended")
    else:
        print("\nnothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
