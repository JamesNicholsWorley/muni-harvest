"""Score candidate re-rankings against the reports whose old cut held no return.

A cut is judged by whether the WINDOW it produces contains a tally page --
ballot vocabulary laid out as a table, which is the shape `atr_sections.is_tally`
already names -- not by whether the top page looks right. Plymouth heads its
return on one page and prints eleven pages of tallies after the warrant, so the
page that scores is often the run-up and the tallies are what the window has to
reach.

The old ranking is scored the same way on the same reports, so the number that
matters is the difference.
"""
import json
import os
import sys

import pymupdf

pymupdf.TOOLS.mupdf_display_errors(False)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import atr_sections as S                            # noqa: E402
from scratch.atr_pagefeat import features                      # noqa: E402


def variants(f, base):
    tab = f["prose"] < 30
    fig = min(f["ints"], 120) // 10 + min(f["names"], 40) // 5
    return {"old": base,
            "b then old": (f["b"], base),
            "b x6": (base + 6 * f["b"],),
            "b then old, tabular first": (f["b"], tab, base)}


def window_holds_a_tally(texts, page, n):
    lo, hi, _ = S.grow(texts, page, n)
    return any(S.is_tally(texts[i]) for i in range(lo, hi + 1)), (lo, hi)


def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else "/tmp/recut_eval.json"
    names = None
    hits = {}
    detail = {}
    for path in sorted(os.listdir("/tmp/reports")):
        if not path.endswith(".pdf"):
            continue
        stem = path[:-4]
        try:
            doc = pymupdf.open(os.path.join("/tmp/reports", path))
            texts = [p.get_text() for p in doc]
            n = doc.page_count
            doc.close()
        except Exception:
            continue
        scored = S.score_pages(None, texts)
        if not scored:
            continue
        feats = {i: features(texts[i]) for _, i, _, _, _ in scored}
        picks = {}
        for base, i, _, _, _ in scored:
            for k, v in variants(feats[i], base).items():
                v = v if isinstance(v, tuple) else (v,)
                if v > picks.get(k, ((-10 ** 9,), 0))[0]:
                    picks[k] = (v, i)
        if names is None:
            names = sorted(picks)
            hits = dict.fromkeys(names, 0)
        detail[stem] = {}
        for k in names:
            ok, win = window_holds_a_tally(texts, picks[k][1], n)
            hits[k] += ok
            detail[stem][k] = [picks[k][1] + 1, win[0] + 1, win[1] + 1, ok]
    print("reports scored: %d\n" % len(detail))
    for k in names:
        print("  %-20s %3d windows reach a tally page" % (k, hits[k]))
    json.dump(detail, open(cache, "w"))


if __name__ == "__main__":
    main()
