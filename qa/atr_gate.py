"""Decide which pre-2021 records are fit to publish beside the 2021-2026 corpus.

The bar is not "the parse succeeded". A pre-2021 record is weaker evidence than
a 2021-2026 one by construction: it was cut out of a two-hundred-page report by
a locator that is sometimes wrong, and read by the cheap model. Publishing all
of them would put town meeting minutes and arithmetically impossible contests
on the same page as a clerk's certified return, and the page would stop meaning
anything.

So the gate is a ladder, and a record's rung is stated in the record rather
than decided by whoever looks at it next:

    publish   the arithmetic closes, every figure was read, every candidate has
              a name, and a ballot count can be derived from contests that agree
    review    sound in itself but something is unresolved -- no ballot count, a
              seat count nobody could establish, an unreadable figure
    hold      the arithmetic is impossible, or the transcriber says the
              document is not a return at all

`hold` is not a bin. A record held because the document is wrong is a LOCATOR
failure with a known fix -- re-cut that report -- and it is counted separately
from one held because its figures do not add up, which needs a human with the
page. Collapsing the two would hide which pile is which, and only one of them
gets smaller by spending money on a better model.
"""
import argparse
import collections
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import escalate                                      # noqa: E402


def grade(doc):
    """(rung, reasons) for one bridged record."""
    contests = doc.get("elections") or []
    reasons = []
    if not contests:
        return "hold", ["the parse found no contest in this section"]

    verdict, why = escalate.review(doc)
    wrong_doc = [w for w in why if w.startswith("the document is not a return")]
    if wrong_doc:
        return "hold", wrong_doc
    impossible = [w for w in why if "impossible" in w]
    if impossible:
        return "hold", impossible

    soft = ("no two contests agree", "seat count left null", "not readable",
            "figure was not readable")
    unresolved = [w for w in why if any(s in w for s in soft)]
    if unresolved:
        return "review", unresolved

    # A bridged record that could not resolve its own date is not publishable:
    # the site indexes by municipality and date, and a null date puts the
    # record nowhere.
    if not (contests[0].get("date")):
        return "review", ["no election date could be derived"]

    if verdict == "escalate":
        return "review", why[:2]
    return "publish", reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridged", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--ledger", default="atr_gate.csv")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    counts = collections.Counter()
    why_counts = collections.Counter()
    rows = []
    if a.apply and a.out:
        for rung in ("publish", "review", "hold"):
            os.makedirs(os.path.join(a.out, rung), exist_ok=True)

    for path in sorted(glob.glob(os.path.join(a.bridged, "*.json"))):
        doc = json.load(io.open(path, encoding="utf-8"))
        rung, reasons = grade(doc)
        counts[rung] += 1
        stem = doc.get("_source_stem") or os.path.basename(path)[:-5]
        if reasons:
            why_counts[reasons[0][:58]] += 1
        rows.append([stem, rung, len(doc.get("elections") or []),
                     reasons[0] if reasons else ""])
        doc["_gate"] = rung
        doc["_gate_reasons"] = reasons
        if a.apply and a.out:
            io.open(os.path.join(a.out, rung, stem + ".json"), "w",
                    encoding="utf-8").write(
                        json.dumps(doc, indent=1, ensure_ascii=False))

    import csv
    with io.open(a.ledger, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["stem", "rung", "contests", "reason"])
        w.writerows(rows)

    total = sum(counts.values())
    for rung in ("publish", "review", "hold"):
        print("  %-8s %5d  %3d%%" % (rung, counts[rung],
                                     counts[rung] * 100 // max(total, 1)))
    print("\n  commonest reason for not publishing:")
    for why, n in why_counts.most_common(6):
        print("    %4d  %s" % (n, why))
    print("\n  ledger: %s" % a.ledger)
    if not a.apply:
        print("  DRY RUN. Nothing written. Pass --apply.")


if __name__ == "__main__":
    main()
