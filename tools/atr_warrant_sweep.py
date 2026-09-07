"""Find the election warrant in the full Annual Town Report.

`atr_sections.py` cuts around the RETURN, and the warrant is almost never
inside that cut -- it is printed with the town meeting material, often a hundred
pages away. Of 1,327 sections, 22 happened to contain one. So confirming an
uncontested election means going back to the whole report and looking
specifically for the warrant, which is what this does.

It runs only on the town-years that need it: a section with no tally page, whose
return is therefore either uncontested or mis-cut, and where nothing in the cut
can tell those apart. A warrant settles it, because the warrant enumerates the
offices to be filled and the seats for each, so a return listing one name
against each of the warrant's offices is uncontested as a matter of record.

The warrant also supplies the seat count on exactly the documents that never
print one -- small-town returns -- which is the field this corpus gets wrong
most often.
"""
import csv
import io
import os
import subprocess
import sys
import time

import pymupdf
from curl_cffi import requests

# Running `python tools/atr_warrant_sweep.py` puts tools/ on sys.path, not the
# repository root, so the package import below needs the root added first.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import warrant                                   # noqa: E402

SHARD = int(os.environ.get("SHARD", "0"))
SHARDS = int(os.environ.get("SHARDS", "1"))
URL_CSV = os.environ.get("URL_CSV", "config/atr_warrant_urls.csv")
PER_MINUTE = max(1, int(os.environ.get("PER_MINUTE", "20")))
LIMIT = int(os.environ.get("LIMIT", "0"))
OCR = os.environ.get("OCR", "") == "1"
THRESHOLD = int(os.environ.get("THRESHOLD", "6"))
OUT = "warrants_out"

os.makedirs(os.path.join(OUT, "pdf"), exist_ok=True)


def page_texts(doc):
    if not OCR:
        return [p.get_text() for p in doc]
    out = []
    for i, page in enumerate(doc):
        t = page.get_text()
        if t.strip():
            out.append(t)
            continue
        pix = page.get_pixmap(matrix=pymupdf.Matrix(150 / 72, 150 / 72))
        png = os.path.join(OUT, f"_p{i}.png")
        pix.save(png)
        try:
            r = subprocess.run(["tesseract", png, "stdout", "-l", "eng", "--psm", "6"],
                               capture_output=True, text=True, timeout=120)
            out.append(r.stdout or "")
        except Exception:
            out.append("")
        finally:
            if os.path.exists(png):
                os.remove(png)
    return out


def window(texts, best, page_count):
    """A warrant runs a few pages: the summons, then the articles.

    Grown by warrant score rather than by ballot vocabulary, because a warrant
    has none -- that absence is what distinguishes it from the return.
    """
    hi = best
    while (hi + 1 < page_count and hi - best < 6
           and warrant.score_page(texts[hi + 1]) >= 3):
        hi += 1
    return max(0, best - 1), min(page_count - 1, hi + 1)


def main():
    with io.open(URL_CSV, encoding="utf-8", newline="") as fh:
        rows = [r for n, r in enumerate(csv.DictReader(fh)) if n % SHARDS == SHARD]
    if LIMIT:
        rows = rows[:LIMIT]

    manifest = []
    gap = 60.0 / PER_MINUTE
    for row in rows:
        stem = f"{row['municipality'].replace(' ', '')}{row['year']}"
        rec = {"municipality": row["municipality"], "year": row["year"],
               "stem": stem, "url": row["url"], "status": "", "pages": 0,
               "picked": "", "score": 0, "runner_up": 0, "detail": ""}
        t0 = time.time()
        try:
            r = requests.get(row["url"], impersonate="chrome", timeout=90)
            body = r.content or b""
            if r.status_code != 200:
                rec["status"] = f"HTTP_{r.status_code}"
            elif not body.startswith(b"%PDF"):
                rec["status"] = "NOT_PDF"
            else:
                doc = pymupdf.open(stream=body, filetype="pdf")
                rec["pages"] = doc.page_count
                texts = page_texts(doc)
                scored = sorted(((warrant.score_page(t), i)
                                 for i, t in enumerate(texts)), reverse=True)
                if not scored or scored[0][0] < THRESHOLD:
                    has_text = any(t.strip() for t in texts)
                    rec["status"] = "NO_WARRANT" if has_text else "NEEDS_OCR"
                    rec["score"] = scored[0][0] if scored else 0
                else:
                    rec["score"] = scored[0][0]
                    rec["runner_up"] = scored[1][0] if len(scored) > 1 else 0
                    lo, hi = window(texts, scored[0][1], doc.page_count)
                    cut = pymupdf.open()
                    cut.insert_pdf(doc, from_page=lo, to_page=hi)
                    cut.save(os.path.join(OUT, "pdf", f"{stem}_warrant.pdf"),
                             garbage=4, deflate=True)
                    rec["picked"] = f"{lo+1}-{hi+1}"
                    rec["status"] = "OK"
                    rec["detail"] = f"best page {scored[0][1]+1}, score {scored[0][0]}"
        except Exception as e:
            rec["status"] = "ERROR"
            rec["detail"] = f"{type(e).__name__}: {str(e)[:120]}"
        manifest.append(rec)
        print(f"  {rec['status']:<11} {stem:<22} {rec['picked']:<7} {rec['detail'][:50]}",
              flush=True)
        slept = time.time() - t0
        if slept < gap:
            time.sleep(gap - slept)

    with io.open(os.path.join(OUT, f"manifest_{SHARD}.csv"), "w",
                 encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)
    ok = sum(1 for m in manifest if m["status"] == "OK")
    print(f"\nshard {SHARD}: {ok}/{len(manifest)} warrants found")


if __name__ == "__main__":
    main()
