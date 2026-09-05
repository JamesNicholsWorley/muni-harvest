"""Documents that need OCR, so nobody reads the same scan twice.

A document with no text layer still has to be read, and a run reads it by
rendering the pages and looking at them. That works, and it is expensive, and it
buys nothing for the next run: the pages are rendered again, looked at again,
and the reading is gone the moment the session ends.

So a run that reads a scan by eye also records it here. Something later runs
Tesseract over the queue and writes `data/raw_ocr/<Stem>.txt`, and from then on
the document is readable by anything -- the grounding checks included, which is
the part that matters. A scan nobody has OCR'd is invisible to every check that
looks for a name or a figure in the text.

    python -m qa.ocr_queue --add Salem2023 --why "21-page compilation, no text layer"
    python -m qa.ocr_queue                       # what is waiting
    python -m qa.ocr_queue --run                 # OCR everything queued
    python -m qa.ocr_queue --run --limit 20      # or a few

`--run` needs Tesseract, which the cloud environment's setup script installs. It
is deliberately a separate command: OCR of a long scan takes minutes, and a run
working a bucket should queue the work and move on rather than stop to do it.

The queue is a file in the repository because that is the only durable thing a
cloud session has. It is also the audit trail: a stem sitting here with a date
and a reason is a documented gap, which is the difference between "we have not
read this" and silence.
"""

import argparse
import csv
import datetime
import glob
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(BASE, "qa", "ocr_queue.csv")
FIELDS = ["stem", "why", "queued_on", "status", "chars", "done_on"]


def load():
    if not os.path.exists(QUEUE):
        return []
    with open(QUEUE, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def save(rows):
    with open(QUEUE, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def add(stem, why):
    rows = load()
    for r in rows:
        if r["stem"] == stem:
            print(f"{stem} is already queued ({r['status']})")
            return
    rows.append({
        "stem": stem, "why": why,
        "queued_on": datetime.date.today().isoformat(),
        "status": "waiting", "chars": "", "done_on": "",
    })
    save(rows)
    print(f"queued {stem}")


def run(limit):
    """Tesseract over the waiting stems, one page image at a time.

    Page-at-a-time with the image deleted after each page: a runner has 14 GB of
    disk and a long scan at 300 DPI will exhaust it otherwise.
    """
    rows = load()
    waiting = [r for r in rows if r["status"] == "waiting"][:limit or None]
    if not waiting:
        print("nothing waiting")
        return
    for r in waiting:
        stem = r["stem"]
        pdf = os.path.join(BASE, "data", "pdfs", stem + ".pdf")
        if not os.path.exists(pdf):
            r["status"] = "no-document"
            print(f"  {stem}: no PDF held")
            continue
        out = os.path.join(BASE, "data", "raw_ocr", stem + ".txt")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        text = []
        try:
            info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True)
            pages = 1
            for line in info.stdout.splitlines():
                if line.startswith("Pages:"):
                    pages = int(line.split()[1])
        except FileNotFoundError:
            sys.exit("pdfinfo not found; poppler-utils is not installed here")

        for page in range(1, pages + 1):
            img = os.path.join(BASE, f"_ocr_{stem}_{page}")
            subprocess.run(["pdftoppm", "-r", "300", "-png", "-f", str(page),
                            "-l", str(page), pdf, img], capture_output=True)
            got = glob.glob(img + "*.png")
            if not got:
                continue
            t = subprocess.run(["tesseract", got[0], "stdout", "-l", "eng"],
                               capture_output=True, text=True)
            text.append(t.stdout)
            for f in got:
                os.remove(f)

        body = "\n".join(text).strip()
        # An OCR that produced almost nothing is not a reading, and writing it
        # would make the document look read.  Prefer the honest empty.
        if len(body) < 40:
            r["status"] = "failed"
            r["chars"] = str(len(body))
            print(f"  {stem}: OCR produced {len(body)} chars -- not a reading")
            continue
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(body)
        r["status"] = "done"
        r["chars"] = str(len(body))
        r["done_on"] = datetime.date.today().isoformat()
        print(f"  {stem}: {len(body)} chars -> data/raw_ocr/{stem}.txt")
    save(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", metavar="STEM")
    ap.add_argument("--why", default="no text layer")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if args.add:
        return add(args.add, args.why)
    if args.run:
        return run(args.limit)

    rows = load()
    if not rows:
        print("queue is empty")
        return
    import collections
    c = collections.Counter(r["status"] for r in rows)
    print(f"{len(rows)} in the queue: {dict(c)}\n")
    for r in rows:
        if r["status"] == "waiting":
            print(f"  {r['stem']:<20} {r['why'][:60]}  (since {r['queued_on']})")


if __name__ == "__main__":
    main()
