"""Record what this session read off the pages, in the form the applier can use.

Every row here was formed by rendering the page and reading it.  The earlier
rows said the same things in prose -- "null (ballots_cast_source: cannot_derive)"
in `was`, "829, from the figure printed on the document" in `should_be` -- and
the applier addresses a correction by searching the record for the value being
replaced, so prose could never locate anything.  This rewrites `was` and
`should_be` as the bare values and puts this session's own reading in `read`.

Run once:  python scratch/ledger_2026_09_07.py
"""
import csv
import hashlib
import io
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")
TODAY = "2026-09-07"
ME = "civicatlas-qa (unattended run 2026-09-07)"


def sha(stem):
    p = os.path.join(BASE, "data", "pdfs", stem + ".pdf")
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# (index in the ledger or None to append, stem, field, was, should_be, read, why, status)
R = []


def row(idx, stem, field, was, should, read, why, status="verified"):
    R.append((idx, stem, field, was, should, read, why, status))


# ---- ballots cast, each read off the page this session -------------------
B = [
    (74, "Provincetown2026", "829",
     "Page 1 of Provincetown2026.pdf rendered with PyMuPDF at 150dpi and the "
     "header re-cropped at 300dpi. Verbatim: 'May 12, 2026' / 'Offical Election "
     "Results' / 'Total Registered voter 3486' / 'Total Ballots Cast 829' / "
     "'Voter Turnout 23.78%'. 829/3486 = 23.78%."),
    (75, "Palmer2025", "358",
     "Page 1 of Palmer2025.pdf at 150dpi. Foot of the sheet, verbatim: 'Total # "
     "of Voters: 103 99 81 75 358' and 'Percentage of Voters that Voted: 3.5%', "
     "over 'Susan M. Coache June 11, 2025 / Palmer Town Clerk'. 103+99+81+75=358. "
     "'Councilor at Large -3 year term' closes on it: 15+211+85+47 = 358."),
    (76, "Petersham2021", "120",
     "Page 1 (the only page) of Petersham2021.pdf at 150dpi. Heading 'ANNUAL TOWN "
     "ELECTION MAY 17, 2021'; at the foot, verbatim: '12% voter turnout' and '120 "
     "voters voted out of 989'. The largest single-seat figure on the page is TOWN "
     "CLERK 'Diana L. Cooley 117', under 120."),
    (77, "Hinsdale2023", "60",
     "Page 1 (the only page) of Hinsdale2023.pdf at 150dpi, a marked-up 'Annual "
     "Town Election / Hinsdale, Massachusetts / May 13, 2023' ballot with every "
     "figure written in by hand. Hand-written at the lower right, verbatim: '1468 "
     "- Registered Voters' and '60 - Ballots Cast'. 'FINANCE COMMITTEE - 3 years / "
     "Vote for Three' reads 49 + 48 + 49 = 146, under 60 x 3."),
    (110, "Wilmington2022", "638",
     "Page 1 (the only page) of Wilmington2022.pdf at 160dpi. 'TOTAL TALLY SHEET - "
     "CERTIFIED RESULTS / TOWN OF WILMINGTON - ANNUAL TOWN ELECTION / 23-Apr-22'. "
     "Foot of the sheet, verbatim: 'Total Voters 3052 2975 2862 3025 2969 2982 "
     "17865' / 'TOTAL VOTES 96 129 66 125 122 100 638' / 'TURNOUT ... 3.57%'. Each "
     "block also prints 'Total Ballots 95 130 66 125 122 100', which sums to 638."),
    (183, "Norton2026", "1232",
     "Page 3 of Norton2026.pdf at 200dpi. Heading 'ANNUAL TOWN ELECTION 04 - 11 - "
     "2026 OFFICIAL RESULTS'; columns 'TAPE COUNTS BY PRECINCT 1 2 3 4 5', 'HAND "
     "COUNT TOTALS', 'PROVISIONAL BALLOTS', 'TOTAL BALLOTS'. The TOTALS row reads "
     "294 231 243 275 182 | 5 | 2 | 1232. BOARD OF ASSESSORS closes on it: 787 + "
     "432 + 13 = 1232; MODERATOR 879 + 340 + 13 = 1232."),
    (185, "Wales2026", "64",
     "The single page of Wales2026.pdf at 160dpi: an 'OFFICIAL BALLOT / ANNUAL "
     "TOWN ELECTION / WALES, MASSACHUSETTS / MAY 27, 2026' with the tallies and "
     "the blanks written on it by hand, '>5% VOTER TURNOUT' across the foot. No "
     "ballot count is printed. Nine single-seat blocks each sum to 64: SELECTMEN "
     "54 + write-in 2 + blank 8; ASSESSORS 1 YEAR 53 + 2 + 9; ASSESSORS 3 YEAR 61 "
     "+ 0 + 3; LIBRARY TRUSTEE 55 + 3 + 6; SCHOOL COMMITTEE 5 + 59; CONSTABLE 60 + "
     "0 + 4; BOARD OF HEALTH 59 + 1 + 4; CEMETERY 58 + 1 + 5; PLANNING BOARD 2 "
     "YEAR 5 + 59. 'PLANNING BOARD MEMBER / 3 YEAR TERM / VOTE FOR TWO' reads 57 + "
     "53 + 1 + 17 = 128 = 64 x 2."),
    (181, "Wales2022", "86",
     "The single page of Wales2022.pdf at 160dpi: an 'ABSENTEE OFFICIAL BALLOT / "
     "ANNUAL TOWN ELECTION / WALES, MASSACHUSETTS / MAY 25, 2022' used as the "
     "tally sheet, figures written on it in red marker. Written across the foot in "
     "black, verbatim: 'OFFICIAL RESULTS' and '86 VOTERS'. The largest figures on "
     "the page are TOWN CLERK 77 and CEMETERY COMMISSIONER 77, under 86."),
    (197, "NorthBrookfield2021", "630",
     "Page 1 of NorthBrookfield2021.pdf at 160dpi: an 'OFFICIAL BALLOT / ANNUAL "
     "TOWN ELECTION / NORTH BROOKFIELD, MASSACHUSETTS / MAY 3, 2021' with the "
     "results written on it in ink and '17% Voter Turnout' at the top right. No "
     "ballot count is printed. Eleven single-seat blocks each sum to 630: SELECTMAN "
     "454 + 176; ASSESSORS 481 + 149; PLANNING BOARD 429 + 201; WATER 3 YEARS 498 + "
     "132; WATER 2 YEARS 497 + 133; BOARD OF HEALTH 349 + 211 + 70; PLAYGROUND 494 "
     "+ 136; HOUSING AUTHORITY 12 + 618; SWCRVSD 489 + 141; CEMETERY 29 + 601. "
     "SCHOOL COMMITTEE (VOTE FOR TWO) 287 + 328 + 325 + 162 + 158 = 1260 = 630 x 2; "
     "LIBRARY TRUSTEES (VOTE FOR THREE) 463 + 462 + 509 + 456 = 1890 = 630 x 3."),
    (198, "NorthBrookfield2023", "662",
     "Page 1 of NorthBrookfield2023.pdf at 160dpi: an 'OFFICIAL BALLOT / ANNUAL "
     "TOWN ELECTION / NORTH BROOKFIELD, MASSACHUSETTS / MAY 1, 2023', tallies "
     "written on it in red. No ballot count is printed. Single-seat blocks each sum "
     "to 662: SELECTMAN 420 + 242; ASSESSORS 501 + 161; PLANNING BOARD 398 + 264; "
     "WATER 497 + 165; BOARD OF HEALTH 358 + 281 + 23; CEMETERY 526 + 136; SWCRVSD "
     "530 + 132; CONSTABLE 492 + 170; SCHOOL COMMITTEE 2 YEARS 397 + 265; SCHOOL "
     "COMMITTEE 1 YEAR 422 + 240; each of the three PLAYGROUND COMMITTEE blocks is "
     "a bare write-in figure of 662. The three two-seat blocks each read 1324 = 662 "
     "x 2 (School Committee 373 + 386 + 565; Library Trustees 484 + 413 + 427; "
     "Housing Authority 492 + 476 + 356)."),
    (206, "Harwich2023", "1959",
     "data/pdftext/Harwich2023.txt, extracted from a born-digital PDF. Verbatim: "
     "'Total Registered Voters 3228 2819 2763 2697 11507' / 'Total Voter Turnout "
     "645 549 414 351 1959' / 'Percentage 17.02%'. The three ballot questions each "
     "total 1959; the four 'Vote for not more than TWO' blocks each total 3918 = "
     "1959 x 2."),
    (207, "Eastham2025", "569",
     "data/pdftext/Eastham2025.txt, from a born-digital PDF. 'TOWN OF EASTHAM / "
     "TOWN ELECTION FINAL RESULTS / May 20, 2025'. No ballot count is printed. "
     "'NAUSET REGIONAL SCHOOL COMMITTEE' reads 'Moira Noonan-Kerry 495 / Blanks 74 "
     "/ TOTAL 569', and QUESTION 1 (404 + 149 + 16) and QUESTION 2 (494 + 57 + 18) "
     "each print 'TOTAL 569'. The three '(vote for two)' blocks each print 'TOTAL "
     "1138' = 569 x 2."),
    (208, "Harvard2026", "563",
     "data/pdftext/Harvard2026.txt, from a born-digital PDF. Verbatim: 'MAY 5th, "
     "2026 ANNUAL TOWN ELECTION / OFFICIAL TABULATION OF RESULTS FOR HARVARD / "
     "TOTAL BALLOTS CAST 563 / REGISTERED VOTERS 4849 / TURNOUT 11.61%'. Each "
     "'Vote TWO' block prints a total of 1126 = 563 x 2; QUESTION 1 and QUESTION 2 "
     "each print 563."),
    (215, "Chicopee2025", "6366",
     "Page 1 of Chicopee2025.pdf rendered at 200dpi (the OCR of this scan does not "
     "carry the figure). Header block, verbatim: 'SUMMARY REPORT' / 'City of "
     "Chicopee / Municipal Election / November 4, 2025' / 'PRECINCTS COUNTED (OF "
     "21) . 21 100.00' / 'REGISTERED VOTERS - TOTAL . 0' / 'BALLOTS CAST - TOTAL. "
     ". 6,366' / 'BALLOTS CAST - BLANK. . 1 .02'."),
    (223, "Methuen2021", "4073",
     "Page 1 of Methuen2021.pdf at 200dpi, read in two crops. Heading 'CERTIFIED "
     "ELECTION RESULTS / NOVEMBER 2, 2021 MUNICIPAL ELECTION - METHUEN, MA'. The "
     "turnout block reads 'Eligible Voters 2,827 2,284 ... 36,762' and 'Total "
     "Voters on Nov. 2, 2021 318 88 266 261 220 316 359 630 367 311 559 378 4,073' "
     "with 'Percentage Turnout 11%'. The MAYOR block prints 'Total VOTES Cast "
     "4,073' and 'Total BALLOTS Cast 4,073', and closes: 3,378 + 120 + 575 = 4,073."),
    (224, "Billerica2025", "4781",
     "Page 1 of Billerica2025.pdf at 120dpi (the tables are drawn sideways on a "
     "portrait page and read turned). 'TOWN OF BILLERICA / OFFICIAL ELECTION "
     "RESULTS / TOWN ELECTION / April 5, 2025'. Top right, verbatim: '# Registered "
     "Voters 31,895 / Total Votes Cast 4,781 / Percent 15%', and the 'Total Votes "
     "Cast' row across the twelve precincts carries a GRAND TOTAL of 4781. The "
     "seat count is printed in each heading: 'SELECT BOARD - 3 YR (2)' totals 9562 "
     "= 4781 x 2, 'PLANNING BOARD - 3 YR (3)' totals 14343 = 4781 x 3."),
    (225, "Attleboro2021", "6920",
     "Page 1 of Attleboro2021.pdf at 150dpi. 'Election Summary Report / General "
     "Election / ATTLEBORO / November 02, 2021 ... Unofficial Results City Wide'. "
     "Verbatim: 'Precincts Reported: 12 of 12 (100.00%)' / 'Registered Voters: "
     "6,920 of 31,523 (21.95%)' / 'Ballots Cast: 6,920'. The MAYOR block repeats it "
     "as 'Times Cast 6,920'."),
    (226, "Beverly2021", "8442",
     "Page 1 of Beverly2021.pdf at 130dpi. 'November 2, 2021 / CITY OF BEVERLY, "
     "MASSACHUSETTS / MUNICIPAL ELECTION / OFFICIAL RESULTS', stamped 'NOV 12 2021 "
     "A TRUE COPY ATTEST: Lisa E Kent, City Clerk'. No ballot count is printed. The "
     "single-seat MAYOR block prints its own total: 'Michael P. Cahill 5,904 / "
     "Esther W. Ngotho 2,258 / All Others 114 / Blank 166 / Total 8,442'."),
    (229, "Billerica2021", "3715",
     "Page 1 of Billerica2021.pdf at 150dpi. 'Statement of Votes Cast / ANNUAL TOWN "
     "ELECTION / BILLERICA, MA / SOVC For Jurisdiction Wide, All Counters, All "
     "Races / APRIL 10, 2021 / OFFICIAL RESULTS'. The TURN OUT block prints 'Reg. "
     "Voters 29301 | Cards Cast 3715 | % Turnout 12.68%' on its Total row, over "
     "eleven precinct rows that sum to it."),
    (238, "Northampton2023", "5450",
     "Page 6 of Northampton2023.pdf at 130dpi (Page rot 270; rendered upright). "
     "'SCHOOL COMMITTEE AT LARGE (vote for 2)' prints a 'TOTAL BALLOTS CAST' row "
     "across the fourteen ward columns 1A 1B 2A 2B 3A 3B 4A 4B 5A 5B 6A 6B 7A 7B: "
     "287 497 356 276 380 388 227 473 391 507 374 448 423 423, Totals 5,450. The "
     "block itself totals 10,900 = 5,450 x 2."),
    (289, "Alford2025", "54",
     "Page 1 of Alford2025.pdf (Page rot 270) rendered upright at 170dpi. Heading "
     "'COMMONWEALTH OF MASSACHUSETTS / Town of Alford's Annual Town Election May "
     "20, 2025 / TOWN HALL 5 ALFORD CENTER ROAD---VOTING HOURS 12PM TO 6PM / "
     "UNOFFICIAL BALLOT COUNT-----TOWN CLERK'. Hand-written at the right, verbatim: "
     "'Total Ballots 54 / In Person 53 / Absentee Voter 1'. 'Planning Board Three "
     "Years Vote for 2' reads 45 + 49 = 94, under 54 x 2."),
    (313, "Blandford2025", "156",
     "Blandford2025.pdf is the 47-page 'Annual Town Report'. PDF page 40 (printed "
     "page 39, under the ADDENDA divider on page 39) is headed 'Local Election "
     "Results 2025' and its first line reads, verbatim: 'There were 156 ballots "
     "cast in the June 14, 2025 town election.' Read at 150dpi."),
    (71, "Worcester2021", "17326",
     "Page 1 of Worcester2021.pdf at 170dpi, left column. Verbatim: 'SUMMARY "
     "REPORT' / 'OFFICIAL ELECTION RESULTS' / 'MUNICIPAL ELECTION 11/02/2021' / "
     "'REPORT-EL45 PAGE 001' / 'PRECINCTS COUNTED (OF 50) . 50 100.00' / "
     "'REGISTERED VOTERS - TOTAL . 104,595' / 'BALLOTS CAST - TOTAL. 17,326' / "
     "'BALLOTS CAST - BLANK. 8 .05' / 'VOTER TURNOUT - TOTAL 16.56'. MAYOR (VOTE "
     "FOR) 1 closes on it: 10,100 + 4,153 + 1,513 + 933 + 627 blanks = 17,326."),
]
for idx, stem, val, read in B:
    row(idx, stem, "ballots_cast", "None", val, read,
        "The document states the ballot count and the record holds null. Re-read "
        "this session; `was` and `should_be` rewritten as bare values so the "
        "applier can locate the field. NOTE: ballots_cast_source still reads "
        "'cannot_derive' and the applier has no route to that field.")

# ---- write-in aggregate counted twice ------------------------------------
row(324, "Dunstable2026",
    'elections[Constable].candidates[name_original == "Others"].votes',
    "88", "24",
    "data/pdftext/Dunstable2026.txt, from a born-digital PDF, verbatim: "
    "'Constable - One Year - Chose 2  Totals / Steven C. Tully 493 / Write-Ins 64 "
    "/ Jon Crandall 40 / Scattered 24 / Blanks 658 / Totals 1215'. The 'Write-Ins "
    "64' row is the subtotal of the two rows under it: 40 + 24 = 64, and 493 + 64 "
    "+ 658 = 1215, the printed total. The record's 'Others' holds 64 + 24 = 88, "
    "the subtotal added to its own breakdown.",
    "Keep the named write-in and give the aggregate the remainder. With Others = "
    "24 the block reads 493 + 40 + 24 + 658 = 1215, the town's own printed total.")
row(None, "Dunstable2026",
    'elections[Board of Library Trustees].candidates[name_original == "Others"].votes',
    "111", "45",
    "data/pdftext/Dunstable2026.txt, verbatim: 'Board of Library Trustees - Three "
    "Years  Totals / Write-Ins 66 / Tarra Hammond 21 / Scattered 45 / Blanks 545 / "
    "Totals 611'. 21 + 45 = 66, and 66 + 545 = 611, the printed total. The record's "
    "'Others' holds 66 + 45 = 111.",
    "Same class as the Constable row on this document: the printed write-in "
    "subtotal was added to its own breakdown.")
row(325, "Orange2022",
    'elections[Elem. School Comm. 3 yr.].candidates[name_original == "Others"].votes',
    "19", "4",
    "data/pdftext/Orange2022.txt, from a born-digital PDF, verbatim: 'Elem. School "
    "Comm. 3 yr. 3 / Malory L. Ellis 86 93 179 / Write-in 3 12 15 / Katie Hunkler "
    "*Did Not Accept 0 11 11 / Others 3 1 4 / Blanks 232 267 499'. 'Write-in 15' is "
    "the subtotal of Hunkler 11 and Others 4. The document also prints 'Total Voted "
    "107 124 231'; with Others = 4 the block reads 179 + 11 + 4 + 499 = 693 = 231 x "
    "3 exactly, where the heading's '3' is the seat count.",
    "The record's 'Others' holds 15 + 4 = 19, the subtotal added to its own "
    "breakdown, which puts the block 15 marks over 231 x 3.")
row(None, "Orange2022",
    'elections[Cemetery Commissioner].candidates[name_original == "Others"].votes',
    "54", "10",
    "data/pdftext/Orange2022.txt, verbatim: 'Cemetery Commissioner 1 / Write-in 16 "
    "28 44 / Glen Harris *Accepted 10 7 17 / Harold Vielleux 5 10 15 / Others 1 9 "
    "10 / Blanks 91 96 187'. The record's 'Others' holds 44 + 10 = 54. The town's "
    "own breakdown is short of its subtotal by 2 in precinct 2 (7 + 10 + 9 = 26 "
    "against a printed 28); precinct 1 reconciles exactly (10 + 5 + 1 = 16).",
    "Others takes the printed figure 10, not the remainder 12 -- the page prints "
    "an Others row and a transcription copies what is printed. The 2-mark gap is "
    "the town's own and shows as tally_incomplete, which is the right verdict.")
row(87, "Pepperell2022",
    'elections[Select Board].candidates[name_original == "Others"].votes',
    "428", "1",
    "data/pdftext/Pepperell2022.txt, from a born-digital PDF, verbatim: 'Vote for "
    "One (3 years) Select Board Prec. 1 Prec. 2 Prec. 3 Prec. 4 Totals / Charles "
    "Walkovich 100 194 197 112 603 / Write-ins 116 132 124 56 428 / Caroline Ahdab "
    "116 132 124 55 427 / Provisional 0 0 0 0 0 / Blanks 35 34 42 21 132 / Totals "
    "251 360 363 189 1163'. 603 + 428 + 132 = 1163, the printed total, so the "
    "'Write-ins 428' row contains Ahdab's 427.",
    "Keep the name and give the aggregate the remainder: Others = 428 - 427 = 1. "
    "The record counts Ahdab alongside the full 428, which puts a one-seat contest "
    "427 marks over its own printed total.")
row(None, "Pepperell2022",
    'elections[Recreation Commission].candidates[name_original == "Others"].votes',
    "123", "69",
    "data/pdftext/Pepperell2022.txt, verbatim: 'Recreation Commission Prec. 1 Prec. "
    "2 Prec. 3 Prec.4 Totals / Write-ins 24 47 30 22 123 / Shaun Shattuck 10 25 10 "
    "6 51 / Caroline Ahdab 3 3 / Provisional 0 0 0 0 0 / Blanks 227 313 333 167 "
    "1040 / Totals 251 360 363 189 1163'. 123 + 1040 = 1163, the printed total.",
    "Same class as the Select Board row on this document. Others = 123 - 51 - 3 = "
    "69.")
row(53, "Norton2021",
    'elections[Planning Board].candidates[name_original == "Others"].votes',
    "511", "195",
    "Page 1 of Norton2021.pdf at 150dpi (printed page '186'), verbatim: 'TOWN OF "
    "NORTON / RECORD OF / Annual Town Election / OFFICIAL RESULTS / Saturday, April "
    "10, 2021'; the Planning Board block reads 'Blanks 1444 1280 1089 1373 859 "
    "6045 / Write Ins 134 120 67 93 97 511' over a total row '1578 1400 1156 1466 "
    "956 6556'. 6045 + 511 = 6556. Page 2 (printed '187') is headed 'WRITE INS' and "
    "breaks the 511 down: 'Planning Board / Wayne Graff 20 23 15 13 23 94 / Allen "
    "Bouley 62 48 27 20 24 181 / Michael Conroy 3 9 4 7 18 41 / 85 80 46 40 65 316'.",
    "The three named write-ins are inside the 511, so the aggregate takes the "
    "remainder 511 - 316 = 195. The record counts them alongside the full 511. "
    "See also the Planning Board seat-count row filed this session: the block "
    "closes on 3278 x 2, not x 1.")

# ---- figures read off the page -------------------------------------------
row(67, "Salem2023",
    'elections[2023-05-16 MAYOR].candidates[name_original == "NEIL J. HARRINGTON"].votes',
    "4300", "4390",
    "Page 2 of Salem2023.pdf (Page rot 270) rendered upright at 150dpi. Heading "
    "verbatim: 'CITY OF SALEM / MAYORAL SPECIAL / FINAL ELECTION / MAY 16, 2023 / "
    "OFFICIAL RESULTS', left margin 'TO FILL THE VACANCY OF THE MAYOR FOR THE "
    "REMAINDER OF THE TERM 1ST MONDAY IN 2026', top right 'Registered Voters: "
    "32,915 / % of Turnout: 28%'. The MAYOR rows, with the TOTALS column: 'BLANKS "
    "20 / DOMINICK PANGALLO 4827 / NEIL J. HARRINGTON 4390 / WRITE-INS 2 / ROBERT "
    "K. MCCARTHY 6'.",
    "A figure, re-read this session at 150dpi. The record's 4300 is not what the "
    "page prints. Whether this contest belongs in the annual Salem2023 slot at all "
    "is a separate open question for the owner (row 1 of this ledger); the figure "
    "travels with the contest either way.")
row(None, "Salem2023",
    'elections[2023-05-16 MAYOR].candidates[name_original == "ROBERT K. MCCARTHY"].votes',
    "1", "6",
    "Page 2 of Salem2023.pdf at 150dpi, same block as above: 'ROBERT K. MCCARTHY 5 "
    "0 0 0 0 0 0 1 0 0 0 0 0 0' across the fourteen ward-precinct columns, TOTALS "
    "6. The separate 'WRITE-INS' row totals 2, so McCarthy is a named write-in line "
    "beside the scattered total, not inside it.",
    "A figure, re-read this session. The record holds 1, which is one of "
    "McCarthy's precinct figures rather than his total.")
row(None, "Provincetown2026",
    'elections[Select Board].candidates[name_original == "Austin Douglas Miller"].votes',
    "564", "584",
    "Page 1 of Provincetown2026.pdf at 150dpi, and the Select Board block "
    "re-cropped at 300dpi to be sure of the digit. Verbatim: 'Select Board / Austin "
    "Douglas Miller - Elect 584 / Austin Phillip Knight 244 / Dana L. Masterpolo - "
    "Elect 615 / Write In 15'. Highlighted rows carry '- Elect'.",
    "A figure read off the page while confirming this record's ballot count. The "
    "record holds 564.")
row(117, "Holland2023",
    'elections[Water Commissioner].candidates[name_original == "Anthony Landers"].votes',
    "None", "8",
    "Page 1 (the only page) of Holland2023.pdf at 150dpi: an 'ANNUAL TOWN ELECTION "
    "/ OFFICIAL BALLOT / HOLLAND, MASSACHUSETTS / June 13, 2023', signed 'Valerie "
    "Lundin, Town Clerk', with 'OFFICIAL ELECTION RESULTS 6/13/23' and 'VOTERS: "
    "217' written on it. Every block carries its figure written beside the office "
    "heading; the Water Commissioner block reads 'Water Commissioner / 3 year term "
    "[8] Vote for One' with 'ANTHONY LANDERS' written across the WRITE-IN SPACE "
    "ONLY line.",
    "The figure is on the page. NOT APPLIABLE AS FILED: the applier locates a "
    "correction by searching the record for the value being replaced, and this "
    "record holds two nulls -- this candidate's votes and ballots_cast -- so 'None' "
    "matches twice and it refuses. Needs the owner, or a way to address a field "
    "directly.", "needs-owner")
row(None, "Holland2023", "ballots_cast", "None", "217",
    "Page 1 of Holland2023.pdf at 150dpi. Hand-written at the foot, verbatim: "
    "'VOTERS: 217', beside 'OFFICIAL ELECTION RESULTS 6/13/23' and a second Town "
    "Clerk signature. The Selectboard block reads 'Kate Landers 122 / Timothy West "
    "93' = 215, under 217.",
    "Same blocker as the Water Commissioner row above: two nulls in one record, so "
    "'None' cannot address either of them. If the owner fixes one by hand the other "
    "becomes appliable.", "needs-owner")
row(None, "Holland2023",
    'elections[Treasurer].candidates[name_original == "Sharon Ashleigh"].votes',
    "172", "178",
    "Page 1 of Holland2023.pdf, Treasurer block re-cropped at 400dpi to be sure of "
    "the digit. Verbatim: 'Treasurer / 1 year remaining term  Vote for One' with "
    "'178' written above the line and 'Sharon Ashleigh 4 Lakeview Drive' under it. "
    "Every other figure on this page matches the record: Landers 122, West 93, "
    "Julian 175, Furst 182 and 176, Johnson 151 and 153, Mott 180, Alden 172, Iller "
    "172, Anderstrom 175, Gillen 169.",
    "Found while confirming the Water Commissioner figure. NOT APPLIABLE AS FILED: "
    "three candidates in this record hold 172 (Alden, Iller, Ashleigh), so the "
    "applier cannot tell which one the row means.", "needs-owner")
row(115, "Granville2023",
    'elections[Library Trustee].candidates[name_original == "Jennifer M. Kinsman"].votes',
    "143", "148",
    "Page 1 (the only page) of Granville2023.pdf at 150dpi, the Library Trustee "
    "block re-cropped at 400dpi. Verbatim: 'One Library Trustee for 3 years / Vote "
    "for ONE / Jennifer M. Kinsman 148 / Write in 0 / Blank 20' with '168' written "
    "under the block, which is the ballot count this hand-annotated ballot carries "
    "under every contest. The record holds Kinsman 143 and Blanks 25, which also "
    "sums to 168, so the arithmetic could never have caught it. The names this row "
    "was originally filed for -- 'Emily Bouwer' and 'Mario Langlois' -- are printed "
    "in the write-in list on the same page and the record already holds both "
    "spellings correctly, so that part of the row is satisfied.",
    "This row is now the figure correction, and it must move as a PAIR: Kinsman 143 "
    "-> 148 and Library Trustee Blanks 25 -> 20. Applying either alone leaves the "
    "block summing to 163 instead of 168. NOT APPLIABLE AS FILED: the record holds "
    "143 twice (Moderator Pierce and Kinsman), so the applier cannot locate it, and "
    "the blanks half is deliberately not filed on its own.", "needs-owner")
row(None, "Granville2023",
    'elections[Tax Collector].candidates -- a write-in printed on the page is not in the record',
    "Mary Beth Sussmann 154, Laura Burnett 1, Blanks 12",
    "the same three plus Sue Tenerowicz 1",
    "Page 1 of Granville2023.pdf at 150dpi, verbatim: 'One Tax Collector for 3 "
    "years / Vote for ONE / Mary Beth Sussmann 154 / Write in Laura Burnett 1 / "
    "Blank 12 / Sue Tenerowicz 1' with '168' written under the block. The record "
    "holds the first three and sums to 167.",
    "A lost name, of the class the arithmetic cannot see. Adding a candidate is not "
    "something the applier does -- it replaces a value it can find -- so this needs "
    "the owner.", "needs-owner")
row(70, "Worcester2021",
    'candidates[].name_original == "DONNA M. COLORID" (MAYOR and COUNCILLOR AT LARGE)',
    "DONNA M. COLORID", "DONNA M. COLORIO",
    "Page 1 of Worcester2021.pdf at 170dpi. MAYOR (VOTE FOR) 1 reads 'JOSEPH M. "
    "PETTY 10,100 60.48 / DONNA M. COLORIO 4,153 24.87 / BILL COLEMAN 1,513 9.06 / "
    "PETER A. STEFAN 933 5.59'; COUNCILOR AT LARGE (VOTE FOR) 6 reads 'DONNA M. "
    "COLORIO 7,285 10.76'. The SCHOOL COMMITTEE MEMBER (VOTE FOR) 6 block reads "
    "'JERMAINE L. JOHNSON 8,908 / SUSAN M. MAILMAN 8,879 / MOLLY O. MCCULLOUGH "
    "8,197 / TRACY O'CONNELL NOVICK 8,022 / JERMOH V. KAMARA 8,001 / LAURA B. "
    "CLANCEY 6,911 / DIANNA L. BIANCHERIA 6,132 / SHANEL C. SOUCY 5,085 / Total "
    "60,135 / Blank Votes 43,821' -- so the other three names this row was filed "
    "for (MAILMAN, SOUCY, KAMARA) are already right in the record.",
    "Only COLORID is still wrong. NOT APPLIABLE AS FILED: the same misreading "
    "appears in two contests, and the applier refuses a value it finds twice rather "
    "than guess which one is meant.", "needs-owner")

# ---- seats up ------------------------------------------------------------
row(None, "Norton2021",
    'elections[Select Board].num_winners', "3", "2",
    "Page 1 of Norton2021.pdf at 150dpi (printed page '186'). The Select Board "
    "block reads 'Blanks 533 440 343 472 312 2100 / Megan A. Artz 431 357 340 377 "
    "214 1719 / Christine Ann Deveau 322 295 283 341 211 1452 / Frank J. Parker, "
    "III 288 300 180 268 213 1249 / Write Ins 4 8 6 12 6 36' over a total row '1578 "
    "1400 1152 1470 956 6556'. The document prints no 'vote for' line anywhere. "
    "The Board of Assessors block totals 3278 on the same precinct columns, which "
    "is the ballot count; 2100 + 1719 + 1452 + 1249 + 36 = 6556 = 3278 x 2 exactly. "
    "At three seats the block would be 3278 marks short of 9834, and the printed "
    "blanks figure would have to be 5378 rather than 2100.",
    "num_winners is seats up and it decides who won: at two seats Parker (1249) "
    "does not take one. No printed seat count outranks this, so it rests on the "
    "arithmetic and on the town's own printed block total.")
row(None, "Norton2021",
    'elections[Planning Board].num_winners', "1", "2",
    "Page 1 of Norton2021.pdf at 150dpi. The Planning Board block reads 'Blanks "
    "1444 1280 1089 1373 859 6045 / Write Ins 134 120 67 93 97 511' over a total "
    "row '1578 1400 1156 1466 956 6556'. The blanks alone (6045) exceed the ballot "
    "count (3278), which is impossible at one seat whatever the write-ins are, and "
    "6045 + 511 = 6556 = 3278 x 2.",
    "NOT APPLIABLE AS FILED: four contests in this record hold num_winners == 1, "
    "so the applier cannot tell which one the row means. Pairs with the Planning "
    "Board write-in row above.", "needs-owner")
row(None, "Provincetown2026",
    'elections[Select Board].num_winners', "1", "2",
    "Page 1 of Provincetown2026.pdf at 150dpi and 300dpi. The Select Board block "
    "reads 'Austin Douglas Miller - Elect 584 / Austin Phillip Knight 244 / Dana L. "
    "Masterpolo - Elect 615 / Write In 15'; two of the three carry '- Elect' and "
    "are highlighted, as every winner on this sheet is. The header prints 'Total "
    "Ballots Cast 829'. 584 + 244 + 615 + 15 = 1458, which is impossible at one "
    "seat and sits under 829 x 2 = 1658 with 200 marks untallied (this sheet prints "
    "no blanks row). The page prints no 'vote for' line.",
    "NOT APPLIABLE AS FILED: six contests in this record hold num_winners == 1. "
    "Two candidates marked '- Elect' in one block is the document saying two seats.",
    "needs-owner")

# ---- a parse artifact worth the owner's eye ------------------------------
row(None, "Provincetown2026",
    "elections[].municipality (all seven contests)", "Austin", "Provincetown",
    "Page 1 of Provincetown2026.pdf at 150dpi. The sheet carries the town seal "
    "('TOWN OF PROVINCETOWN ... PRECINCT OF CAPE COD') and is signed 'Elizabeth "
    "Paine / Town Clerk'; it names no municipality in type. Its first two "
    "candidates are 'Austin Douglas Miller' and 'Austin Phillip Knight'.",
    "Every contest in this record carries municipality 'Austin', which is a "
    "candidate's first name and not a town. The field exists only to disagree with "
    "the stem, so a wrong value here is a false wrong-town witness rather than a "
    "cosmetic error -- and 'Austin' looks like the parser reading the first "
    "candidate row. Filed for the owner because a municipality is not a string "
    "test the applier runs, and because the interesting question is how many other "
    "records carry a first name in this field.", "needs-owner")

# ---- rows already satisfied by the record --------------------------------
for idx, stem, note in (
    (15, "Worcester2021",
     "Verified against page 1 at 170dpi this session: the SCHOOL COMMITTEE MEMBER "
     "block prints 'JERMOH V. KAMARA 8,001' and the record already holds that name "
     "and that figure. Nothing left to apply."),
    (69, "Worcester2021",
     "Same correction as the row above and same reading; the record already holds "
     "'JERMOH V. KAMARA' 8001. Nothing left to apply."),
):
    R.append((idx, stem, None, None, None, None, note, "applied"))


def main():
    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())

    for idx, stem, field, was, should, read, why, status in R:
        if idx is None:
            r = {k: "" for k in fields}
            rows.append(r)
        else:
            r = rows[idx]
            assert r["stem"] == stem, (idx, r["stem"], stem)
        r["stem"] = stem
        r["source_sha256"] = sha(stem)
        if field is not None:
            r["field"], r["was"], r["should_be"] = field, was, should
            r["read"] = read
            r["why"] = why
        else:
            r["why"] = (r.get("why") or "") + " || " + why
        r["status"] = status
        r["decided_by"] = ME
        r["decided_on"] = TODAY
        if status == "applied":
            r["applied_on"] = TODAY

    with io.open(LEDGER, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"{len(R)} rows written; ledger now {len(rows)} rows")


main()
