"""Four ballot counts the source prints and the record does not hold.

Every one of these records reports `ballots_cast: null` with
`ballots_cast_source: cannot_derive`, which is right -- no contest in them
prints its blanks, so nothing can be derived.  It is not the same as the count
being unknown: the article says it in prose, in the same passage that reports
the result.

Each was read in context rather than matched, because "voters" is not always
ballots and a percentage is not a count.  The ones that did NOT survive that
reading are as much of the answer: Monson 2021 says "approximately 20 percent",
Mattapoisett 2021 quotes the clerk saying "Over 1,500 voters", Somerset 2023
prints per-race totals and no town figure, and Hampden 2023 states two
different turnouts -- 239 for the election it reports and 480 for "the 2023
annual town election" -- which is a question about which year the article is
about, not a ballot count to record.

None of the four changes any existing check: with the count in place, every
contest in all four sits under ballots x seats.
"""

import csv
import datetime
import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")

ROWS = [
    ("Ipswich2024", 4507,
     "Turn out was very high for a town election at around 45%. In all, 4,507 "
     "ballots were cast. Votes were posted by town clerk Amy Akell around 8:30 "
     "p.m. outside the count center in the Ipswich Y.",
     "The record's one tallied contest, Select Board, sums to 4,252 marks, "
     "which sits under 4,507 as an uncontested town-wide race should. NOTE FOR "
     "THE APPLIER: this record also holds one candidate with votes null, so a "
     "search for 'None' finds two places and the row will be refused as "
     "ambiguous. It is the ballots_cast that is meant."),
    ("Worthington2022", 266,
     "Ballots Cast - 266 Registered Voters - 997",
     "Printed as a labelled pair at the head of the town's own results page, "
     "not inferred from a percentage. Finance Committee 130+115 = 245 and "
     "School Committee 481 of 266 x 2 both sit under it."),
    ("Granby2022", 621,
     "The 621 voters represented a 13% turnout of Granby's 4,859 voters.",
     "621/4,859 = 12.8%, which rounds to the 13% the same sentence prints, so "
     "the two halves corroborate each other. Select Board 611, Board of Health "
     "594 and Commissioner of Burial Grounds 541 all sit just under it, which "
     "is the shape of a town-wide ballot with a few blanks."),
    ("Cheshire2024", 1465,
     "Turnout was about 22 percent with 1,465 of the town's 6,574 registered "
     "voters going to the polls.",
     "1,465/6,574 = 22.3%, which agrees with the 'about 22 percent' in the "
     "same sentence. Every contest in the record sits far under it; most are "
     "single write-in votes."),
]


def main():
    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    have = {(r["stem"], r["field"]) for r in rows}
    added = 0
    for stem, value, quote, why in ROWS:
        field = "ballots_cast"
        if (stem, field) in have:
            print("already filed:", stem)
            continue
        rows.append({
            "stem": stem, "source_sha256": "", "field": field,
            "was": "None", "should_be": str(value),
            "read": "The only reading held is the news article "
                    f"(data/news_text/{stem}.md), which prints, verbatim: "
                    f'"{quote}"',
            "why": "The record holds ballots_cast null with "
                   "ballots_cast_source 'cannot_derive', which is correct -- no "
                   "contest in it prints its blanks. The count is not unknown "
                   "though: the source states it in prose. " + why,
            "status": "verified",
            "decided_by": "civicatlas-qa (unattended run)",
            "decided_on": datetime.date.today().isoformat(),
            "applied_on": "",
        })
        added += 1
        print(f"filed: {stem:<18} ballots_cast None -> {value}")
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
