"""Read a printed ballot count out of a news-sourced town-year, and test it.

For 607 records `derive_ballots` returns None and layer 2 does nothing at all --
no contest in them is ever tested against anything.  178 of those are records
whose only reading is a news article, and 122 of those articles print a ballot
or turnout figure in prose.  That figure is the document's own statement of how
many ballots were cast, so the contests in the record can be tested against it
exactly as they would be against a derived count.

This does not decide anything.  It extracts, quotes, and computes, so a session
can read the sentence the figure came out of and say whether it is the town's
ballot count or something else -- registered voters, a percentage, last year's
figure.  Nothing here writes to the corpus.
"""

import collections
import csv
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402

# A ballot count as prose prints it.  Anchored on the word that says these are
# BALLOTS, never on a bare number: "1,234 ballots", "cast 1,234 ballots",
# "1,234 residents cast ballots", "1,234 voters turned out".  Registered voters
# are deliberately not matched -- that is a denominator, not a ballot count.
RE_BALLOTS = re.compile(
    r"(?:(\d[\d,]{1,8})\s+(?:total\s+)?(?:ballots|votes)\s+(?:were\s+)?(?:cast|counted)"
    r"|(?:cast|counted|received|tallied)\s+(?:a\s+total\s+of\s+)?(\d[\d,]{1,8})\s+(?:total\s+)?ballots"
    r"|(\d[\d,]{1,8})\s+(?:of\s+the\s+town's\s+)?(?:residents|voters|people)\s+(?:cast|turned out)"
    r"|turnout\s+of\s+(\d[\d,]{1,8})\s+(?:ballots|voters))",
    re.I)


def printed_ballots(text):
    """Every ballot count the prose states, each with the window it came from."""
    out = []
    for m in RE_BALLOTS.finditer(text):
        raw = next(g for g in m.groups() if g)
        try:
            n = int(raw.replace(",", ""))
        except ValueError:
            continue
        a, b = max(0, m.start() - 60), min(len(text), m.end() + 60)
        out.append((n, " ".join(text[a:b].split())))
    return out


def main():
    rows = list(csv.DictReader(open(os.path.join(BASE, "qa", "worklist.csv"),
                                    encoding="utf-8")))
    want = [r["stem"] for r in rows if r["status"] == "deferred"]
    tally = collections.Counter()
    for stem in want:
        p = os.path.join(BASE, "data", "json", stem + ".json")
        if not os.path.exists(p):
            continue
        record = json.load(open(p, encoding="utf-8"))
        if layers.derive_ballots(record)[0]:
            continue
        text, source = layers.document_text(stem)
        if source != "news_text" or not text:
            continue
        found = printed_ballots(text)
        if not found:
            tally["no printed count"] += 1
            continue
        counts = sorted({n for n, _ in found})
        # Only a single unambiguous figure can be tested; two different numbers
        # in one article is a disagreement, not a reading.
        if len(counts) > 1:
            tally["several figures"] += 1
            print(f"AMBIGUOUS {stem}: {counts}")
            for n, w in found:
                print(f"          {n}: {w[:150]}")
            continue
        ballots = counts[0]
        over = []
        for e in record.get("elections") or []:
            if layers.scope_of(e) != "at_large":
                continue
            seats = e.get("num_winners") or 1
            m = layers.marks_in(e)
            if m and m > ballots * seats:
                over.append((str(e.get("office_original") or "")[:40], m,
                             seats, ballots * seats))
        tally["testable"] += 1
        if over:
            tally["marks exceed the printed count"] += 1
            print(f"OVER {stem}: printed {ballots} -- {found[0][1][:150]}")
            for o, m, s, exp in over:
                print(f"     {o}: {m} marks > {ballots} x {s} = {exp}")
    print()
    for k, v in sorted(tally.items()):
        print(f"{v:5}  {k}")


if __name__ == "__main__":
    main()
