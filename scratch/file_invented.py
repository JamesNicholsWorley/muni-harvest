"""Numbers nobody printed, in records whose only source is a news article.

`src/fix_invented_uncontested_totals.py` names the convention: an uncontested
winner whose document prints no count has `votes: null` and `status:
"uncontested"`, because a number nobody printed is worse than no number -- null
cannot be summed by accident and a filler can.  Its own sweep says "A corpus
sweep found these two and no others", and that sweep ran before
`qa.bootstrap` linked `civicatlas-private/news_text`: the 221 news-sourced
records had no readable text at all, so nothing in them could be found
ungrounded.  With the reading mounted they can be.

Two shapes, both read in the article before being written down:

  votes: 1 as "elected, no count printed".  Sheffield 2026 gives four winners a
  vote each from an article that prints no figure for any of them.  Cheshire
  2024 does it six times; those do not appear in a grounding sweep because the
  digit 1 occurs in any prose, which is exactly why the shape needs naming.

  votes: 0 for a named candidate the article says lost.  Orange 2024's
  Weinstein and Clarke stood in contested races whose winners' totals are
  printed and whose losers' are not.  Zero is a claim the article contradicts.

Granby 2021 settles the convention question inside one record: six of its
winners already carry `votes: null, status: "uncontested"` and three library
trustees from the same sentence carry 0.
"""

import csv
import datetime
import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")

ROWS = [
    ("Sheffield2026",
     "elections[Planning Board x2, Moderator, Library Trustees]"
     ".candidates[].votes",
     "Brian Sangster 1, Sari Hoy 1, Julie Hannum 1, Amy Brainbridge-Jordan 1",
     "votes null with status 'uncontested' for all four",
     'The article prints no figure for any of the four: "With no one running '
     'for a two-year term on the Planning Board, Brian Sangster won as a '
     'write-in candidate. Incumbents Sari Hoy was reelected to a three-year '
     'term on the Planning Board, along with Julie Hannum being reelected as '
     'moderator. Amy Brainbridge-Jordan won a seat on the library trustees in '
     'an uncontested race." The only figures it gives are the contested Select '
     'Board (Kilmer 254, Levine 237) and the turnout, "Of the 2,711 registered '
     'voters in Sheffield, 493 participated".',
     "Four ones that are not vote counts. The record's own Select Board "
     "contest shows what a figure from this article looks like."),
    ("Cheshire2024",
     "elections[Hoosac Valley Regional, Assessor, Board of Health, Cemetery "
     "Commissioner, Water Commissioner, Planning Board].candidates[].votes",
     "Robert Tetlow Jr. 1, Kellie Lahey 1, Brian Trudeau 1, Timothy Garner 1, "
     "Ricky Gurney 1, Peter Traub 1",
     "votes null with status 'uncontested' for all six",
     'The article names the uncontested winners in a list and prints no figure '
     'for any of them; the figures it does print are the contested Select '
     'Board and the turnout, "Turnout was about 22 percent with 1,465 of the '
     "town's 6,574 registered voters going to the polls.\"",
     "The same shape as Sheffield 2026 and invisible to a grounding sweep: the "
     "digit 1 occurs in any prose, so figures_grounded passes on all six."),
    ("Granby2021",
     "elections[Library Trustee].candidates[Janice Cook, Theresa Laprade, "
     "Denise Conti].votes",
     "0, 0 and 0",
     "votes null with status 'uncontested' for all three",
     'The article says, verbatim: "Janice Cook was re-elected to a three-year '
     'term as a library trustee; Theresa Laprade was re-elected to serve three '
     'years as a library trustee; Denise Conti was also elected to serve for '
     'three years as a library trustee." No figure for any of them.',
     "This record already carries the right convention for six other winners "
     "-- Board of Health, Moderator, Town Collector, Town Treasurer, Housing "
     "Authority and Commissioner of Burial Grounds all hold votes null with "
     "status 'uncontested' -- so the three trustees are the inconsistency, in "
     "the same record and from the same sentence of the same article."),
    ("Hatfield2023",
     "elections[Select Board].candidates[Kerry Flaherty, Amie Jones].votes",
     "0 and 0",
     "votes null",
     "The article prints Gregory Gagnon's 410 and no figure for either of the "
     "other two candidates in the contest.",
     "A named candidate in a contested race did not receive zero votes. Null "
     "says the count is not held; 0 says it was counted and was nothing."),
    ("Orange2023",
     "elections[Elementary School Committee].candidates[Crystal Cooke, "
     "Adrienne Berry].votes",
     "0 and 0",
     "votes null",
     'The article says, verbatim: "Elizabeth Cross notched 34 write-in votes '
     'to edge out Crystal Cooke for the other three-year position up for '
     'grabs. India Eadie bested Adrienne Berry with 33 write-in votes for a '
     'two-year spot on the Elementary School Committee."',
     "'Edged out' and 'bested' describe a margin, so both women polled "
     "something under 34 and 33 respectively. The article does not say what, "
     "and 0 is a number it contradicts."),
    ("Orange2024",
     "elections[Selectboard, Elementary School Committee].candidates[Sandra "
     "Fawn Weinstein, Crystal Clarke].votes",
     "0 and 0",
     "votes null",
     'The article says, verbatim: "Davis was the race\'s top vote-getter, '
     'receiving 384 votes, and Smith accumulated 304. The two competed against '
     'Sandra Fawn Weinstein for a pair of three-year seats." and "Frank Hains '
     'and Jessica Reske bested Crystal Clarke ... Hains got 366 votes while '
     'Reske received 242."',
     "The winners' totals are printed and the losers' are not. Same class as "
     "Orange 2023, in the following year's article from the same paper."),
    ("Plympton2022",
     "elections[Finance Committee].candidates[Steven R. Lewis].votes",
     "0",
     "votes null with status 'uncontested'",
     'The article says, verbatim: "The two Finance Committee five-year terms '
     'were won by Steven R. Lewis, candidate for re-election, and Michael '
     'Lemieux, who garnered nine write-in votes. Blanks were 258 and others '
     'were 11."',
     "Lewis was the candidate on the ballot and won; the article gives a "
     "figure for the write-in winner beside him and none for him. Zero is the "
     "one number he cannot have polled."),
]


def main():
    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    have = {(r["stem"], r["field"]) for r in rows}
    added = 0
    for stem, field, was, should, read, why in ROWS:
        if (stem, field) in have:
            print("already filed:", stem)
            continue
        rows.append({
            "stem": stem, "source_sha256": "", "field": field,
            "was": was, "should_be": should,
            "read": "The only reading held is data/news_text/%s.md. %s"
                    % (stem, read),
            "why": "A number nobody printed, which "
                   "src/fix_invented_uncontested_totals.py names as worse than "
                   "no number: null cannot be summed by accident and a filler "
                   "can. That module's sweep found two records and said so, "
                   "and it ran before qa.bootstrap linked news_text -- the "
                   "news-sourced records had no readable text, so nothing in "
                   "them could be found ungrounded. " + why,
            "status": "", "decided_by": "civicatlas-qa (unattended run)",
            "decided_on": datetime.date.today().isoformat(), "applied_on": "",
        })
        added += 1
        print(f"filed: {stem:<18} {was[:50]}")
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
