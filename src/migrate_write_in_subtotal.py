"""The write-in subtotal, counted twice: drop the aggregate, keep the people.

Clarksburg 2024's MODERATOR block prints, in this order:

    Seth Alexander 199 / Blanks 45 / Ronald Boucher 23 / Bryana Malloy 1 /
    Kathy Denault 1 / Colton Andrews 1 / Mark Denault 1 / John Jacobbe 1 /
    Others 28

The six names after Blanks are the write-ins, itemised. `Others 28` is their
total -- 23+1+1+1+1+1 -- printed again as one line, which is how a clerk shows
the same thing twice. The parse took both, so the contest totals 300 marks on
272 ballots for one seat, and reads as impossible.

## What decides it

Not a name pattern: the itemised write-ins here are ordinary names, and a check
looking for rows called "Write-In" finds none of them. What decides it is the
arithmetic, and exactly:

    marks - aggregate == ballots x seats

An aggregate that is double-counted makes the contest overflow by precisely its
own value, so removing it lands on the ballot count exactly rather than merely
closer. That is a coincidence worth trusting once; across 24 contests in 19
town-years it is a pattern.

Where TWO aggregate rows would each close the contest -- Groveland 2021 prints
both `Write In 2` and `Other 2` -- the arithmetic cannot say which is the
duplicate, so the contest is left alone and reported.

## Which one goes

The aggregate. The named write-ins are people who received votes and the
subtotal is a restatement of them; keeping the names and dropping the total
loses nothing and keeps who-was-written-in, which is the part a reader wants.

    python -m src.migrate_write_in_subtotal           # report, change nothing
    python -m src.migrate_write_in_subtotal --write
"""
import argparse
import collections
import glob
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402

AGGREGATE = re.compile(
    r"^\s*(?:others?|write[\s-]*ins?|scattering|scattered|all\s+others)\s*$", re.I)


def duplicated_aggregates(record):
    """(contest index, candidate index) for every aggregate that is counted twice.

    Second value is the list of contests where more than one row would close it,
    which cannot be settled by arithmetic and must not be guessed.
    """
    ballots = record.get("ballots_cast")
    if not isinstance(ballots, int) or ballots <= 0:
        return [], []
    drop, ambiguous = [], []
    for i, e in enumerate(record.get("elections") or []):
        # A regional contest spans several towns, so its marks are expected to
        # exceed the host town's ballots and this arithmetic says nothing.
        if layers.scope_of(e) == "regional_district":
            continue
        seats = e.get("num_winners") or 1
        cands = e.get("candidates") or []
        marks = sum(c.get("votes") or 0
                    for c in cands if isinstance(c.get("votes"), int))
        room = ballots * seats
        if marks <= room:
            continue
        closers = [ci for ci, c in enumerate(cands)
                   if isinstance(c.get("votes"), int)
                   and AGGREGATE.match(str(c.get("name_original") or ""))
                   and marks - c["votes"] == room]
        if len(closers) == 1:
            drop.append((i, closers[0]))
        elif len(closers) > 1:
            ambiguous.append((i, [str(cands[ci].get("name_original"))
                                  for ci in closers]))
    return drop, ambiguous


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    removed = 0
    touched, unsettled = [], []
    for path in sorted(glob.glob(os.path.join(BASE, "data", "json", "*.json"))):
        stem = os.path.basename(path)[:-5]
        with io.open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        drop, ambiguous = duplicated_aggregates(record)
        for i, names in ambiguous:
            unsettled.append((stem, i, names))
        if not drop:
            continue
        # Remove from the end so earlier indices stay valid.
        for i, ci in sorted(drop, reverse=True):
            e = record["elections"][i]
            print(f"  {stem:<18} {str(e.get('office_original'))[:34]:<34} "
                  f"drop {e['candidates'][ci].get('name_original')!r}"
                  f"={e['candidates'][ci].get('votes')}")
            del e["candidates"][ci]
            removed += 1
        touched.append(stem)
        if args.write:
            with io.open(path, "w", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False, indent=1)

    print(f"\n{removed} duplicated aggregates in {len(touched)} town-years")
    if unsettled:
        print(f"\n{len(unsettled)} contests where two rows would each close it, "
              f"left alone:")
        for stem, i, names in unsettled:
            print(f"   {stem} elections[{i}] {names}")
    if args.write:
        with io.open(os.path.join(BASE, "src", "_write_in_subtotal.txt"),
                     "w", encoding="utf-8") as fh:
            fh.write("\n".join(touched))
    else:
        print("\nnothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
