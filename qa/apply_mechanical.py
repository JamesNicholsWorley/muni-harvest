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
    counts = {"questions moved": 0, "figures summed from precincts": 0,
              "residual rows closed": 0, "seats fixed": 0, "seats reported": 0,
              "duplicate row removed": 0, "records touched": 0}

    for path in sorted(glob.glob(os.path.join(a.parsed, "*.json"))):
        doc = json.load(io.open(path, encoding="utf-8"))
        rec = doc.get("record")
        if not (isinstance(rec, dict) and isinstance(rec.get("elections"), list)):
            continue
        touched = False

        # A question is in the wrong field of the right record, so it moves
        # before anything reads the contests -- it has no seat count, so
        # leaving it in place teaches the ballot arithmetic to see a race with
        # no seats and the gate to withhold the whole return over it.
        keep = []
        for contest in rec["elections"]:
            if isinstance(contest, dict) and mechanical.ballot_question(contest):
                rows.append([doc["stem"],
                             str(contest.get("office_original") or "")[:60],
                             "ballot question moved to `questions`", "", "",
                             "rows are %s -- a question, not an office"
                             % ", ".join(repr(c.get("name_original"))
                                         for c in (contest.get("candidates")
                                                   or [])[:4])])
                counts["questions moved"] += 1
                touched = True
                if a.apply:
                    rec.setdefault("questions", []).append(
                        contest.get("office_original"))
                    continue
            keep.append(contest)
        if a.apply:
            rec["elections"] = keep
        el = [c for c in rec["elections"] if isinstance(c, dict)]

        trustworthy, agreeing, _ = mechanical.breakdown_is_precincts_only(el)
        for contest in el:
            office = str(contest.get("office_original") or "")[:60]
            if trustworthy:
                for i, total, note in mechanical.sum_from_precincts(contest):
                    rows.append([doc["stem"], office,
                                 "figure summed from its precincts", "", total,
                                 "%s; %d rows in this record close against "
                                 "their own breakdown, so the columns are "
                                 "precincts" % (note, agreeing)])
                    counts["figures summed from precincts"] += 1
                    touched = True
                    if a.apply:
                        contest["candidates"][i]["votes"] = total
            closed = mechanical.close_residual_row(contest)
            if closed:
                i, total, note = closed
                rows.append([doc["stem"], office,
                             "residual row closed against the printed total",
                             "", total, note])
                counts["residual rows closed"] += 1
                touched = True
                if a.apply:
                    contest["candidates"][i]["votes"] = total

        ballots = mechanical.derive_ballots(el)
        if not ballots:
            if touched and a.apply:
                counts["records touched"] += 1
                doc["record"] = rec
                doc["mechanically_repaired"] = True
                io.open(path, "w", encoding="utf-8").write(
                    json.dumps(doc, indent=1, ensure_ascii=False))
            continue

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
