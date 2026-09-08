"""A second batch of rows read off rendered pages, and one whole-record fault.

Same discipline as scratch/file_read.py: what the page prints, at the dpi named,
with the arithmetic computed from the record rather than asserted.
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
        stem="Oxford2026",
        field="elections[MODERATOR].candidates['Others'].votes",
        was="12", should_be="10", status="verified",
        read="READ page 1 of data/pdfs/Oxford2026.pdf (2pp, no text layer) at "
             "160dpi. 'Town of Oxford / Official Annual Town Election Results "
             "/ May 19, 2026', header row 'Votes Cast: 273 142 283 196 4 898'. "
             "The MODERATOR block (3yrs, vote 1) prints, verbatim, across the "
             "five precinct columns and TOTALS: 'Cheryll Anne Leblanc 205 111 "
             "224 150 3 693 / Write-ins 0 0 0 0 0 0 / Russell Charles Rheault "
             "3 . . 3 . 6 / Michael Joseph Monticelli 1 . . . . 1 / Mark P. "
             "Mercadante 1 . . . . 1 / Christopher Everitt . 1 . . . 1 / "
             "Garrett Lee Sanford . . . 1 . 1 / Blanks 63 30 58 43 1 195 / "
             "TOTALS 273 142 283 196 4 898'.",
        why="The record aggregates the five named write-ins into one 'Others' "
            "row and holds 12. The page's named write-in rows are 6, 1, 1, 1 "
            "and 1, and the unnamed 'Write-ins' row is 0, so the aggregate is "
            "10. At 10 the block totals 693+10+195 = 898, which is the TOTALS "
            "row the clerk prints and the Votes Cast the header prints; at 12 "
            "it is 900, two marks more than there are ballots in a "
            "single-seat contest. 10 is not printed as a total anywhere, which "
            "is why the string test cannot settle it and this reading has to.",
    ),
    dict(
        stem="Oxford2026", field="ballots_cast",
        was="None", should_be="898", status="verified",
        read="READ page 1 at 160dpi: the table's own header row is 'Votes "
             "Cast: 273 142 283 196 4 | 898' across precincts 1, 2, 3, 4 and "
             "4A.",
        why="273+142+283+196+4 = 898, and both the BOARD OF LIBRARY TRUSTEES "
            "and MODERATOR blocks print a TOTALS row of 898 independently. The "
            "record holds null.",
    ),
    dict(
        stem="Bolton2026",
        field="elections[Nashoba Regional School Committee - 3 year]"
              ".candidates['Others'].votes",
        was="491", should_be="6", status="verified",
        read="READ page 3 of data/pdfs/Bolton2026.pdf, which has a text layer, "
             "so these are the clerk's own characters: 'Race / Candidate / "
             "Vote for 1 / Nashoba Regional School Committee - 3 year / Write "
             "In's 485 / Blanks 123 / Anthony Lapomardo 190 / Joel McCarthy "
             "289 / All Others 6'. Page 1 heads the document 'Total number of "
             "votes cast = 608 / Registered voters in Bolton = 4519 / % Voter "
             "turnout = 13% / Unofficial Results / Annual Town Election / "
             "5/11/2026'.",
        why="The write-in subtotal counted twice, and by 485. 'Write In's 485' "
            "is the aggregate and the three rows under it are its breakdown: "
            "190+289+6 = 485 exactly, and 485+123 = 608, the total votes cast. "
            "The record keeps the two named write-ins AND holds Others 491, "
            "which is the 485 aggregate plus the 6 remainder, so the contest "
            "sums to 1,093 on 608 ballots. Others 6 -- the printed 'All "
            "Others' row -- closes it at 190+289+6+123 = 608 exactly. Nothing "
            "flagged this because the contest is scoped regional_district and "
            "is exempt from the ballot arithmetic; the figures here are "
            "Bolton's own column, which is why the exemption hid a 485-vote "
            "error.",
    ),
    dict(
        stem="Hadley2025", field="ballots_cast",
        was="None", should_be="1082", status="verified",
        read="READ page 1 of data/pdfs/Hadley2025.pdf at 160dpi. 'DOINGS AT "
             "THE MAY 20, 2025 ANNUAL TOWN ELECTION ... The ballot machine "
             "tape total was 1081. There was one (1) hand count ballot, and "
             "one (1) provisional ballot (not accepted). A total of 1082 voted "
             "out of an eligible 3972 voters = 27% turn out'.",
        why="Stated in a sentence and reconciled in the same sentence: 1081 "
            "machine + 1 hand count = 1082. Eight blocks on the page print a "
            "Total row of 1082 (Moderator, Assessor, Board of Health, Planning "
            "Board 5yr, School Committee, Oliver Smith Will Elector, Park "
            "Commission, Town Clerk), each closing on it exactly.",
    ),
    dict(
        stem="Windsor2025", field="ballots_cast",
        was="None", should_be="56", status="verified",
        read="READ the single page of data/pdfs/Windsor2025.pdf at 160dpi. "
             "'ANNUAL TOWN ELECTION RESULTS - May 12, 2025' over '56 Voted Out "
             "of the 730 Registered Voters'.",
        why="Every single-seat block on the sheet closes on it: Select Board "
            "3yr 55+1+0 = 56, Select Board 2yr 46+10 = 56, Cemetery 50+6 = 56, "
            "Constable 54+2 = 56, Moderator 51+5 = 56, Planning Board 49+7 = "
            "56, Tree Warden 49+7 = 56, MLP 3yr 49+7 = 56, MLP 2yr 49+7 = 56.",
    ),
]

NOTES = [
    dict(
        stem="Hadley2025",
        field="elections[SELECT BOARD].candidates[Blanks].votes -- NO CHANGE, "
              "filed as a reading",
        was="359", should_be="359 (unchanged)", status="needs-owner",
        read="READ page 1 at 160dpi and the block again at 400dpi. 'SELECT "
             "BOARD (vote for two) three year term / Randall E. Izer received "
             "six hundred twenty nine votes 629 / Molly A. Keegan received six "
             "hundred ninety three votes 693 / Philip W. Shumway received four "
             "hundred seventy five votes 475 / Others 8 / Blanks 2164 / Total "
             "2752'. At 400dpi the Blanks cell is unambiguously 2164.",
        why="This is the one block on the page whose own two summary cells do "
            "not work. Every other block closes on 1082 exactly. Here the "
            "marks are 629+693+475+8 = 1805 and the ceiling is 1082 x 2 = "
            "2164 -- which is the number printed in the BLANKS cell, so the "
            "clerk's spreadsheet has put the ballots-times-seats figure in the "
            "blanks row. The printed Total 2752 works out to blanks of 947, "
            "which would be 2,752 marks in a contest that can hold 2,164 and "
            "is impossible. 2164 - 1805 = 359 is the only value consistent "
            "with the ballot count, and it is what the record holds. Filed so "
            "the reason figures_grounded fails is on the record; nothing to "
            "change.",
    ),
    dict(
        stem="WestBrookfield2026",
        field="whole record -- every contest drops the document's Undervotes "
              "row and double-counts its BLANK row",
        was="nine contests summing well short of the ballot count; e.g. "
            "SELECTMAN 818+25+6 = 849 and BOARD OF HEALTH 860+15+10 = 885",
        should_be="a reparse against the document's own row semantics",
        status="",
        read="READ page 1 of data/pdfs/WestBrookfield2026.pdf (3pp, no text "
             "layer) at 150dpi. 'WEST BROOKFIELD LOCAL ELECTION / OFFICIAL "
             "RESULTS / TUESDAY, MAY 5, 2026'. SELECTMAN prints 'HENRY BROGNA "
             "818 / TOTAL WRITE IN 25' over twelve indented names (Jordan "
             "Brooks 7, Barbara Portal 2, then ten at 1) then 'BLANK 6 / "
             "Overvotes 0 / Undervotes 305 / TOTAL 1148'. BOARD OF HEALTH (3 "
             "YEARS) prints 'JASON PAQUETTE 860 / TOAL WRITE IN 15' over five "
             "names at 1, then 'BLANK 10 / Overvotes 0 / Undervotes 273 / "
             "TOTAL 1148'. COMMON COMMITTEE labels the same row 'TOTAL WRITE "
             "IN/BLANK 10' over three names at 1 and 'BLANK 7'.",
        why="The label COMMON COMMITTEE uses says what the rows mean: TOTAL "
            "WRITE IN/BLANK is write-ins PLUS blank, 3+7 = 10. So SELECTMAN's "
            "25 is its nineteen itemised write-ins plus BLANK 6, and BOARD OF "
            "HEALTH's 15 is five plus 10 -- and 818+25+305 = 1148 and "
            "860+15+273 = 1148, the TOTAL each block prints. The record maps "
            "TOTAL WRITE IN to Others and BLANK to Blanks, which counts BLANK "
            "twice and drops Undervotes entirely, so all nine contests sit "
            "hundreds short of 1,148 and no ballot count can be derived. This "
            "is a whole-record reparse against one document's row semantics, "
            "not a figure to correct, so it is yours.",
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
        print(f"filed: {spec['stem']:<20} {spec['field'][:50]}")
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
