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

## The same habit, seen from the other side

Some clerks print the aggregate FIRST and itemise underneath it, and then the
aggregate is not a restatement of the names -- it CONTAINS them. Pepperell
2021's Recreation Commission prints `Write-ins 95 / Alan Leao 59 / Dana Hanson
14 / Blanks 342` over a printed `Totals 437`, and 95 + 342 is 437 exactly:
Leao and Hanson are two of the ninety-five. Boxborough 2025 prints `WRITE INS
66 / Bryan Lynch, 436 Littlefield Rd 37 / Blanks 673 / Total 739`. Shirley
2023 goes further and prints the winner as a sentence -- `Write Ins 84 /
Blanks 604 / WINNER - WILLIAM MCGUINNESS 21 VOTES / TOTAL 688`.

Dropping the aggregate is wrong here: it would throw away the write-ins nobody
named. What the project's own rule says is to keep the name and give the
aggregate the remainder, so `Write-ins 95` becomes 22 and the block closes on
437. The arithmetic that decides it is the mirror of the first rule:

    marks - (every named row) == ballots x seats,  and aggregate >= that sum

Thirteen contests in eight town-years fit it, and every one was read against
its document before this ran: Boxborough 2025, Georgetown 2023, Kingston 2022,
Pepperell 2021 (four), Shirley 2023 (three), Webster 2021, Webster 2022 (two).
In each the printed total equals aggregate + blanks, which is the document
saying the same thing the arithmetic does.

Where both rules would fire the first one wins, because dropping a row the
clerk restated is the established treatment and leaves no zero behind.

The second rule costs something and it is worth stating: the remainder it
writes is a figure the page does not print, so `figures_grounded` starts
failing on five of the eight records it touches. That is the check being
right -- the number IS derived -- and it is the same trade the corpus already
makes for a blanks row computed from a printed total. Thirteen arithmetically
impossible contests for five ungrounded remainders.

## Why the rules can be run separately

The first rule cannot tell a restated subtotal from a write-in row a machine
prints OUTSIDE its own total. Attleboro 2021's return is the second: every
contest reads `Times Cast 6,920 / Blanks 1,754 / ZAIDA KEEFER 5,166 100.00% /
Total Votes 5,166 / Unresolved Write-In`, so blanks plus votes already make
the ballot count and the write-in line sits beside them. Dropping those six
rows would close six contests and throw away the only record that anyone wrote
anything in. That is a convention decision about a whole document, it is in
`adjudications.csv` as the owner's, and `--rule` exists so the other rule can
run without waiting on it.

    python -m src.migrate_write_in_subtotal                    # report only
    python -m src.migrate_write_in_subtotal --write
    python -m src.migrate_write_in_subtotal --rule overstated --write
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


def overstated_aggregates(record, already):
    """(contest, candidate, new value) for every aggregate that CONTAINS the names.

    The mirror of `duplicated_aggregates`: there the aggregate restates the
    itemised write-ins and is removed, here it includes them and keeps the
    remainder.  `already` is the set of contest indices the first rule has
    claimed, which wins.
    """
    ballots = record.get("ballots_cast")
    if not isinstance(ballots, int) or ballots <= 0:
        return []
    out = []
    for i, e in enumerate(record.get("elections") or []):
        if i in already or layers.scope_of(e) == "regional_district":
            continue
        seats = e.get("num_winners") or 1
        cands = e.get("candidates") or []
        marks = sum(c.get("votes") or 0
                    for c in cands if isinstance(c.get("votes"), int))
        room = ballots * seats
        if marks <= room:
            continue
        aggs = [ci for ci, c in enumerate(cands)
                if isinstance(c.get("votes"), int)
                and AGGREGATE.match(str(c.get("name_original") or ""))]
        named = [c.get("votes") for c in cands
                 if isinstance(c.get("votes"), int) and not layers.is_tally_row(c)]
        total_named = sum(named)
        if len(aggs) != 1 or not total_named or marks - total_named != room:
            continue
        # The aggregate has to be big enough to have contained them.
        if cands[aggs[0]]["votes"] < total_named:
            continue
        out.append((i, aggs[0], cands[aggs[0]]["votes"] - total_named))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--rule", choices=("both", "duplicate", "overstated"),
                    default="both",
                    help="which of the two shapes to act on (see the docstring)")
    args = ap.parse_args()

    removed = 0
    reduced = 0
    touched, unsettled = [], []
    for path in sorted(glob.glob(os.path.join(BASE, "data", "json", "*.json"))):
        stem = os.path.basename(path)[:-5]
        with io.open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        drop, ambiguous = duplicated_aggregates(record)
        for i, names in ambiguous:
            unsettled.append((stem, i, names))
        keep = overstated_aggregates(record, {i for i, _ in drop})
        if args.rule == "duplicate":
            keep = []
        elif args.rule == "overstated":
            drop = []
        if not drop and not keep:
            continue
        for i, ci, value in keep:
            e = record["elections"][i]
            c = e["candidates"][ci]
            print(f"  {stem:<18} {str(e.get('office_original'))[:34]:<34} "
                  f"{c.get('name_original')!r} {c.get('votes')} -> {value} "
                  f"(the named write-ins were inside it)")
            c["votes"] = value
            reduced += 1
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

    print(f"\n{removed} duplicated aggregates dropped and {reduced} overstated "
          f"ones reduced, in {len(touched)} town-years")
    if unsettled:
        print(f"\n{len(unsettled)} contests where two rows would each close it, "
              f"left alone:")
        for stem, i, names in unsettled:
            print(f"   {stem} elections[{i}] {names}")
    if args.write:
        # One record of the run per rule, so running the second rule does not
        # overwrite the list the first one left.
        name = {"both": "_write_in_subtotal.txt",
                "duplicate": "_write_in_subtotal.txt",
                "overstated": "_write_in_inside_aggregate.txt"}[args.rule]
        with io.open(os.path.join(BASE, "src", name), "w", encoding="utf-8") as fh:
            fh.write("\n".join(touched))
    else:
        print("\nnothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
