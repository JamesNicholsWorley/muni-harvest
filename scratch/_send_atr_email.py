import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import mail                                          # noqa: E402

STANDING = (
    "166 records moved up a rung and 12 down. The 1,331 parsed pre-2021 "
    "sections now stand at 657 publish, 238 review, 430 hold -- 317 of the "
    "hold still holding no contest. The published folder is 961 town-years, "
    "nine withdrawn today. Every affected stem is in the CSV.")

QUESTIONS = [
    {"title": "94 records: one unreadable figure the page's own total says is zero",
     "detail": (
         "Each is a single null in a write-in or all-others row, in a contest "
         "whose printed total the other rows already reach. Filling them is "
         "the only thing that moves them, and it collides with the rule that "
         "a value invented in a blank cell is the error arithmetic can never "
         "catch. Belmont 2018 is why I did not: it is fabricated -- "
         "\"MICHAEL L WINNER 2103\" where the page reads \"MICHAEL J WIDMER "
         "2103\", 2 of 18 names anywhere on its page -- and three unreadable "
         "figures are the only reason it is not published."),
     "ask": "Fill those zeroes, or leave them?"},
    {"title": "42 contests where a printed seat count and the arithmetic disagree",
     "detail": (
         "Bourne 2017 prints \"Brd of Health / 3 years vote for 1\" and runs "
         "three candidates plus blanks summing to exactly twice its 1103 "
         "ballots. Danvers 2016 prints \"Vote for not more than 2\" against "
         "three times ballots. The page and the figures cannot both be right "
         "and I will not overwrite a quoted page."),
     "ask": "Work these one at a time, or take the printed count as final?"},
    {"title": "317 re-cut sections need a shard run and then a parse",
     "detail": (
         "Ballot vocabulary now decides which page of a report is the return, "
         "and a state primary ranks below the town's own election. Over 189 "
         "of these reports the old order reached the town's tallies 20 times "
         "and the new one 90; over 82 that already publish, 77 against 76. "
         "config/atr_section_recut.csv is ready for atr-section-shard with "
         "ocr=1. The parse afterwards needs the API key, which I do not hold."),
     "ask": "Run the shard and the parse when you can -- anything held back?"},
]

if __name__ == "__main__":
    dry = "--send" not in sys.argv
    out = mail.compose("Civic Atlas QA", STANDING, QUESTIONS,
                       lists=("/tmp/atr_findings.csv",), send_it=not dry)
    print(out if dry else "sent: %s" % (out,))
