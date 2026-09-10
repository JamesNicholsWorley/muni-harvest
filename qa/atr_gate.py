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
              a name
    review    sound in itself but something is unresolved -- a seat count
              nobody could establish, an unreadable figure, no derivable date
    hold      the arithmetic is impossible, or the transcriber says the
              document is not a return at all

The bar is calibrated against the corpus these records would join rather than
invented. Run over the 1,900 already-published 2021-2026 records, this gate
passes 80% of them -- so a pre-2021 record is being asked to clear the same
height as the material beside it, not a higher one. An earlier version was
stricter than the live standard, which is not caution but inconsistency: what
justifies more doubt about these records is their provenance, and that is
carried in the record for a reader to weigh rather than enforced by
withholding.

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
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import escalate                                      # noqa: E402
from qa import layers                                        # noqa: E402


def section_text(sections, stem):
    """The text of the section this record was cut from, or None.

    None means there is nothing to ground against -- either the section is not
    held, or it is a scan whose pages carry no text layer. That is a different
    answer from "the figures are not on the page", and the difference is the
    whole point: 91 of these sections are scans, and treating an unreadable
    section as an ungrounded record would condemn every one of them.
    """
    if not sections:
        return None
    path = os.path.join(sections, stem + "_atr.pdf")
    if not os.path.exists(path):
        return None
    try:
        import pymupdf
        doc = pymupdf.open(path)
        text = "\n".join(p.get_text() for p in doc)
    except Exception:
        return None
    return text if layers.readable_chars(text) >= 200 else None


def grounding(doc, text):
    """(figures_found, figures, names_found, names) against the page. Or None."""
    if text is None:
        return None
    got = {}
    for row in layers.layer1_grounded("", doc, text, "the section"):
        m = re.search(r"(\d+)/(\d+)", row[4])
        if m:
            got[row[2]] = (int(m.group(1)), int(m.group(2)))
    if not got:
        return None
    f = got.get("figures_grounded", (0, 0))
    n = got.get("names_grounded", (0, 0))
    return f + n


def grade(doc, text=None):
    """(rung, reasons) for one bridged record."""
    contests = doc.get("elections") or []
    reasons = []
    if not contests:
        return "hold", ["the parse found no contest in this section"]

    # Layer 0 asks whether this is the right document at all, and zero support
    # is its answer that it is not. Carver 2014's cut is a financial statement,
    # the report's INDEX -- "Annual Town Election Results, 4/26/14 .... 10" --
    # and a blank page, and the record read from it holds nine contests with
    # named candidates and vote totals, not one of which is printed anywhere on
    # those three pages. It was graded publishable and published.
    #
    # Only ZERO is treated as a wrong document. A section that grounds
    # partially is usually a cut that holds part of a longer return, and
    # condemning those would cost far more than it saved.
    ground = grounding(doc, text)
    if ground and ground[1] and ground[0] == 0 and ground[2] == 0:
        return "hold", ["not one of the %d figures in this record is printed "
                        "on the page it was cut from, and none of its %d names"
                        % (ground[1], ground[3])]

    verdict, why = escalate.review(doc)
    wrong_doc = [w for w in why if w.startswith("the document is not a return")]
    if wrong_doc:
        return "hold", wrong_doc
    # A state election, a state primary or a county race is a right reading of
    # the wrong election. It cannot be repaired by re-reading the page and it
    # must never occupy an annual town-year slot, so it is held rather than
    # reviewed -- the fix is a different cut of the same report.
    out_of_scope = [w for w in why
                    if w.startswith("this is not an annual municipal election")]
    if out_of_scope:
        return "hold", out_of_scope
    impossible = [w for w in why if "impossible" in w]
    if impossible:
        return "hold", impossible

    # An underivable ballot count is a gap in our ability to CHECK, not a
    # defect in what was read, and 294 records already published share
    # it. Recorded, not withheld.
    uncheckable = [w for w in why if "no two contests agree" in w]

    soft = ("seat count left null", "not readable",
            "figure was not readable")
    unresolved = [w for w in why if any(s in w for s in soft)]
    if unresolved:
        return "review", unresolved

    # A bridged record that could not resolve its own date is not publishable:
    # the site indexes by municipality and date, and a null date puts the
    # record nowhere.
    if not (contests[0].get("date")):
        return "review", ["no election date could be derived"]

    if verdict == "escalate" and not (set(why) <= set(uncheckable)):
        return "review", why[:2]
    return "publish", uncheckable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridged", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--ledger", default="atr_gate.csv")
    ap.add_argument("--sections", default="",
                    help="directory of <Stem>_atr.pdf sections to ground against")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    counts = collections.Counter()
    why_counts = collections.Counter()
    rows = []
    if a.apply and a.out:
        for rung in ("publish", "review", "hold"):
            os.makedirs(os.path.join(a.out, rung), exist_ok=True)

    # A town-year may be published once. Two stems reaching the same
    # municipality and date is the fiscal-year offset -- a 2020 report carrying
    # May 2019 -- and both cannot stand.
    claims = {}
    for path in sorted(glob.glob(os.path.join(a.bridged, "*.json"))):
        doc = json.load(io.open(path, encoding="utf-8"))
        el = doc.get("elections") or []
        if not el:
            continue
        key = (el[0].get("municipality"), (el[0].get("date") or "")[:4])
        if not all(key):
            continue
        claims.setdefault(key, []).append(
            (len(el), doc.get("_source_stem") or os.path.basename(path)[:-5]))
    # The record reading more contests read more of the page. A tie is not
    # broken by filename, which is the thing already shown unreliable here.
    loser = {}
    # `contenders`, not `rows` -- `rows` is the ledger being built below, and
    # shadowing it here wrote a leaked tuple into the CSV as a data row.
    for key, contenders in claims.items():
        if len(contenders) < 2:
            continue
        contenders.sort(reverse=True)
        if contenders[0][0] == contenders[1][0]:
            for _, stem in contenders:
                loser[stem] = ("two records claim %s %s and hold the same "
                               "number of contests; neither can be preferred"
                               % key)
        else:
            for _, stem in contenders[1:]:
                loser[stem] = ("%s %s is already published from %s, which read "
                               "more of the page"
                               % (key[0], key[1], contenders[0][1]))

    for path in sorted(glob.glob(os.path.join(a.bridged, "*.json"))):
        doc = json.load(io.open(path, encoding="utf-8"))
        stem_now = doc.get("_source_stem") or os.path.basename(path)[:-5]
        text = section_text(a.sections, stem_now)
        if stem_now in loser:
            rung, reasons = "review", [loser[stem_now]]
        else:
            rung, reasons = grade(doc, text)
        counts[rung] += 1
        stem = doc.get("_source_stem") or os.path.basename(path)[:-5]
        if reasons:
            why_counts[reasons[0][:58]] += 1
        rows.append([stem, rung, len(doc.get("elections") or []),
                     reasons[0] if reasons else ""])
        doc["_gate"] = rung
        doc["_gate_reasons"] = reasons
        # How much of the record the page itself corroborates travels with the
        # record. A reader can then tell a checked record from an unchecked
        # one, which is the distinction the coverage pages currently cannot
        # make: "a record shown here without a flag has not necessarily been
        # verified -- it may only be unchecked, and the two look identical".
        ground = grounding(doc, text)
        if ground:
            doc["_grounded"] = {"figures": "%d/%d" % ground[:2],
                                "names": "%d/%d" % ground[2:]}
        elif a.sections:
            doc["_grounded"] = {"figures": "no text held for this section",
                                "names": "no text held for this section"}
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
