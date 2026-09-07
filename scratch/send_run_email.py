"""The one email for the 2026-09-07 unattended run.

Kept because the body is written, not generated, and the next run should be
able to see what shape a body under 2,200 characters actually is.

    python scratch/send_run_email.py          # print it, send nothing
    python scratch/send_run_email.py --send
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import mail  # noqa: E402

CSV = ("/tmp/claude-0/-home-user/18019660-714a-5785-a314-1c4adc6f66e5/"
       "scratchpad/civicatlas-qa-2026-09-07.csv")

STANDING = """
Applied nothing and closed 48 adjudications the corpus had already absorbed:
the correction was in the JSON and the value it replaced was gone, and two were
one --apply away from rewriting the wrong candidate. The worklist had no open
rows at all -- 183 stood deferred as unworkable in a cloud session, 182 read
fine now that bootstrap links news_text, and 173 are resolved.

STILL WAITING ON YOU: Holyoke 2021, Springfield 2025, Clinton 2022, Billerica
2021, Northampton 2023, Needham 2025, Milford 2025, Attleboro 2025, Stoughton
2026 -- and 42 more standing as needs-owner.
"""

QUESTIONS = [
    {
        "title": "ballots_cast is two fields and qa.apply writes one",
        "detail": "53 rows read this run: the source prints the count, the "
                  "record holds null. Writing ballots_cast alone would leave "
                  "ballots_cast_source at cannot_derive, which no record in the "
                  "corpus does, so I filed rather than applied. Four "
                  "date_corroboration rows are stuck the same way.",
        "ask": "Shall I add the companion write to qa/apply.py, or will you "
               "run the 57?",
    },
    {
        "title": "Weymouth 2023's figures are percentages, not counts",
        "detail": "The article says Hedlund won 75% of the 6,784 votes cast "
                  "and Mathews took 70% of the 890; the record holds 5088, "
                  "1218, 623 and 267 -- each computed, none printed. 0 of 5 "
                  "figures ground. 41,448 registered voters.",
        "ask": "Withdraw the four figures and keep the winners, or hold the "
               "record until the clerk's return turns up?",
    },
    {
        "title": "Plainville 2023's only source is dated 2 April 2018",
        "detail": "The Sun Chronicle piece carries that date twice, the "
                  "record's own date_parsed_raw is 2018-04-02 against a date of "
                  "2023-04-03, and all ten figures match it exactly. Clinton "
                  "2022's shape. Wayback would settle it; we are blocked from "
                  "Wayback here.",
        "ask": "Re-file it as the 2018 election and reopen the 2023 slot, or "
               "leave it until someone can check the archive?",
    },
    {
        "title": "Blanks computed from turnout make the derivation circular",
        "detail": "Aquinnah 2022's blanks are each 169 minus that contest's "
                  "two candidates, and 169 is the turnout the article states, "
                  "so ballots_cast is derived from itself. Chesterfield 2021 "
                  "the same; its source says 'No blanks are given'.",
        "ask": "Should a computed blanks row be dropped, or kept with the "
               "contest marked as not printing blanks?",
    },
]


def main(send_it):
    got = mail.compose("Civic Atlas QA", STANDING, QUESTIONS,
                       lists=[CSV] if os.path.exists(CSV) else [],
                       send_it=send_it)
    if not send_it:
        body, _ = got
        print(body)
        print(f"---- {len(body)} chars (limit {mail.MAX_BODY})")
    else:
        print(got)


if __name__ == "__main__":
    main("--send" in sys.argv)
