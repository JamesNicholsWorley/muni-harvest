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
from qa import atr_gate                                     # noqa: E402
from qa import mechanical                                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--ledger", default="mechanical_repairs.csv")
    ap.add_argument("--sections", default="",
                    help="directory of <Stem>_atr.pdf, to check a derived "
                         "figure against the page before writing it")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    rows = []
    counts = {"seats fixed": 0, "seats reported": 0, "duplicate row removed": 0,
              "seats derived where none printed": 0,
              "unreadable figure recovered": 0,
              "still impossible": 0, "records touched": 0}

    for path in sorted(glob.glob(os.path.join(a.parsed, "*.json"))):
        doc = json.load(io.open(path, encoding="utf-8"))
        rec = doc.get("record")
        if not (isinstance(rec, dict) and isinstance(rec.get("elections"), list)):
            continue
        el = rec["elections"]
        touched = False
        text = atr_gate.section_text(a.sections, doc["stem"])

        # First, because a figure recovered here is a figure the ballot count
        # below is derived from. It needs the printed total and the page and
        # nothing else, so it runs on records that cannot derive a count at all.
        for contest in el:
            if not isinstance(contest, dict):
                continue
            fill = mechanical.fill_unreadable_figure(contest, text)
            if not fill:
                continue
            i, value = fill
            name = contest["candidates"][i].get("name_original")
            rows.append([doc["stem"], str(contest.get("office_original") or "")[:60],
                         "unreadable figure recovered", "", value,
                         "%r was the only unreadable row; the printed total %s "
                         "leaves %d for it, and the page prints %d"
                         % (name, contest.get("printed_total"), value, value)])
            if a.apply:
                contest["candidates"][i]["votes"] = value
                contest.setdefault("problems", []).append(
                    "the figure for %r was recovered from the printed total "
                    "and found on the page" % name)
            counts["unreadable figure recovered"] += 1
            touched = True

        ballots = mechanical.derive_ballots(el)
        if not ballots:
            if touched:
                counts["records touched"] += 1
                if a.apply:
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

            seats = mechanical.derive_seat_count(contest, ballots)
            if seats:
                note = ("the page printed no seat count; %d marks are exactly "
                        "%dx the ballot count %d"
                        % (mechanical._marks(contest), seats, ballots))
                rows.append([doc["stem"], office, "seats derived where none printed",
                             "", seats, note])
                if a.apply:
                    contest["num_winners"] = seats
                    contest["num_winners_source"] = "derived"
                    contest["num_winners_basis"] = note
                counts["seats derived where none printed"] += 1
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
