"""The twenty-eight ballot counts an earlier run read and could not file.

Row 329 of the ledger carries all twenty-eight as one prose cell, refused as
"qa.apply's figure path matches the value being replaced and this record holds
null".  That is nearly right and gives up one step early: the applier compares
`str(record value) == str(was)`, so a null field is addressed by the four
characters `None`.  It works wherever the record holds exactly ONE null.

So this session opened each of the twenty-eight readings itself -- born-digital
extractions read directly, scans rendered and read by eye -- and files the ones
that can be addressed as their own rows.  Four cannot: their records hold
several nulls at once, which is ambiguous to the applier and is itself worth the
owner's eye.

Run once:  python scratch/ledger_2026_09_07b.py
"""
import csv
import hashlib
import io
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")
TODAY = "2026-09-07"
ME = "civicatlas-qa (unattended run 2026-09-07)"

WHY = ("The document states the ballot count and the record holds null. Read "
       "this session and filed as bare values -- `was` is the four characters "
       "`None`, which is how the applier addresses a null field, and which is "
       "why row 329's table of twenty-eight could not be applied as written. "
       "NOTE: ballots_cast_source still reads 'cannot_derive' and the applier "
       "has no route to that field.")

# stem, figure, reading
READ = [
    ("NewMarlborough2021", "146",
     "data/pdftext/NewMarlborough2021.txt, from a born-digital PDF. Verbatim: "
     "'Results of Annual Town Election / Held Monday, May 10, 2021 / Total Active "
     "Voters: 1096 / Total Ballots Cast: 146'. The largest figure in the record is "
     "SELECTMEN 128, under 146."),
    ("NewMarlborough2022", "184",
     "data/pdftext/NewMarlborough2022.txt. Verbatim: 'RESULTS OF ANNUAL TOWN "
     "ELECTION / HELD ON MODAY, MAY 9, 2022 / TOTAL REGISTRIED VOTERS: 1080 / "
     "TOTAL BALLOTS CAST: 184'. Largest figure 161 (Cemetery Commissioner), under "
     "184."),
    ("NewMarlborough2023", "138",
     "data/pdftext/NewMarlborough2023.txt. Verbatim: 'RESULTS OF ANNUAL TOWN "
     "ELECTION / HELD ON MODAY, MAY 8, 2023 / TOTAL REGISTRIED VOTERS: 1141 / "
     "TOTAL BALLOTS CAST: 138'. Largest figure 127, under 138."),
    ("NewMarlborough2024", "67",
     "data/pdftext/NewMarlborough2024.txt. Verbatim: 'OFFICIAL RESULTS OF ANNUAL "
     "TOWN ELECTION / HELD ON MODAY, MAY 13, 2024 / TOTAL REGISTRIED VOTERS: 1166 "
     "/ TOTAL BALLOTS CAST: 67'. Largest figure 63 (Moderator), under 67."),
    ("NewMarlborough2026", "65",
     "data/pdftext/NewMarlborough2026.txt. Verbatim: 'OFFICIAL RESULTS OF ANNUAL "
     "TOWN ELECTION / HELD ON MODAY, MAY 11, 2026 / TOTAL REGISTRIED VOTERS: 1188 "
     "/ TOTAL BALLOTS CAST: 65'. Largest figure 57 (Moderator), under 65."),
    ("Alford2021", "53",
     "data/pdftext/Alford2021.txt, from a born-digital PDF. Verbatim: 'RESULTS OF "
     "ANNUAL TOWN ELECTION MAY 18,2021' / 'TOTAL ACTIVE VOTERS-379 TOTAL BALLOTS "
     "CAST-53'. Largest figure 52 (Constable), under 53."),
    ("Nahant2024", "586",
     "data/pdftext/Nahant2024.txt, from a born-digital PDF. Headed 'NAHANT ANNUAL "
     "TOWN ELECTION / APRIL 27, 2024 / OFFICIAL RESULTS'; the last line of the "
     "table reads, verbatim: 'Total Ballots Cast 586'. Largest figure 548 (Town "
     "Clerk), under 586."),
    ("Nahant2025", "821",
     "data/pdftext/Nahant2025.txt. The last line of the table reads, verbatim: "
     "'Total Ballots Cast 821'. Largest figure 627 (Planning Board- 5 Years), "
     "under 821."),
    ("Nahant2026", "644",
     "data/pdftext/Nahant2026.txt. The last line of the table reads, verbatim: "
     "'Total Ballots Cast 644', over 'True Copy Attest: Diane Dunfee, Nahant Town "
     "Clerk'. The ballot question reads YES 386 / NO 154 = 540, under 644."),
    ("Acushnet2024", "498",
     "data/pdftext/Acushnet2024.txt. The source held for this town-year is a "
     "newspaper page, headline 'Fewer than 500 vote in Acushnet Election', by-line "
     "'By Beth David, Editor'. Verbatim: 'A total of 498 ballots were cast out of "
     "8,573 registered voters, for a turnout of 5.8%.' Largest figure in the "
     "record 460, under 498. (Separately: this PDF is published in civicatlasma "
     "and is a news page, which the project's rules say does not belong there.)"),
    ("Littleton2021", "1486",
     "data/pdftext/Littleton2021.txt, from a born-digital PDF. Verbatim: 'Total "
     "ballots cast 1486. These totals do not include blanks and scatterings.' -- "
     "which is also why derive_ballots cannot reach it."),
    ("Southampton2022", "303",
     "data/pdftext/Southampton2022.txt, from a born-digital PDF. Verbatim: 'There "
     "were 303 ballots cast. There were 5 absentee ballots. There is a total 4496 "
     "of active registered voters in town.'"),
    ("Brimfield2024", "828",
     "data/pdftext/Brimfield2024.txt, from a born-digital PDF. Verbatim: 'TOTAL "
     "BALLOTS CAST: 828 (27.9%)' / 'TOTAL VOTERS: 2965'. 828/2965 = 27.9%."),
    ("Bernardston2025", "56",
     "data/pdftext/Bernardston2025.txt, from a born-digital PDF. Verbatim: '56 "
     "Voters cast ballots out of 1734 registered voters.'"),
    ("Blandford2022", "198",
     "data/pdftext/Blandford2022.txt, from a born-digital PDF -- the town's own "
     "annotated ballot, with '*' beside each winner. Written into the sheet beside "
     "the Field Driver block, verbatim: '198 ballots cast'. The largest figure on "
     "it is Library Trustee 195, under 198."),
    ("Hubbardston2021", "254",
     "data/markdown/Hubbardston2021.md, which is the only reading held for this "
     "town-year and quotes the source directly: '\"Total # Registered Voters = "
     "3451    TOTAL VOTES CAST TODAY: 254 (7.36%)\"'. 254/3451 = 7.36%."),
    ("EastBrookfield2023", "297",
     "data/markdown/EastBrookfield2023.md, the only reading held: 'Source: a "
     "photograph of the town's own OFFICIAL BALLOT for the 9 May 2023 annual town "
     "election ... the clerk wrote the tallies on it in marker, and totalled the "
     "turnout at the foot', quoting '297 VOTERS CAST BALLOTS'."),
    ("Gill2026", "250",
     "data/markdown/Gill2026.md, the only reading held, quoting the town's own "
     "notice: 'These results will be updated later in the week with write-ins and "
     "blanks, with 250 ballot cast and 1313 registered voters.' -- which also says "
     "why no contest in this record prints blanks, so nothing can be derived."),
    ("Hinsdale2021", "135",
     "Page 1 (the only page) of Hinsdale2021.pdf rendered at 130dpi: 'Annual Town "
     "Election / Hinsdale, Massachusetts / June 12, 2021 / List of Candidates for "
     "Town Office', with the tallies written on it by hand. Written across the top "
     "left, verbatim: 'Total Vote 135'. The hand-written blanks corroborate it: "
     "ASSESSOR - 3 years 'Blanks 133' and PLANNING BOARD - 4 years 'Blanks 134', "
     "both just under 135, and the ballot question reads YES 87 NO 42 = 129."),
    ("Hinsdale2025", "148",
     "Page 1 (the only page) of Hinsdale2025.pdf at 130dpi: 'ANNUAL TOWN ELECTION "
     "/ HINSDALE, MASSACHUSETTS / MAY 17, 2025 / LIST OF CANDIDATES FOR TOWN "
     "OFFICE', the word SAMPLE printed across it in script and the results written "
     "on it by hand. Written across the top left, verbatim: '148 ballots cast'. "
     "The largest figure is Tree Warden 136, under 148; the question reads YES 86 "
     "NO 30."),
    ("NewAshford2021", "81",
     "Page 1 (the only page) of NewAshford2021.pdf, a photograph of the marked-up "
     "'OFFICIAL BALLOT / ANNUAL TOWN ELECTION / NEW ASHFORD, MASSACHUSETTS / MAY "
     "25, 2021', rendered at 60dpi (the scan is 5016 x 6367). Hand-written at the "
     "top right, verbatim: '81 VOTERS'; at the top left 'POSTED 5/25/2021'. "
     "Selectmen 49 + 30 = 79 and Town Clerk 37 + 43 = 80, both under 81."),
    ("NewAshford2022", "26",
     "Page 1 (the only page) of NewAshford2022.pdf at 130dpi: a photograph of a "
     "typed sheet headed 'Results of elections' that carries five town-years at "
     "once. Verbatim: '2022  26 ballots cast / Ken McInerney 3 year term "
     "selectboard 25 votes / Richard George 3 year term board of health 22 votes / "
     "Steve Jennings 5 year term planning 24 votes'. The record holds exactly "
     "those three figures."),
    ("NewAshford2025", "28",
     "The same sheet, read at 130dpi. Verbatim: '2025  28 ballots cast / Ken "
     "McInerney 3 yr term select board 28 votes / Richard George 3 yr term board "
     "of health 28 votes / Lars Reinhard 5 yr term planning board 28 votes'. Every "
     "contest is 28 of 28, so the count is stated and confirmed by three blocks."),
    ("NewAshford2026", "34",
     "The same sheet, read at 130dpi. Verbatim: '2026  34 ballots cast / Mark "
     "Phelps 3 yr term select board 32 votes / Helen Majchrowski 3 yr term board "
     "of health 28 votes / Nathan Bradbury 2 yr term board of health 32 votes / "
     "Mario Gagliardi 5 yr term planning 32 votes'. The record holds exactly those "
     "four."),
]

STUCK = [
    ("Worthington2021", "209",
     "data/pdftext/Worthington2021.txt, from the town's own page "
     "(worthington-ma.us). Verbatim: 'There are 989 Registered Voters in "
     "Worthington' / '209 Ballots were cast in this Town Election'. The page "
     "prints figures for the contested School Committee only (115, 84, 146) and "
     "lists the ten uncontested offices by name with no figure at all, which is "
     "the town's own choice and faithfully transcribed.",
     "NOT APPLIABLE: ten candidates in this record hold null votes because the "
     "source prints none, so `None` matches eleven places and the applier cannot "
     "tell which is ballots_cast. The record is right and the tool cannot reach "
     "it."),
    ("Abington2022", "876",
     "data/markdown/Abington2022.md, the only reading held: a news article, "
     "'Source: ABINGTON NEWS, \"YOUR CHOICE '22: VanNest, Christian, Shepherd, "
     "Grafton chosen by voters\"'. It states 'Total ballots cast: 876'.",
     "NOT APPLIABLE: eleven candidates in this record hold null votes -- the "
     "article names winners without figures -- so `None` matches twelve places."),
    ("NewAshford2024", "37",
     "Page 1 of NewAshford2024.pdf at 130dpi, the five-year 'Results of elections' "
     "sheet. Verbatim: '2024  37 ballots cast / Jason Jayco 3 yr term select board "
     "33 votes / Emilee Gagliardi 3yr term board of health 21 votes / Tammy "
     "Steinhoff 5 yr term planning board 31 votes'.",
     "NOT APPLIABLE while the record carries a second null: see the candidate row "
     "filed beside this one. Fix that and this becomes a one-line apply."),
]

R = []
for stem, val, read in READ:
    R.append((stem, "ballots_cast", "None", val, read, WHY, "verified"))
for stem, val, read, note in STUCK:
    R.append((stem, "ballots_cast", "None", val, read, WHY + " || " + note,
              "needs-owner"))

R.append((
    "NewAshford2024",
    'elections[Board of Health - 3 year term].candidates -- "Helen Majchrowski" '
    "does not belong to this town-year",
    "Emilee Gagliardi 21, Helen Majchrowski null",
    "Emilee Gagliardi 21 alone",
    "Page 1 of NewAshford2024.pdf at 130dpi. The sheet lists five town-years in "
    "order and each block is complete on its own line. Verbatim: '2024  37 ballots "
    "cast / Jason Jayco 3 yr term select board 33 votes / Emilee Gagliardi 3yr "
    "term board of health 21 votes / Tammy Steinhoff 5 yr term planning board 31 "
    "votes'. Helen Majchrowski appears once on this sheet and it is in the block "
    "below: '2026  34 ballots cast / ... Helen Majchrowski 3 yr term board of "
    "health 28 votes', and the NewAshford2026 record already holds her there with "
    "28.",
    "A candidate has crossed a block boundary on a document that carries five "
    "town-years, and arrived with no figure because there was none to take. "
    "Removing a candidate is not something the applier does -- it replaces a value "
    "it can find -- so this needs the owner. It also blocks this record's ballot "
    "count, which is the row beside it.",
    "needs-owner"))


def sha(stem):
    p = os.path.join(BASE, "data", "pdfs", stem + ".pdf")
    if not os.path.exists(p):
        return ""              # markdown-only town-years hold no PDF
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())

    for stem, field, was, should, read, why, status in R:
        rows.append({
            "stem": stem, "source_sha256": sha(stem), "field": field,
            "was": was, "should_be": should, "read": read, "why": why,
            "status": status, "decided_by": ME, "decided_on": TODAY,
            "applied_on": "",
        })

    # Row 329 carried all twenty-eight as one cell and could never be applied.
    for i, r in enumerate(rows):
        if r["stem"] == "(28 records)":
            r["why"] += (" || 2026-09-07: superseded. Every one of the "
                         "twenty-eight readings was reopened this session and "
                         "filed as its own row, addressed as `None` -- which is "
                         "how the applier reaches a null field, and is the step "
                         "this row stopped one short of. Twenty-four apply; four "
                         "hold several nulls at once and are filed with the "
                         "reason.")
            r["status"] = "needs-owner"
            r["decided_by"] = ME

    with io.open(LEDGER, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"{len(R)} rows appended; ledger now {len(rows)} rows")


main()
