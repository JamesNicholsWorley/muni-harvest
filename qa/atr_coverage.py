"""Coverage of the pre-2021 ATR corpus, reported two ways and never one.

Coverage by town-year and coverage weighted by population answer different
questions and differ by more than ten points, so a single number is always the
wrong one to quote. A corpus holding every small hilltown and no city can look
excellent by town-year and cover a fifth of the electorate.

Absence is reported alongside presence. A town-year we never had a document for
and a town-year whose document we could not read are different failures with
different fixes, and collapsing them into "not covered" hides which.
"""
import argparse
import collections
import csv
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import escalate                                     # noqa: E402

YEARS = list(range(2000, 2021))


def load(parsed_dirs):
    """Later directories win, so a Sonnet re-read supersedes the Haiku pass."""
    recs = {}
    for d in parsed_dirs:
        for path in glob.glob(os.path.join(d, "*.json")):
            doc = json.load(io.open(path, encoding="utf-8"))
            rec = doc.get("record")
            if isinstance(rec, dict) and isinstance(rec.get("elections"), list):
                recs[doc["stem"]] = {"record": rec, "model": doc.get("model")}
    return recs


def split(stem):
    m = re.match(r"^(.*?)(\d{4})$", stem)
    return (m.group(1), int(m.group(2))) if m else (stem, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parsed", nargs="+", required=True)
    ap.add_argument("--attempted", required=True,
                    help="every town-year the harvest tried (municipality,year,...)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    recs = load(a.parsed)
    attempted = collections.defaultdict(set)
    with io.open(a.attempted, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            y = int(row["year"])
            if 2000 <= y <= 2020:
                attempted[row["municipality"].replace(" ", "")].add(y)

    usable, empty, flagged = {}, set(), set()
    for stem, d in recs.items():
        el = d["record"].get("elections") or []
        if not el:
            empty.add(stem)
            continue
        verdict, _ = escalate.review(d["record"])
        usable[stem] = len(el)
        if verdict == "escalate":
            flagged.add(stem)

    towns = collections.defaultdict(set)
    for stem in usable:
        t, y = split(stem)
        if 2000 <= y <= 2020:
            towns[t].add(y)

    n_att_towns = len(attempted)
    n_att_ty = sum(len(v) for v in attempted.values())
    n_ty = sum(len(v) for v in towns.values())
    print("PRE-2021 ATR COVERAGE, %d-%d\n" % (YEARS[0], YEARS[-1]))
    print("  town-years with a usable parse   %5d  of %5d attempted  (%d%%)"
          % (n_ty, n_att_ty, n_ty * 100 // max(n_att_ty, 1)))
    print("  municipalities represented       %5d  of %5d attempted  (%d%%)"
          % (len(towns), n_att_towns, len(towns) * 100 // max(n_att_towns, 1)))
    print("  contests                         %5d" % sum(usable.values()))
    print("  parsed but holding no contest    %5d" % len(empty))
    print("  parsed and flagged by escalate   %5d  (%d%% of usable)"
          % (len(flagged), len(flagged) * 100 // max(len(usable), 1)))

    print("\n  by year")
    for y in YEARS:
        n = sum(1 for t in towns if y in towns[t])
        att = sum(1 for t in attempted if y in attempted[t])
        bar = "#" * (n // 4)
        print("    %d  %3d of %3d attempted  %s" % (y, n, att, bar))

    depth = collections.Counter(len(v) for v in towns.values())
    print("\n  years held per municipality")
    for k in sorted(depth):
        print("    %2d year%s  %3d towns" % (k, " " if k == 1 else "s", depth[k]))

    if a.out:
        with io.open(a.out, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["municipality", "years_held", "years",
                        "years_attempted_without_result"])
            for t in sorted(attempted):
                held = sorted(towns.get(t, []))
                miss = sorted(attempted[t] - set(held))
                w.writerow([t, len(held), " ".join(map(str, held)),
                            " ".join(map(str, miss))])
        print("\n  per-town detail written to %s" % a.out)


if __name__ == "__main__":
    main()
