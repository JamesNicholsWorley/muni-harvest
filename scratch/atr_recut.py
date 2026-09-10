"""Re-cut a fetched Annual Town Report with the re-ranked locator.

Reads reports from /tmp/reports, writes sections to <out>/pdf and a manifest
recording, for every report, what BOTH rankings chose. The comparison is the
point: a re-cut that moves the window is a claim about which page is the
return, and the manifest is where that claim can be checked without refetching
2,900 reports.
"""
import argparse
import csv
import io
import json
import os
import subprocess
import sys

import pymupdf

pymupdf.TOOLS.mupdf_display_errors(False)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import atr_sections as S                            # noqa: E402
from scratch.atr_pagefeat import features                      # noqa: E402


def ocr_page(page, tmp):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(150 / 72, 150 / 72))
    pix.save(tmp)
    try:
        r = subprocess.run(["tesseract", tmp, "stdout", "-l", "eng",
                            "--psm", "6"], capture_output=True, text=True,
                           timeout=120)
        return r.stdout or ""
    except Exception:
        return ""
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def page_texts(doc, ocr, tmp):
    out = []
    for i, page in enumerate(doc):
        t = page.get_text()
        out.append(t if t.strip() or not ocr else ocr_page(page, tmp))
    return out


def old_scored(texts):
    return S.score_pages(None, texts)


def new_scored(texts):
    """Same pages, re-ranked. Never narrows what is eligible.

    Eligibility is left exactly where `atr_sections.score_pages` put it,
    because that is the leniency Hawley's all-uncontested return needs and
    Petersham and Newbury were thrown away for. What changes is the ORDER: a
    report names its election on the warrant page, in the officers directory
    and in the contents, and all three carry headings and office words, so the
    old score could not tell them from the return. Ballot vocabulary, a table
    of names against figures, and the absence of warrant articles can.
    """
    out = []
    for score, i, h, b, o in S.score_pages(None, texts):
        f = features(texts[i])
        s = (score + 2 * f["b"] + min(f["ints"], 120) // 10
             + min(f["names"], 40) // 5
             - 3 * f["article"] - 4 * f["state"]
             - (10 if f["prose"] >= 30 else 0))
        out.append((s, i, h, b, o))
    out.sort(reverse=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", default="/tmp/reports")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--stems", default="")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "pdf"), exist_ok=True)

    want = set(open(a.stems).read().split()) if a.stems else None
    rows = []
    for path in sorted(os.listdir(a.reports)):
        if not path.endswith(".pdf"):
            continue
        stem = path[:-4]
        if want and stem not in want:
            continue
        rec = {"stem": stem, "status": "", "pages": 0, "old_pick": "",
               "new_pick": "", "old_score": 0, "new_score": 0, "moved": "",
               "ballot_words": 0, "mean_line": 0, "detail": ""}
        try:
            doc = pymupdf.open(os.path.join(a.reports, path))
            rec["pages"] = doc.page_count
            texts = page_texts(doc, a.ocr,
                               os.path.join(a.out, "_%s.png" % stem))
            old, new = old_scored(texts), new_scored(texts)
            if not new:
                rec["status"] = ("NO_SECTION" if any(t.strip() for t in texts)
                                 else "NEEDS_OCR")
            else:
                lo, hi, capped = S.grow(texts, new[0][1], doc.page_count)
                cut = pymupdf.open()
                cut.insert_pdf(doc, from_page=lo, to_page=hi)
                cut.save(os.path.join(a.out, "pdf", "%s_atr.pdf" % stem),
                         garbage=4, deflate=True)
                f = features(texts[new[0][1]])
                rec.update(status="OK", old_pick=old[0][1] + 1,
                           new_pick=new[0][1] + 1, old_score=old[0][0],
                           new_score=new[0][0],
                           moved="yes" if old[0][1] != new[0][1] else "",
                           ballot_words=f["b"], mean_line=round(f["prose"]),
                           detail="cut %d-%d of %d" % (lo + 1, hi + 1,
                                                       doc.page_count))
            doc.close()
        except Exception as e:
            rec["status"] = "ERROR"
            rec["detail"] = "%s: %s" % (type(e).__name__, str(e)[:100])
        rows.append(rec)
        print("  %-11s %-22s old p%-5s new p%-5s b=%-3s %s"
              % (rec["status"], stem, rec["old_pick"], rec["new_pick"],
                 rec["ballot_words"], rec["detail"][:40]), flush=True)

    with io.open(os.path.join(a.out, "manifest.csv"), "w", encoding="utf-8",
                 newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if r["status"] == "OK"]
    moved = [r for r in ok if r["moved"]]
    looks = [r for r in ok if r["ballot_words"] >= 3 and r["mean_line"] < 30]
    print("\n  %d cut, %d moved off the old page, %d land on a tabular page "
          "carrying ballot vocabulary" % (len(ok), len(moved), len(looks)))


if __name__ == "__main__":
    main()
