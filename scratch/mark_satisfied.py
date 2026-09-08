"""Five ledger rows whose correction is already in the record -- and a trap.

Each of these was refused as ambiguous because the value it replaces appeared
twice in the record.  The correction has since landed upstream, so only ONE of
the two places still holds that value -- and it is the OTHER one, the one that
was always correct.  The ambiguity that protected these rows is gone, and the
by-value search now finds a single, wrong target:

    Chicopee 2021   row means COUNCILOR WARD 2 'Others' 6 -> 7.  Ward 2 already
                    holds 7; the only 6 left is COUNCILOR WARD 7, where it is
                    right.  Applying it would put 7 in Ward 7.
    Granville 2023  row means Library Trustee Kinsman 143 -> 148.  Kinsman
                    already holds 148; the only 143 left is Moderator Richard
                    N. Pierce.  (Two rows, 115 and 342, say the same thing.)
    Orleans 2023    row means TRUSTEE FOR SNOW LIBRARY 'Others' 1 -> 2.  Snow
                    Library already holds 2; the only 1 left is ELEMENTARY
                    SCHOOL COMMITTEE.
    Plympton 2021   row means PLANNING BOARD - 5 Year Cohen 35 -> 33.  Cohen
                    already holds 33; the only 35 left is Nathaniel Sides in
                    FINANCE - 3 Years, where it is right.

So these must not be re-verified.  `qa.apply` skips a row whose status is
`applied` or `needs-owner`, and both are safe; what is not safe is a later run
reading "a session verified this" and setting `verified` to unstick it.  The
note goes in the row so it is read where the decision is made.

Every one was checked against the record and against its own block's
arithmetic before this was written:

    Chicopee 2021 WARD 2   349 + 7 + 106 = 462
    Granville 2023 Library 148 + 0 + 20  = 168, the hand-written total
    Orleans 2023 Snow Lib. 1171 + 1161 + 718 + 2 = 3052 = 1526 x 2
    Plympton 2021 Planning 33 + 20 + 354 + 10 = 417 = the ballot count x 1
"""

import csv
import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")

NOTE = (" || SATISFIED 2026-09-08: the record already holds the corrected "
        "value, and the block closes on it. DO NOT set this row 'verified' to "
        "unstick it: the duplicate that made it ambiguous is gone, so the "
        "by-value search now finds exactly one place -- {other} -- which is a "
        "DIFFERENT contest whose figure is correct. Applying it would corrupt "
        "that one.")

WHERE = {
    ("Chicopee2021", "6"): "COUNCILOR WARD 7 'Others' = 6",
    ("Granville2023", "143"): "Moderator / Richard N. Pierce = 143",
    ("Orleans2023", "1"): "ELEMENTARY SCHOOL COMMITTEE 'Others' = 1",
    ("Plympton2021", "35"): "FINANCE - 3 Years / Nathaniel Sides = 35",
}


def main():
    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    n = 0
    for r in rows:
        key = (r["stem"], (r.get("was") or "").strip())
        if key in WHERE and "SATISFIED" not in (r.get("why") or ""):
            r["why"] = (r.get("why") or "") + NOTE.format(other=WHERE[key])
            n += 1
            print(f"noted: {r['stem']:<16} {r['was']} -> {r['should_be']}")
    if "--write" in sys.argv and n:
        with io.open(LEDGER, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})
        print(f"\n{n} rows noted")
    else:
        print("\nnothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
