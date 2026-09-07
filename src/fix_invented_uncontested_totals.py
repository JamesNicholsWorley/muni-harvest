"""Two records where an uncontested winner was given a number the page never gave him.

Conway 2021's source names five uncontested winners with no figure beside any of
them, and the record gives all five 92 votes. The only 92 on the page is the
turnout, spelled out: "Ninety-two voters showed up to the polls at Town Hall on
Thursday, which represents 6 percent of all registered voters in Conway." The
turnout became five identical vote counts.

New Salem 2022 is the same class with a different filler. The article prints
figures for four candidates -- Bohn 115, Conde 17, Blinder 105, Doyle 28 -- and
names nine more with no numbers. Those nine each hold 1.

A corpus sweep found these two and no others.

## The convention

An uncontested winner whose document prints no count has `votes: null` and
`status: "uncontested"`, which the schema has had since the -1/-3 sentinels were
retired. A number nobody printed is worse than no number: null cannot be summed
by accident, and 92 can -- five times, in Conway's case, which is how a turnout
figure became 460 votes spread across five contests.

Where the source says a winner came in on write-ins, `status:
"write_in_winner"` says so. Ohlson and Devlin are named that way.

The turnout itself is kept, in the field that means turnout: `ballots_cast`,
`stated_in_record`, because in both cases the page states it in a sentence.

Both records' documents were saved news articles, removed from the public
repository in September because it reproduced them in full. The readings quoted
above were recorded verbatim by the runs that opened them, in
`qa/worklist.csv`, before they were removed.

    python -m src.fix_invented_uncontested_totals            # report
    python -m src.fix_invented_uncontested_totals --write
"""
import argparse
import io
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# stem -> (the filler that is not a vote count, turnout, quote, write-in winners)
CASES = {
    "Conway2021": (
        92, 92,
        "Ninety-two voters showed up to the polls at Town Hall on Thursday, "
        "which represents 6 percent of all registered voters in Conway.",
        set()),
    "NewSalem2022": (
        1, 140,
        "According to Town Clerk Stacy Senflug, 140 (or 16%) of the town's 831 "
        "registered voters showed up to the polls.",
        {"Andrew Ohlson", "Elizabeth Devlin"}),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    for stem, (filler, turnout, quote, write_ins) in CASES.items():
        path = os.path.join(BASE, "data", "json", stem + ".json")
        if not os.path.exists(path):
            print(f"  {stem}: no record held")
            continue
        with io.open(path, encoding="utf-8") as fh:
            record = json.load(fh)

        changed = 0
        for e in record.get("elections") or []:
            for c in e.get("candidates") or []:
                if c.get("votes") != filler:
                    continue
                name = str(c.get("name_original") or "")
                c["votes"] = None
                c["status"] = ("write_in_winner" if name in write_ins
                               else "uncontested")
                print(f"  {stem:<14} {name:<26} {filler} -> null "
                      f"({c['status']})")
                changed += 1

        record["ballots_cast"] = turnout
        record["ballots_cast_source"] = "stated_in_record"
        record.setdefault("document", {})["turnout_quote"] = quote

        print(f"  {stem:<14} ballots_cast -> {turnout} (stated_in_record)")
        print(f"  {stem:<14} {changed} invented totals cleared\n")
        if args.write:
            with io.open(path, "w", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False, indent=1)

    if not args.write:
        print("nothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
