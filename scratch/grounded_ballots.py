"""Where the derivation fails, does the DOCUMENT still state the ballot count?

607 records cannot derive their ballot count from their contests, and layer 2
does nothing at all on them: `layer2_arithmetic` returns as soon as the
derivation fails, so not one of their contests is tested against anything.

Many of those records nevertheless hold a `ballots_cast`, and for the
news-sourced ones that figure was transcribed out of prose -- "438 ballots were
cast", "TOTAL VOTERS 715" -- rather than derived from the contests.  Where the
figure is FOUND IN THE DOCUMENT it is not circular to test against it: it is the
document's own statement of how many ballots there were, checked the same way
every other figure in the record is checked.

This measures what such a test would say before any of it goes near a check:
how many records it reaches, how many contests it would test, and -- the only
part that matters -- how many contests it would report as impossible.  A test
that fires on nothing is not worth its runtime, and one that fires on hundreds
is measuring the wrong thing.
"""

import collections
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402


def main():
    tally = collections.Counter()
    over = []
    for p in sorted(glob.glob(os.path.join(BASE, "data", "json", "*.json"))):
        stem = os.path.basename(p)[:-5]
        record = json.load(open(p, encoding="utf-8"))
        if layers.derive_ballots(record)[0]:
            continue
        tally["cannot derive"] += 1
        held = record.get("ballots_cast")
        if not isinstance(held, int) or held <= 0:
            tally["no ballots_cast held"] += 1
            continue
        text, source = layers.document_text(stem)
        if not text:
            tally["no readable text"] += 1
            continue
        if not layers.figure_found(held, text):
            tally["ballots_cast not in the document"] += 1
            continue
        tally["testable: count is printed"] += 1
        for e in record.get("elections") or []:
            if layers.scope_of(e) != "at_large":
                continue
            seats = e.get("num_winners") or 1
            m = layers.marks_in(e)
            if not m:
                continue
            tally["contests tested"] += 1
            if m > held * seats:
                tally["contests over the printed count"] += 1
                over.append((stem, source, str(e.get("office_original"))[:34],
                             m, held, seats, m - held * seats))
    over.sort(key=lambda r: -r[6])
    for x in over:
        print("%-20s %-10s %-34s %6d marks > %d x %d  (over by %d)"
              % (x[0], x[1], x[2], x[3], x[4], x[5], x[6]))
    print()
    for k, v in sorted(tally.items()):
        print(f"{v:6}  {k}")


if __name__ == "__main__":
    main()
