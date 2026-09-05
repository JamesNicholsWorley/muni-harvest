"""Assemble `data/` in a cloud session, so the checks measure the same thing.

`data/` is gitignored here -- the corpus is gigabytes and does not belong in a
repository. That is right for the repository and wrong for a fresh clone, which
arrives with the checks but nothing to check. The first run of the loop found
this the hard way: it improvised symlinks, got a partial corpus, and watched
`document_held` go from 14 failures to 210 because 196 documents simply were not
there. It noticed and refused to commit the numbers, which was the correct
instinct, but no run should have to have it.

So this builds `data/` from what a session does hold -- the published corpus in
the `civicatlasma` clone -- and reconstructs the derived stores the checks read.

    python -m qa.bootstrap                 # assemble, then say what is missing
    python -m qa.bootstrap --verify        # report only, change nothing

What it can and cannot reproduce:

  data/json      linked from civicatlasma/json          complete
  data/markdown  linked from civicatlasma/markdown      complete for what is public
  data/pdfs      linked from civicatlasma/pdfs, _d0 stripped from the name
  data/pdftext   extracted here with pdftotext          deterministic, exact
  data/raw_ocr   NOT reproducible without running OCR   see below

`raw_ocr` is the OCR of documents that have no text layer. It cannot be
regenerated from the published corpus without actually running Tesseract over
the scans, which takes real time. Until it is published or rebuilt, a cloud
session sees fewer readable documents than a local one, and `document_held` and
the grounding checks will report worse numbers than the corpus deserves.

**That difference is the point of `--verify`.** A run that compares its counts
against a baseline built somewhere else is comparing two different corpora and
calling the difference a regression. Better to say so than to let a number be
wrong quietly.
"""

import argparse
import glob
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

# A cloud session clones the repositories as siblings.  Local checkouts differ,
# so look in both places rather than assuming one.
CANDIDATE_ROOTS = [
    os.path.join(os.path.dirname(BASE), "civicatlasma"),
    "/home/user/civicatlasma",
    os.path.join(os.path.dirname(BASE), "CivicAtlasMA", "publish"),
]


def find_published():
    for root in CANDIDATE_ROOTS:
        if os.path.isdir(os.path.join(root, "json")):
            return root
    return None


def link(src, dst):
    if os.path.islink(dst) or os.path.exists(dst):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.symlink(src, dst)
    return True


def assemble(published):
    made = {}
    for name in ("json", "markdown", "xlsx"):
        src = os.path.join(published, name)
        if os.path.isdir(src):
            made[name] = link(src, os.path.join(DATA, name))

    # The published documents carry a _d0 suffix; the checks look for <Stem>.pdf.
    # Link rather than copy: 1,575 files and 600 MB, and a copy would be stale
    # the moment the corpus moves.
    pdfs = os.path.join(published, "pdfs")
    if os.path.isdir(pdfs):
        out = os.path.join(DATA, "pdfs")
        os.makedirs(out, exist_ok=True)
        n = 0
        for p in glob.glob(os.path.join(pdfs, "*_d0.pdf")):
            stem = os.path.basename(p)[:-len("_d0.pdf")]
            if link(p, os.path.join(out, stem + ".pdf")):
                n += 1
        made["pdfs"] = n
    return made


def extract_text():
    """Rebuild data/pdftext with pdftotext. Deterministic, so it is safe to
    regenerate rather than publish."""
    out = os.path.join(DATA, "pdftext")
    os.makedirs(out, exist_ok=True)
    done = skipped = failed = 0
    for p in sorted(glob.glob(os.path.join(DATA, "pdfs", "*.pdf"))):
        stem = os.path.basename(p)[:-4]
        target = os.path.join(out, stem + ".txt")
        if os.path.exists(target):
            skipped += 1
            continue
        try:
            r = subprocess.run(["pdftotext", "-layout", p, target],
                               capture_output=True, timeout=90)
            done += 1 if r.returncode == 0 else 0
            failed += 0 if r.returncode == 0 else 1
        except Exception:
            failed += 1
    return done, skipped, failed


def verify():
    """What the checks will and will not be able to read."""
    counts = {}
    for name in ("json", "pdfs", "markdown", "pdftext", "raw_ocr"):
        d = os.path.join(DATA, name)
        counts[name] = len(os.listdir(d)) if os.path.isdir(d) else 0

    records = counts["json"]
    unreadable = []
    for p in sorted(glob.glob(os.path.join(DATA, "json", "*.json"))):
        stem = os.path.basename(p)[:-5]
        if not any(os.path.exists(os.path.join(DATA, d, stem + ext))
                   for d, ext in (("raw_ocr", ".txt"), ("markdown", ".md"),
                                  ("pdftext", ".txt"))):
            unreadable.append(stem)

    print(f"{'store':<12}{'files':>8}")
    print("-" * 20)
    for k, v in counts.items():
        print(f"{k:<12}{v:>8}")
    print()
    print(f"records with no readable text: {len(unreadable)} of {records}")
    if counts["raw_ocr"] == 0:
        print()
        print("data/raw_ocr is empty. It holds the OCR of documents with no text")
        print("layer and cannot be rebuilt from the published corpus without")
        print("running Tesseract over the scans. Until it exists here, the")
        print("grounding checks will report worse numbers than the corpus")
        print("deserves, and a regression comparison against a baseline built")
        print("elsewhere is comparing two different corpora.")
    return len(unreadable)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="report only")
    args = ap.parse_args()

    if not args.verify:
        published = find_published()
        if not published:
            sys.exit("no civicatlasma checkout found; looked in:\n  " +
                     "\n  ".join(CANDIDATE_ROOTS))
        print(f"published corpus: {published}")
        made = assemble(published)
        print(f"linked: {made}")
        done, skipped, failed = extract_text()
        print(f"pdftext: {done} extracted, {skipped} already present, {failed} failed")
        print()
    verify()


if __name__ == "__main__":
    main()
