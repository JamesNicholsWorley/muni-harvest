"""Impossible contests, worked from the largest overshoot down.

Two hundred and nine contests report more marks than ballots x seats.  Sorted by
how far over they are rather than by how many marks, the top of that list is not
noise: it is wrong seat counts, write-in aggregates counted twice, candidates
that crossed a block boundary, and one document whose rows all shifted by one.

Each row here was formed by opening the reading and doing the arithmetic
outside the model.

Run once:  python scratch/ledger_2026_09_07c.py
"""
import csv
import hashlib
import io
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")
TODAY = "2026-09-07"
ME = "civicatlas-qa (unattended run 2026-09-07)"

ROWS = [
 # ---- appliable: the write-in aggregate counted twice -------------------
 ("Hopkinton2026",
  'elections[CONSTABLE].candidates[name_original == "Others"].votes',
  "425", "46",
  "data/pdftext/Hopkinton2026.txt, from a born-digital PDF. Every block on this "
  "sheet prints Blanks, the named candidates, 'Write In', 'Scattered' and a block "
  "total, and every other block totals 966 for one seat or 1932 for two -- SELECT "
  "BOARD (1) 200 + 721 + 45 = 966, BOARD OF ASSESORS (1) 204 + 732 + 11 = 966. "
  "The CONSTABLE (1) block reads, verbatim: 'Blanks 69 108 107 88 160 532 / JASON "
  "WATSON 26 45 27 31 48 177 / DANIEL HARVEY 36 29 53 34 50 202 / Write In 70 79 "
  "90 69 117 425 / Scattered 0 0 0 0 0 0' over a total row '201 261 277 222 375 "
  "1336', against ballots of 141 188 197 161 279 = 966. Read as separate piles, "
  "precinct 1 alone would be 201 marks on 141 ballots. Read with the two names "
  "inside the 425, precinct 3 closes exactly (107 + 90 = 197) and no precinct "
  "goes over: 532 + 425 = 957 of 966.",
  "The named write-ins are inside the printed 'Write In' aggregate, so the "
  "aggregate takes the remainder: 425 - 177 - 202 = 46. Same class as Dunstable "
  "2026, Orange 2022, Pepperell 2022 and Norwood 2024, filed this session.",
  "verified"),
 ("Norwood2024",
  'elections[CONSTABLE].candidates[name_original == "Others"].votes',
  "267", "126",
  "data/pdftext/Norwood2024.txt, from a born-digital PDF. Verbatim: 'CONSTABLE - "
  "1 (1 YR TO FILL A VACANCY) / BLANKS 230 211 270 364 134 148 221 262 227 2067 / "
  "WRITE-INS 14 15 13 24 4 10 14 24 23 141 / DANIEL P. WILLIAMS 1 1 2 11 15 / "
  "SCATTERING 13 14 13 24 4 8 14 24 12 126 / TOTAL VOTE 244 226 283 388 138 158 "
  "235 286 250 2208'. 2067 + 141 = 2208 exactly, and 15 + 126 = 141 exactly: the "
  "WRITE-INS row is the subtotal of Williams and Scattering.",
  "The record's Others holds 141 + 126 = 267, the subtotal added to its own "
  "breakdown, which puts a one-seat contest 141 marks over its own printed total. "
  "With Others = 126 the block reads 15 + 126 + 2067 = 2208 exactly.",
  "verified"),
 # ---- appliable: figures the document's own columns settle ---------------
 ("Mashpee2022",
  'elections[Moderator].candidates[name_original == "Blanks"].votes',
  "1092", "377",
  "data/pdftext/Mashpee2022.txt, from a born-digital PDF. The sheet prints 'Total "
  "Turnout By Precinct 338 235 173 189 534 1469'. The Moderator block reads, "
  "verbatim: 'Moderator / Vote for 1 - 3 Years / John Miller 243 179 143 139 386 "
  "1090 / Write-Ins 2 0 0 0 0 2 / Blanks 93 56 30 50 148 1092 / Total 338 235 173 "
  "189 534 2184'. The five precinct cells on the Blanks row sum to 377, not 1092, "
  "and 1090 + 2 + 377 = 1469, which is the printed turnout. Every other block on "
  "the sheet closes on 1469 or 2938: Housing Authority 802 + 367 + 5 + 295 = 1469, "
  "Library Trustees (Vote for 2) 1033 + 417 + 722 + 4 + 762 = 2938.",
  "The document's own TOTAL column is wrong on this one row -- 1092 is Miller's "
  "1090 plus the two write-ins, printed where the blanks total belongs, and the "
  "block total 2184 carries the same error. The record copied the printed total. "
  "377 is the sum of the five printed precinct cells, computed here rather than "
  "read: 93 + 56 + 30 + 50 + 148.",
  "verified"),
 ("Dalton2021",
  'elections[SELECT BOARD].candidates[name_original == "Robert W. Bishop"].votes',
  "490", "330",
  "data/markdown/Dalton2021.md, the only reading held for this town-year, which "
  "quotes the clerk's record: 'there had been a total of 523 Ballots cast', with "
  "precinct totals of 284 and 239. Each block prints Precinct I, Precinct II and "
  "a Total. The SELECT BOARD (3 Yrs.) block carries only two of the three columns "
  "for its candidates: 'Robert W. Bishop 160 330 / John W. Roughley 77 189 / "
  "Blanks 1 1 2 / Write-ins 1 1'. Those are Precinct II and the Total: 170 + 112 "
  "+ 1 + 1 = 284 and 160 + 77 + 1 + 1 = 239, the two printed precinct totals, and "
  "330 + 189 + 2 + 2 = 523, the printed ballot count. Read as Precinct I and "
  "Precinct II instead, Bishop's 330 would exceed Precinct II's 239 ballots.",
  "The record holds 490 = 160 + 330 and 266 = 77 + 189 -- a precinct column added "
  "to the total it belongs to. TOWN CLERK on the same sheet shows the intended "
  "shape: '256 217 473', and 256 + 217 = 473.",
  "verified"),
 ("Dalton2021",
  'elections[SELECT BOARD].candidates[name_original == "John W. Roughley"].votes',
  "266", "189",
  "data/markdown/Dalton2021.md, same block as the row above: 'John W. Roughley 77 "
  "189'. 189 is the total column; 77 is Precinct II. 330 + 189 + 2 + 2 = 523, the "
  "printed ballot count.",
  "Pairs with the Bishop row: the same column added to the same total. Applying "
  "one without the other leaves the block wrong either way, so both are filed "
  "together and both are verified.",
  "verified"),
 # ---- appliable: seats up ------------------------------------------------
 ("Southbridge2023",
  'elections[School Committee].num_winners', "2", "3",
  "data/markdown/Southbridge2023.md, the only reading held. The School Committee "
  "block reads, verbatim: 'Carla Delacruz Davila 144 78 134 222 87 665 / Frank "
  "Stephen Kaitbenski 133 53 134 221 59 600 / Write-Ins 11 3 16 11 3 44 / Number "
  "of Overvotes 0 0 0 0 0 0 / Number of Undervotes 429 226 405 691 232 1983 / "
  "Total 717 360 689 1145 381 3292'. The ballot count is 1098: Board of Assessors "
  "reads 799 + 5 + 294 = 1098 and Southbridge Redevelopment Authority 794 + 3 + "
  "301 = 1098. 3292 is 1098 x 3 less two, and Councilor-At-Large, which the "
  "record already holds at three seats, prints 3293 on the same sheet -- the same "
  "shape. At two seats the block would have to be 2196, which is 1096 marks "
  "fewer than the town printed.",
  "num_winners is seats up. No 'vote for' line is printed on this sheet, so this "
  "rests on the block totals; two candidates stood, so both are elected either "
  "way and what changes is that a third seat went unfilled.",
  "verified"),
 # ---- the owner's: a candidate in the wrong block -------------------------
 ("Chelmsford2023",
  'elections[SCHOOL COMMITTEE].candidates -- two candidates belong to MODERATOR',
  "SCHOOL COMMITTEE holds Mackinnon 2262, King 2074, Kurland 2446, Latina 94, "
  "Others 32, Blanks 2256",
  "SCHOOL COMMITTEE keeps Mackinnon, King, Others 32, Blanks 2256; MODERATOR "
  "takes Kurland 2446 and gains Brian Latina 94",
  "data/pdftext/Chelmsford2023.txt, from a born-digital PDF of 'Town of "
  "Chelmsford Election / OFFICIAL Results of Local Election, April 4, 2023'. "
  "Verbatim, across the eleven precinct columns and a total: 'SUSAN M. MACKINNON "
  "... 2262 / DENNIS F. KING II Candidate for Re-election ... 2074 / Write-ins ... "
  "32 / Blanks ... 2256 / Totals 494 478 542 714 752 560 364 694 708 714 604 "
  "6624' and then 'MODERATOR - One for three years / JON H. KURLAND Candidate for "
  "Re-election ... 2446 / Brian Latina Write-in 6 23 9 9 2 10 2 5 6 20 2 94 / "
  "Write-ins ... 13 / Blanks ... 759 / Totals 247 239 271 357 376 280 182 347 354 "
  "357 302 3312'. The ballot count is 3312 (SELECT BOARD 1439 + 1433 + 167 + 146 "
  "+ 10 + 117 = 3312; BOARD OF HEALTH 2438 + 15 + 859 = 3312), and 6624 = 3312 x "
  "2 for the two-seat School Committee.",
  "Two candidates crossed a block boundary. Without them School Committee is "
  "2262 + 2074 + 32 + 2256 = 6624 exactly, and Moderator with Latina restored is "
  "2446 + 94 + 13 + 759 = 3312 exactly -- both close on the printed totals. The "
  "record's Moderator is currently 94 short and its School Committee 2540 over. "
  "Moving a candidate between contests is not something the applier does; it "
  "replaces a value it can find.",
  "needs-owner"),
 ("Royalston2021",
  'elections[ASSESSOR - 3 YEARS].candidates -- "Nancy Melbourne" belongs to the '
  "adjacent column",
  "ASSESSOR - 3 YEARS holds BLANK 103, Chase 7, Richardson 5, Nancy Melbourne "
  "103, OTHERS 6",
  "ASSESSOR - 3 YEARS without Melbourne: BLANK 103, Chase 7, Richardson 5, "
  "OTHERS 6",
  "data/pdftext/Royalston2021.txt. The sheet is printed in two columns and the "
  "extraction keeps them side by side. Verbatim: 'ASSESSOR - 3 Years - VOTE FOR "
  "ONE / BLANK 75 28 103 / Stephen Chase 6 1 7 / Jim Richardson 5 0 5 / OTHERS 5 "
  "1 6 / TOTALS 91 30 121', and in the right-hand column of the same rows "
  "'TRUSTEES OF THE J.N.. BARTLETT FUND - 1 YEAR - VOTE FOUR / Curtis Deveneau 74 "
  "25 99 / Nancy Melbourne 78 25 103 / Gary Winitzer 53 17 70 / BLANK 152 48 200 "
  "/ OTHERS 7 5 12 / TOTALS 364 120 484'. 103 + 7 + 5 + 6 = 121, the printed "
  "TOTALS row and the ballot count.",
  "Melbourne is in the record twice: correctly in the Bartlett Fund contest with "
  "103, and again in the Assessor contest beside it, which is what puts a "
  "one-seat contest at 224 marks on 121 ballots. Removing a candidate is not "
  "something the applier does. The two-column layout is the cause, so it is worth "
  "asking what else this document lost across the gutter.",
  "needs-owner"),
 ("Hancock2025",
  'elections[Cemetery Comm] -- two contests are fused into one',
  "one contest: Cassavaugh 118, Rancourt 1, Quimby 1, Morin 1, Blanks 126",
  "two contests, each closing on 128: Cassavaugh 118 + write-in 1 + blanks 9, "
  "and the vacant position, write-ins 2 + blanks 126",
  "data/markdown/Hancock2025.md, the only reading held, which is a table of the "
  "town's own results headed 'Annual Town Election / Results  128 Voters'. The "
  "Cemetery rows read, verbatim: '| Lydia Cassavaugh | Cemetery Comm | 118 | 9 | "
  "None |', '| Write In Justin Rancourt | Cemetery Comm | None | None | 1 |', '| "
  "Vacant Cemetery Position | Cemetery Comm | None | 126 | None |', '| Write In "
  "John Quimby | Cemetery Comm | 1 | None | None |', '| Jan Lillie Morin | "
  "Cemetery Comm | 1 | None | None |'. 118 + 9 + 1 = 128 and 126 + 1 + 1 = 128, "
  "each exactly the stated 128 voters.",
  "A fused race, which no ballots-times-seats check can see: the merged block "
  "closes on 128 x 2 as neatly as two blocks close on 128 each. The document says "
  "there are two, and names the second 'Vacant Cemetery Position'. Splitting a "
  "contest is the owner's.",
  "needs-owner"),
 ("Bellingham2022",
  "the whole record -- rows are shifted by one in four of seven contests",
  "PLANNING BOARD: Devine 318, Mobilia 345, Others 208, Blanks 1156",
  "PLANNING BOARD: Devine 318, Elizabeth Berthelette 282, Mobilia 345, Others 3, "
  "Blanks 208 -- and the same shift undone in SELECTMAN, CONSTABLE and SCHOOL "
  "COMMITTEE",
  "Both pages of Bellingham2022.pdf rendered at 150dpi (the raw_ocr of this scan "
  "is mirrored and unusable). Page 2, verbatim: 'PLANNING BOARD / 2 to be elected "
  "- for 3 years / Philip M. Devine 55 63 63 74 63 318 / Elizabeth Berthelette 48 "
  "55 51 69 59 282 / Nick Mobilia 42 67 73 107 56 345 / Write Ins 0 0 3 0 0 3 / "
  "Blanks 27 45 42 56 38 208 / Totals 172 230 232 306 216 1,156'. Also on page 2: "
  "'SCHOOL COMMITTEE / 2 to be elected - for 3 years / Jennifer L. Altomonte 424 "
  "/ Michael J. Reed, Jr. 400 / Write Ins 5 / Blanks 327 / Totals 1,156'. Page 1: "
  "'SELECTMAN - for 3 years / 1 to be elected / Sahan Sahin 414 / Write ins 13 / "
  "Blanks 151 / TOTAL 578' and 'CONSTABLE / 4 to be elected - for 3 years / David "
  "H. Brown 357 / Richard J. Martinelli 391 / William H. Paine 386 / William L. "
  "Roberts, Sr. 362 / Write Ins 3 / Blanks 813 / TOTAL 2,312'.",
  "Four contests are shifted one row: the block total lands in Blanks, the blanks "
  "in Others, and in PLANNING BOARD a candidate is lost off the top (Elizabeth "
  "Berthelette, 282). CONSTABLE carries num_winners 8 where the page says 'to be "
  "elected 4', SCHOOL COMMITTEE carries 4 where the page says 2, and its "
  "Altomonte is split across two rows ('Altomonte' 424 and 'Jennifer L.' 5). "
  "SELECTMAN even closes -- Others 8 and Blanks 156 sum to the same 164 as the "
  "printed 13 and 151 -- which is why only Planning Board shows up as impossible. "
  "This is a reparse of one document, which is the owner's, and it is worth doing "
  "because the page itself is clean and legible at 150dpi.",
  "needs-owner"),
]


def sha(stem):
    p = os.path.join(BASE, "data", "pdfs", stem + ".pdf")
    if not os.path.exists(p):
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    for stem, field, was, should, read, why, status in ROWS:
        rows.append({"stem": stem, "source_sha256": sha(stem), "field": field,
                     "was": was, "should_be": should, "read": read, "why": why,
                     "status": status, "decided_by": ME, "decided_on": TODAY,
                     "applied_on": ""})
    with io.open(LEDGER, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"{len(ROWS)} rows appended; ledger now {len(rows)} rows")


main()
