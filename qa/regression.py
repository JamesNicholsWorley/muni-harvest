"""Fail a build only when it makes things worse.

The corpus has known open defects and will for a while. A gate that fails on any
nonzero count would be red permanently, and a permanently red gate is one nobody
reads -- which is worse than no gate, because it looks like coverage.

So the question this asks is narrower and answerable: **did this change increase
any failure count?** That is the only thing a check on a pull request can
usefully decide.

    python -m qa.regression --baseline qa/baseline.json
    python -m qa.regression --update qa/baseline.json     # after fixing things

Updating the baseline is a deliberate act with a diff somebody can read. It is
not done automatically on green, because a baseline that follows the corpus
downwards records the decline instead of catching it.
"""

import argparse
import collections
import csv
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(BASE, "qa", "layers_report.csv")


def counts(path=REPORT):
    """FAIL and UNKNOWN counts per check. NOTE is descriptive, not a defect."""
    c = collections.Counter()
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["verdict"] in ("FAIL", "UNKNOWN"):
                c[f'{r["layer"]}/{r["check"]}/{r["verdict"]}'] += 1
    return dict(c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--update", action="store_true",
                    help="write the current counts as the new baseline")
    args = ap.parse_args()

    if not os.path.exists(REPORT):
        sys.exit(f"no report at {REPORT}; run `python -m qa.layers` first")

    now = counts()

    if args.update or not os.path.exists(args.baseline):
        with open(args.baseline, "w", encoding="utf-8") as fh:
            json.dump(now, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"baseline written: {len(now)} checks, "
              f"{sum(now.values())} findings -> {args.baseline}")
        return

    with open(args.baseline, encoding="utf-8") as fh:
        was = json.load(fh)

    worse, better, new = [], [], []
    for k in sorted(set(now) | set(was)):
        a, b = was.get(k, 0), now.get(k, 0)
        if k not in was and b:
            new.append((k, b))
        elif b > a:
            worse.append((k, a, b))
        elif b < a:
            better.append((k, a, b))

    for k, a, b in better:
        print(f"  improved  {k}: {a} -> {b}")
    for k, n in new:
        print(f"  NEW CHECK {k}: {n}")
    for k, a, b in worse:
        print(f"  WORSE     {k}: {a} -> {b}")

    total_was, total_now = sum(was.values()), sum(now.values())
    print(f"\ntotal findings: {total_was} -> {total_now}")

    if worse:
        # A new check that finds things is not a regression -- it is the check
        # working.  Only a count rising under a check that already existed means
        # this change broke something.
        sys.exit(f"\n{len(worse)} check(s) got worse. If that is intended, "
                 f"rerun with --update and commit the baseline in the same change.")
    print("no regression")


if __name__ == "__main__":
    main()
