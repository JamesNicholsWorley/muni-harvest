"""Turn the QA report into an ordered queue of work.

`qa/layers.py` says what is wrong.  This says what to do first, and keeps the
answer stable across runs so an unattended agent can pick up where the last one
stopped without two runs racing on the same town-year.

Ordering is severity first, then size.  A wrong figure in Quincy is read by more
people than a wrong figure in Gosnold and the work is the same, so size breaks
ties -- but a FAIL in a small town still outranks a NOTE in a large one.

Size is registered voters, from the Secretary of the Commonwealth interpolated
to each election date (`config/denominators.csv`, 351 municipalities, 2021-2026).
Where a town-year is missing from that table it falls back to `ballots_cast` and
then to the largest contest, so a gap in the denominators cannot silently sort a
record to the bottom of the queue.

The queue is a file in the repository, which is the only coordination mechanism
available: cloud sessions get a fresh clone and there is no lock to take.  An
agent claims rows by writing `in_progress` with its run id and pushing before it
starts work, so a second run sees the claim.  That is advisory, not safe against
a true race -- two runs starting in the same minute can both claim.  Runs are
hours apart by design, which is what makes it hold.

    python -m qa.worklist                 # rebuild from the latest report
    python -m qa.worklist --top 20        # show what is next
"""

import argparse
import collections
import csv
import glob
import json
import math
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(BASE, "qa", "layers_report.csv")
WORKLIST = os.path.join(BASE, "qa", "worklist.csv")

FIELDS = ["stem", "priority", "size", "worst_verdict", "layer", "findings",
          "summary", "status", "claimed_by", "claimed_at", "resolution"]

# A finding's weight.  Layer 0 outranks everything: no later check recovers from
# the wrong document, so fixing anything else about that record is wasted work.
WEIGHT = {
    (0, "FAIL"): 1000,
    (1, "FAIL"): 300,
    (2, "FAIL"): 200,
    (3, "FAIL"): 150,
    (0, "NOTE"): 40,
    (2, "NOTE"): 5,
    (0, "UNKNOWN"): 60,
    (1, "UNKNOWN"): 20,
    (2, "UNKNOWN"): 10,
}


DENOMINATORS = os.path.join(BASE, "config", "denominators.csv")


def registered_voters():
    """Registered voters per town-year, from the Secretary of the Commonwealth.

    Interpolated to each election date (`basis` says how: interpolated, carried
    or snapshot).  This is the honest measure of how many people a record is
    about -- 438,041 in Boston 2021, a few hundred in the smallest towns -- and
    it is why size belongs in the ordering at all.
    """
    reg = {}
    if not os.path.exists(DENOMINATORS):
        return reg
    for r in csv.DictReader(open(DENOMINATORS, encoding="utf-8")):
        try:
            reg[r["municipality"].replace(" ", "") + r["year"]] = int(r["registered"])
        except (ValueError, KeyError):
            continue
    return reg


def record_size(stem, corpus_dir, reg=None):
    """How many people this record is about.

    Registered voters where we have them, ballots cast otherwise, and the
    largest contest as a last resort.  The fallbacks matter: a town-year missing
    from the denominators should not silently sort to the bottom.
    """
    if reg:
        v = reg.get(stem)
        if v:
            return v
    p = os.path.join(corpus_dir, stem + ".json")
    if not os.path.exists(p):
        return 0
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return 0
    b = d.get("ballots_cast")
    if isinstance(b, int) and b > 0:
        return b
    biggest = 0
    for e in d.get("elections") or []:
        t = sum(c.get("votes") or 0 for c in (e.get("candidates") or [])
                if isinstance(c.get("votes"), int) and c.get("votes") > 0)
        biggest = max(biggest, t)
    return biggest


def build(corpus_dir):
    reg = registered_voters()
    rows = list(csv.DictReader(open(REPORT, encoding="utf-8")))
    by_stem = collections.defaultdict(list)
    for r in rows:
        if r["verdict"] == "PASS":
            continue
        by_stem[r["stem"]].append(r)

    # A NOTE is "unusual and true" -- it describes the document, it is not work.
    # A record whose only findings are notes does not belong in a queue somebody
    # is meant to drain, or the queue reads as 1,612 problems when it is 300.
    by_stem = {k: v for k, v in by_stem.items()
               if any(f["verdict"] in ("FAIL", "UNKNOWN") for f in v)}

    # Carry forward anything already claimed or resolved.  A rebuild must never
    # silently reopen work somebody did, or hand the same row to a second agent.
    prior = {}
    if os.path.exists(WORKLIST):
        for r in csv.DictReader(open(WORKLIST, encoding="utf-8")):
            prior[r["stem"]] = r

    out = []
    for stem, findings in by_stem.items():
        size = record_size(stem, corpus_dir, reg)
        score = sum(WEIGHT.get((int(f["layer"]), f["verdict"]), 1) for f in findings)
        worst = min(findings, key=lambda f: (
            0 if f["verdict"] == "FAIL" else 1, int(f["layer"])))
        p = prior.get(stem, {})
        out.append({
            "stem": stem,
            # Size scales the severity score rather than replacing it, so a
            # layer-0 failure in a small town still outranks a note in a city.
            # The log keeps Boston from swamping the queue: it is 438,041
            # registered voters against a few hundred in the smallest towns, and
            # a linear factor would put every city ahead of every real defect.
            "priority": round(score * (1 + math.log10(1 + size / 100.0)), 1),
            "size": size,
            "worst_verdict": worst["verdict"],
            "layer": worst["layer"],
            "findings": len(findings),
            "summary": f'{worst["check"]}: {worst["evidence"][:110]}',
            "status": p.get("status") or "open",
            "claimed_by": p.get("claimed_by", ""),
            "claimed_at": p.get("claimed_at", ""),
            "resolution": p.get("resolution", ""),
        })
    out.sort(key=lambda r: -r["priority"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=os.path.join(BASE, "data", "json"),
                    help="directory of <Stem>.json records")
    ap.add_argument("--top", type=int, default=0)
    args = ap.parse_args()

    if not os.path.exists(REPORT):
        raise SystemExit(f"no report at {REPORT}; run `python -m qa.layers` first")

    rows = build(args.corpus)
    with open(WORKLIST, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    st = collections.Counter(r["status"] for r in rows)
    print(f"town-years needing work: {len(rows)}  ->  {os.path.relpath(WORKLIST, BASE)}")
    print(f"status: {dict(st)}")
    print()
    n = args.top or 15
    print(f"{'priority':>9}  {'size':>7}  {'L':>1} {'verdict':<8} stem")
    print("-" * 92)
    for r in [x for x in rows if x["status"] == "open"][:n]:
        print(f'{r["priority"]:>9}  {r["size"]:>7}  {r["layer"]:>1} '
              f'{r["worst_verdict"]:<8} {r["stem"]:<18} {r["summary"][:44]}')


if __name__ == "__main__":
    main()
