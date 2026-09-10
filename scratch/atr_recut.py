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
        rec = {"stem": stem, "status": "", "pages": 0, "pick": "",
               "score": 0, "runner_up": 0, "reaches_a_tally": "",
               "ballot_words": 0, "mean_line": 0, "detail": ""}
        try:
            doc = pymupdf.open(os.path.join(a.reports, path))
            rec["pages"] = doc.page_count
            texts = page_texts(doc, a.ocr,
                               os.path.join(a.out, "_%s.png" % stem))
            scored = S.score_pages(None, texts)
            if not scored:
                rec["status"] = ("NO_SECTION" if any(t.strip() for t in texts)
                                 else "NEEDS_OCR")
            else:
                page = scored[0][1]
                lo, hi, capped = S.grow(texts, page, doc.page_count)
                cut = pymupdf.open()
                cut.insert_pdf(doc, from_page=lo, to_page=hi)
                cut.save(os.path.join(a.out, "pdf", "%s_atr.pdf" % stem),
                         garbage=4, deflate=True)
                f = features(texts[page])
                tally = [i + 1 for i in range(lo, hi + 1)
                         if S.is_tally(texts[i])]
                rec.update(status="OK", pick=page + 1, score=scored[0][0],
                           runner_up=scored[1][3] if len(scored) > 1 else 0,
                           reaches_a_tally="yes" if tally else "",
                           ballot_words=f["b"], mean_line=round(f["prose"]),
                           detail="cut %d-%d of %d; tally pages %s"
                           % (lo + 1, hi + 1, doc.page_count,
                              tally or "none"))
            doc.close()
        except Exception as e:
            rec["status"] = "ERROR"
            rec["detail"] = "%s: %s" % (type(e).__name__, str(e)[:100])
        rows.append(rec)
        print("  %-11s %-22s p%-5s b=%-3s %s"
              % (rec["status"], stem, rec["pick"], rec["ballot_words"],
                 rec["detail"][:52]), flush=True)

    with io.open(os.path.join(a.out, "manifest.csv"), "w", encoding="utf-8",
                 newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if r["status"] == "OK"]
    reach = [r for r in ok if r["reaches_a_tally"]]
    print("\n  %d cut, %d of them reaching a page of tallies" % (len(ok),
                                                                 len(reach)))


if __name__ == "__main__":
    main()
