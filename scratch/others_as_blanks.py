"""Can a record whose tally row is called "Others" still derive its ballots?

`derive_ballots` needs a contest that prints its BLANKS, because only then is the
block total the whole ballot rather than a lower bound.  It looks for a row named
"Blanks".  Charlton 2021's source prints "Write-ins/Blanks - 240 votes (33.6%)"
under every contest and the parse recorded that row as "Others", so the record
holds the blanks and the check cannot see them: it reports "only 0 qualifying
contest(s); cannot derive" for a record in which every single-seat contest sums
to exactly 715, the "TOTAL VOTERS 715" the article prints.

"Others" normally means write-ins only, and write-ins do not account for blanks,
so treating the row as blanks in general would be wrong.  What is NOT a guess is
the arithmetic: if several independent single-seat contests in a record all sum
to the same number, that number is the ballot count whatever the row is called,
and two contests that disagree are a disagreement rather than a derivation -- the
same quorum rule `derive_ballots` already applies.

This measures how much of the corpus that would reach, and checks each answer
against the ballot count the record already holds.  It writes nothing.
"""

import collections
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402


def others_row(contest):
    """A single tally row that is not named Blanks -- the shape in question."""
    tally = [layers.name_of(c).lower() for c in contest.get("candidates") or []
             if layers.is_tally_row(c)]
    return len(tally) == 1 and tally[0] not in ("blanks", "blank")


def derive_by_agreement(record):
    est = []
    for e in record.get("elections") or []:
        if layers.scope_of(e) != "at_large":
            continue
        if (e.get("num_winners") or 1) != 1:
            continue
        if not layers.has_ballot_candidate(e) or not others_row(e):
            continue
        m = layers.marks_in(e)
        if m:
            est.append(m)
    if len(est) < 2:
        return None, len(est)
    counts = collections.Counter(est)
    top, n = counts.most_common(1)[0]
    return (top if n >= 2 else None), len(est)


def main():
    tally = collections.Counter()
    agree, disagree, novalue = [], [], []
    for p in sorted(glob.glob(os.path.join(BASE, "data", "json", "*.json"))):
        stem = os.path.basename(p)[:-5]
        record = json.load(open(p, encoding="utf-8"))
        if layers.derive_ballots(record)[0]:
            continue                      # already derivable; not this population
        tally["cannot derive today"] += 1
        got, n = derive_by_agreement(record)
        if not got:
            continue
        tally["would derive by agreement"] += 1
        held = record.get("ballots_cast")
        if not isinstance(held, int) or held <= 0:
            novalue.append((stem, got, n))
        elif held == got:
            agree.append((stem, got, n))
        else:
            disagree.append((stem, held, got, n))
    print("agrees with the ballot count the record already holds:", len(agree))
    print("record holds no ballot count:", len(novalue))
    print("DISAGREES with the held ballot count:", len(disagree))
    for x in disagree[:40]:
        print("   %-20s held %-8s contests agree on %-8s (%d contests)" % x)
    print()
    for k, v in sorted(tally.items()):
        print(f"{v:5}  {k}")


if __name__ == "__main__":
    main()
