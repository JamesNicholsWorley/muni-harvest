"""Overriding a check, when the check is wrong about a genuinely unusual record.

Some records are strange and correct. A town that elects on the floor of Town
Meeting, a return printed across two documents, a contest whose seat count the
document states in words -- these can fail a check that is right about almost
everything else. Making the agent grind at them forever is waste, and quietly
weakening the check to accommodate them is worse: it blinds the check for the
other 1,899 records too.

So an override is the last resort, and it is deliberately expensive.

**Four things are required, and a row without all four is not an override.**

    stem            which record
    check           which check, exactly.  Never "all checks".
    source_sha256   the document this reasoning was formed against
    read            what was actually READ -- a verbatim quote from the
                    document, not a description of it
    why             what makes this record genuinely unlike the others

`read` is the load-bearing field. An override written without opening the
document is a guess with a signature on it, and the whole point is that somebody
looked. A reviewer must be able to check the quote against the document and
reach the same conclusion, or disagree with it.

**An override does not make a finding pass.** The finding stays in the report
with verdict OVERRIDDEN. It is still counted, still visible, still reviewable.
A mechanism that made findings vanish would hide its own growth.

**An override dies with its document.** It is bound to `source_sha256`, so
replacing the document retires the reasoning rather than silently applying it to
a file nobody examined. This is the rule adjudications already follow.

**Overrides are counted per check, and a pile is a signal.** If many records need
the same check overridden, that check is wrong about a whole class of documents
and should be fixed. `report()` surfaces this, because the alternative is a
system that quietly accumulates exceptions until the check means nothing.

    python -m qa.overrides --report
    python -m qa.overrides --check-stale --corpus <dir>
"""

import argparse
import collections
import csv
import hashlib
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDES = os.path.join(BASE, "qa", "overrides.csv")

FIELDS = ["stem", "check", "source_sha256", "read", "why",
          "decided_by", "decided_on"]

# Above this many overrides on one check, the check is the problem.  The number
# is a judgement, not a discovery: small enough that a real pattern shows early,
# large enough that a handful of genuine oddities does not cry wolf.
PILE = 5


def load():
    """Overrides keyed by (stem, check).  Rows missing any required field are
    ignored rather than honoured -- an incomplete override is not an override."""
    out = {}
    if not os.path.exists(OVERRIDES):
        return out
    with open(OVERRIDES, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not all((r.get(k) or "").strip()
                       for k in ("stem", "check", "source_sha256", "read", "why")):
                continue
            out[(r["stem"], r["check"])] = r
    return out


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def applies(row, doc_path):
    """True only if the override was formed against the document now held.

    A document that has been replaced is a different document, and reasoning
    about the old one says nothing about the new one.
    """
    if not doc_path or not os.path.exists(doc_path):
        return False
    return sha256_of(doc_path) == row["source_sha256"].strip()


def report():
    rows = list(csv.DictReader(open(OVERRIDES, encoding="utf-8"))) \
        if os.path.exists(OVERRIDES) else []
    if not rows:
        print("no overrides recorded")
        return 0
    by_check = collections.Counter(r["check"] for r in rows)
    print(f"{len(rows)} overrides across {len(by_check)} checks\n")
    print(f"{'count':>6}  check")
    print("-" * 56)
    piles = []
    for check, n in by_check.most_common():
        mark = "  <-- the check is probably wrong" if n >= PILE else ""
        print(f"{n:>6}  {check}{mark}")
        if n >= PILE:
            piles.append((check, n))
    if piles:
        print()
        for check, n in piles:
            print(f"{n} records override `{check}`. That is not {n} unique cases; "
                  f"it is a check that is wrong about a class of documents. "
                  f"Fix the check and delete these rows.")
    return len(piles)


def check_stale(corpus_dir):
    """Overrides whose document has changed since the reasoning was written."""
    stale = []
    for (stem, check), r in load().items():
        p = os.path.join(corpus_dir, stem + ".pdf")
        if os.path.exists(p) and not applies(r, p):
            stale.append((stem, check))
    if stale:
        print(f"{len(stale)} override(s) formed against a document we no longer hold:")
        for stem, check in stale:
            print(f"   {stem:<20} {check}  -- reasoning does not apply to the current file")
    else:
        print("no stale overrides")
    return len(stale)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--check-stale", action="store_true")
    ap.add_argument("--corpus", default=os.path.join(BASE, "data", "pdfs"))
    args = ap.parse_args()
    if args.check_stale:
        raise SystemExit(1 if check_stale(args.corpus) else 0)
    report()


if __name__ == "__main__":
    main()
