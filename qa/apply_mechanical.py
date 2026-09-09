"""Apply the mechanical repairs across a parsed corpus, and log every one.

Dry run by default. Each repair is written to a CSV ledger carrying the numbers
that justify it, so a reviewer can disagree with any single row without having
to re-derive the whole pass.

Two things are deliberately not repaired here. A contest whose page is quoted
as printing a seat count that the arithmetic contradicts is REPORTED, because
the page and the figures cannot both be right and only the document says which.
And a doubling that no single row accounts for is reported too -- if two rows
would each close the sum, the arithmetic cannot say which was duplicated.
"""
import argparse
import csv
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import mechanical                                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--ledger", default="mechanical_repairs.csv")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    rows = []
    counts = {"seats fixed": 0, "seats reported": 0, "duplicate row removed": 0,
              "still impossible": 0, "records touched": 0}

    for path in sorted(glob.glob(os.path.join(a.parsed, "*.json"))):
        doc = json.load(io.open(path, encoding="utf-8"))
        rec = doc.get("record")
        if not (isinstance(rec, dict) and isinstance(rec.get("elections"), list)):
            continue
        el = rec["elections"]
        ballots = mechanical.derive_ballots(el)
        if not ballots:
            continue
        touched = False

        for contest in el:
            if not isinstance(contest, dict):
                continue
            office = str(contest.get("office_original") or "")[:60]

            dup = mechanical.find_doubled_row(contest)
            if dup:
                i, name = dup
                rows.append([doc["stem"], office, "duplicate row removed",
                             contest.get("num_winners"), "",
                             "row %r duplicated the printed total %s"
                             % (name, contest.get("printed_total"))])
                if a.apply:
                    contest["candidates"].pop(i)
                    contest.setdefault("problems", []).append(
                        "a duplicate row %r was removed: the contest summed to "
                        "exactly twice its own printed total" % name)
                counts["duplicate row removed"] += 1
                touched = True

            verdict = mechanical.fix_seat_count(contest, ballots)
            if not verdict:
                continue
            kind, implied, note = verdict
            rows.append([doc["stem"], office, kind.lower() + " seat count",
                         contest.get("num_winners"), implied, note])
            if kind == "FIX":
                counts["seats fixed"] += 1
                if a.apply:
                    contest["num_winners"] = implied
                    contest["num_winners_source"] = "derived"
                    contest["num_winners_basis"] = note
                touched = True
            else:
                counts["seats reported"] += 1

        if touched:
            counts["records touched"] += 1
            if a.apply:
                doc["record"] = rec
                doc["mechanically_repaired"] = True
                io.open(path, "w", encoding="utf-8").write(
                    json.dumps(doc, indent=1, ensure_ascii=False))

    with io.open(a.ledger, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["stem", "office", "action", "was", "becomes", "reason"])
        w.writerows(rows)

    for k, v in counts.items():
        print("  %-24s %d" % (k, v))
    print("\nledger: %s (%d rows)" % (a.ledger, len(rows)))
    if not a.apply:
        print("DRY RUN. Nothing written. Pass --apply.")


if __name__ == "__main__":
    main()
