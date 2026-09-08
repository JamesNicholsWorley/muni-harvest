"""Append adjudication rows read off documents in this run.

A correction is a row, never code.  This is the row-writing, kept out of the
ledger's own module so nothing here can change how rows are applied.
"""

import csv
import datetime
import hashlib
import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")
TODAY = datetime.date.today().isoformat()
BY = "civicatlas-qa (unattended run)"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def pdf_sha(stem):
    p = os.path.join(BASE, "data", "pdfs", stem + ".pdf")
    return sha256_of(p) if os.path.exists(p) else ""


ROWS = [
    dict(
        stem="Attleboro2021",
        field="elections[MAYOR, CITY CLERK, CITY COLLECTOR, CITY TREASURER, "
              "COUNCILMAN AT LARGE, SCHOOL COMMITTEE AT LARGE].candidates"
              "['Others'] -- the Dominion 'Unresolved Write-In' table, read as "
              "a row of the contest above it",
        was="Others 51, 19, 35, 36, 87 and 74 respectively",
        should_be="the six rows removed (or zeroed); every other figure stands",
        read="READ page 2 of data/pdfs/Attleboro2021.pdf (7pp, no text layer) "
             "rendered with pymupdf at 200dpi. CITY COLLECTOR (Vote for 1) "
             "prints, in three separate tables: 'Times Cast 6,920 | Blanks "
             "1,754', then 'Candidate | ZAIDA KEEFER 5,166 100.00% | Total "
             "Votes 5,166', then a THIRD table headed only Election Day/Total "
             "holding 'Unresolved Write-In 35'. Blanks 1,754 + Total Votes "
             "5,166 = 6,920 = Times Cast exactly, so the contest is already "
             "whole before the write-in table is reached: the 35 sits outside "
             "the tally, not inside it. CITY TREASURER on the same page is the "
             "same shape -- Blanks 1,696 + Total Votes 5,224 = 6,920, "
             "Unresolved Write-In 36 below it.",
        why="A parse shape, not an Attleboro fact. Each of the six city-wide "
            "contests overflows by EXACTLY its own 'Others' value: MAYOR 6971 "
            "- 51, CITY CLERK 6939 - 19, CITY COLLECTOR 6955 - 35, CITY "
            "TREASURER 6956 - 36, COUNCILMAN AT LARGE 34687 - 87 = 6920 x 5, "
            "SCHOOL COMMITTEE AT LARGE 20834 - 74 = 6920 x 3. Six coincidences "
            "is a pattern. src/migrate_write_in_subtotal.py already implements "
            "exactly this rule (marks - aggregate == ballots x seats) and "
            "finds these six contests and nothing else in the corpus; it has "
            "not been run against the working corpus since Attleboro 2021 "
            "entered it. Not applied here: this session's data/json is a "
            "symlink into the PUBLISHED civicatlasma, so writing it would edit "
            "the published copy rather than the corpus it represents.",
    ),
    dict(
        stem="Weston2026",
        field="elections[Select Board].num_winners",
        was="2",
        should_be="3",
        read="The only reading held is the news article. It prints, verbatim: "
             "'In the uncontested race for Weston's newly expanded five-member "
             "Select Board , Anupam Sachdev and Alfred Aydelott received the "
             "most votes, 731 votes and 751 votes, and will serve three-year "
             "terms, while Rebecca Mercuri, who received 681 votes, will serve "
             "a two-year term.' and 'Voter turnout was 12.4%, as 1,081 of "
             "Weston's 8,688 registered voters participated.'",
        why="num_winners is SEATS UP. Three people were elected to the Select "
            "Board -- two to three-year terms and one to a two-year term -- so "
            "three seats were up and the record says two. At two seats the "
            "block reads 2,163 marks against 1,081 x 2 = 2,162, one mark over "
            "and impossible; at three it is 2,163 of 3,243, an ordinary "
            "uncontested shortfall. The source states no 'vote for N', so this "
            "is not the printed seat count outranking the arithmetic: it is a "
            "prose statement of who was elected to what term.",
    ),
    dict(
        stem="Sandwich2026",
        field="elections[School Committee] -- a fused race: the one-year "
              "unexpired term is a separate contest",
        was="School Committee, num_winners 2, holding William T. Flynn 431, "
            "Susan Fucarino Miller 430 and Christopher J. Pino 390",
        should_be="School Committee (2 seats): Miller 430, Pino 390. School "
                  "Committee, one-year unexpired term (1 seat): Flynn 431.",
        read="The only reading held is the news article. It prints, verbatim: "
             "'Susan Fucarino Miller has won reelection to a seat on the "
             "Sandwich Public School Committee, with 430 votes, along with "
             "Christopher J. Pino, who received 390. Pino is a new addition to "
             "the committee. William T. Flynn also won a seat for a one-year "
             "unexpired term on the committee, with 431 votes.' and 'A total "
             "of 600 voters participated.'",
        why="A fused race, and the arithmetic saw it only because the fusion "
            "pushed the block past the ceiling: 1,251 marks against 600 x 2 = "
            "1,200. Separated it closes on both halves -- 430 + 390 = 820 of "
            "1,200, and Flynn 431 of 600 -- and the source itself says the "
            "one-year unexpired term is a different seat. Splitting a contest "
            "is structural and belongs to the owner, not to the applier.",
    ),
]


def main():
    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    have = {(r["stem"], r["field"]) for r in rows}
    added = 0
    for spec in ROWS:
        if (spec["stem"], spec["field"]) in have:
            print("already filed:", spec["stem"])
            continue
        row = {k: "" for k in fields}
        row.update(spec)
        row["source_sha256"] = pdf_sha(spec["stem"])
        row["decided_by"] = BY
        row["decided_on"] = TODAY
        rows.append(row)
        added += 1
        print("filed:", spec["stem"], "|", spec["field"][:60])
    if "--write" in sys.argv and added:
        with io.open(LEDGER, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})
        print(f"\n{added} rows appended to {os.path.relpath(LEDGER, BASE)}")
    else:
        print("\nnothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
