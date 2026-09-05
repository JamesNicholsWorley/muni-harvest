"""Record what was decided about a town-year, and what was read to decide it.

The worklist is the run's output as much as its input, and the first run had to
write a throwaway script to update twenty rows. This is that script, kept.

    python -m qa.resolve Salem2023 --status done \\
        --resolution 'no-change: p1 reads "SPECIAL PRELIMINARY ELECTION MARCH 28, 2023"'

    python -m qa.resolve --bucket preliminaries-1 --show
    python -m qa.resolve Agawam2023 --status escalated \\
        --resolution 'no document held and none published; ask the clerk'

A resolution must say what was READ, not only what was concluded. "wrong-doc" is
unverifiable a month later; `wrong-doc: heading reads "SPECIAL TOWN ELECTION
NOVEMBER 15, 2021"` can be checked by anyone against the document. That is the
difference between a record somebody can trust and one they have to redo, so
this refuses a resolution that looks like a bare verdict.
"""

import argparse
import csv
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKLIST = os.path.join(BASE, "qa", "worklist.csv")

STATUSES = ("open", "done", "escalated", "deferred")

# A verdict with nothing behind it.  Not exhaustive -- it cannot be -- but it
# catches the shapes a hurried run actually produces.
BARE = re.compile(r"^\s*(wrong[- ]doc|no[- ]change|resolved|fixed|ok|done|"
                  r"correct|invalid|bad|verified)\W*$", re.I)


def load():
    with open(WORKLIST, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return rows, list(rows[0].keys()) if rows else []


def save(rows, fields):
    with open(WORKLIST, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stem", nargs="?")
    ap.add_argument("--status", choices=STATUSES)
    ap.add_argument("--resolution")
    ap.add_argument("--bucket", help="with --show, list one bucket")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    rows, fields = load()

    if args.show:
        sel = [r for r in rows
               if (not args.bucket or r.get("bucket") == args.bucket)
               and (not args.stem or r["stem"] == args.stem)]
        if not sel:
            sys.exit("nothing matches")
        by = {}
        for r in sel:
            by.setdefault(r.get("status", "open"), []).append(r)
        for status in STATUSES:
            got = by.get(status) or []
            if not got:
                continue
            print(f"\n{status.upper()}  ({len(got)})")
            for r in got:
                print(f"  {r['stem']:<20} {(r.get('resolution') or r['summary'])[:88]}")
        print(f"\n{len(sel)} rows"
              f"{' in ' + args.bucket if args.bucket else ''}")
        return

    if not (args.stem and args.status):
        sys.exit("give a stem and --status, or use --show")

    if args.status in ("done", "escalated") and not args.resolution:
        sys.exit(f"--status {args.status} needs --resolution saying what was read")

    if args.resolution and BARE.match(args.resolution):
        sys.exit(f"'{args.resolution}' is a verdict, not a resolution. Say what "
                 f"the document actually says: a month from now nobody can check "
                 f"a bare verdict, and the record has to be redone.")

    hit = [r for r in rows if r["stem"] == args.stem]
    if not hit:
        sys.exit(f"{args.stem} is not in the worklist")
    for r in hit:
        r["status"] = args.status
        if args.resolution:
            r["resolution"] = args.resolution
    save(rows, fields)
    print(f"{args.stem}: {args.status}")
    if args.resolution:
        print(f"  {args.resolution[:100]}")


if __name__ == "__main__":
    main()
