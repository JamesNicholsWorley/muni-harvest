"""Find vote counts that were COMPUTED from a rounded percentage, not read.

Weymouth 2023 holds Hedlund 5088, Cowen 1218, Others 478 in the Mayor contest.
None of the three is printed anywhere in the only reading held.  What the
article prints is "won 75% of the 6,784 votes cast in the race" and "received
18%", and 0.75 x 6784 = 5088, 0.18 x 6784 = 1221 (the record's 1218 is 17.95%),
and 6784 - 5088 - 1218 = 478.  The figures are arithmetic on a rounded
percentage wearing the clothes of a transcription.

That matters more than an ungrounded figure usually does.  A percentage rounded
to a whole number is worth +/- 34 ballots on a 6,784-vote race, so the record
states a margin it cannot know, and every downstream check reads it as read.

This does not correct anything -- the true count is not recoverable from a
rounded percentage, so there is nothing to correct TO.  It measures the class.
"""

import collections
import csv
import glob
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402

RE_PCT = re.compile(r"(\d{1,3}(?:\.\d)?)\s*(?:%|percent)", re.I)
RE_TOTAL = re.compile(r"(?<![\d,])(\d{1,3}(?:,\d{3})+|\d{2,7})(?![\d,])")


def reconstructions(value, pcts, totals):
    """Every (pct, total) whose product rounds to `value`, at any rounding."""
    out = []
    for p in pcts:
        for t in totals:
            x = p * t / 100.0
            if abs(x - value) < 1.0:
                out.append((p, t))
    return out


def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(BASE, "data", "json", "*.json"))):
        stem = os.path.basename(p)[:-5]
        text, source = layers.document_text(stem)
        if source != "news_text" or not text:
            continue
        record = json.load(open(p, encoding="utf-8"))
        pcts = sorted({float(x) for x in RE_PCT.findall(text)})
        totals = sorted({int(x.replace(",", "")) for x in RE_TOTAL.findall(text)
                         if 20 <= int(x.replace(",", "")) <= 500000})
        if not pcts or not totals:
            continue
        for e in record.get("elections") or []:
            for c in e.get("candidates") or []:
                v = layers.votes_of(c)
                if v is None or v < 20:
                    continue
                if layers.figure_found(v, text):
                    continue
                hits = reconstructions(v, pcts, totals)
                if hits:
                    rows.append((stem, str(e.get("office_original"))[:30],
                                 layers.name_of(c)[:24], v, hits[0]))
    by_stem = collections.defaultdict(list)
    for r in rows:
        by_stem[r[0]].append(r)
    print(f"{len(rows)} ungrounded figures in {len(by_stem)} news-sourced "
          f"records are reproducible as percentage x total\n")
    for stem in sorted(by_stem):
        for _, office, name, v, (p, t) in by_stem[stem]:
            print(f"{stem:<20} {office:<30} {name:<24} {v:>7} = {p}% x {t}")


if __name__ == "__main__":
    main()
