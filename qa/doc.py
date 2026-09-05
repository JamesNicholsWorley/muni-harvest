"""Read a document, the way a run actually needs to read one.

The rule is that nothing changes without opening the document. This is what
opening it costs, so it should not cost a session forty minutes of improvisation.
The first run of the loop hand-rolled all of this: `pdftoppm` at a guessed DPI,
then PIL code to crop the top fifth of twenty-one pages and stitch them into one
image so the headings could be scanned at a glance. That was a good idea and it
should not have to be had twice.

    python -m qa.doc Salem2023              what we hold, and its sha256
    python -m qa.doc Salem2023 --text       the best text reading available
    python -m qa.doc Salem2023 --headers    top of every page, stitched
    python -m qa.doc Salem2023 --pages 1-3  those pages as images

`--headers` is the one that earns its place. A 21-page compilation of every
election a city held in a year is not something to read page by page; what
settles it is the heading on each page, and those fit in one image. It is how
Salem 2023 was identified as a compilation rather than a preliminary.

Images land in a scratch directory and the path is printed. Read them with the
Read tool -- that is what "open the document" means when there is no text layer.
"""

import argparse
import glob
import hashlib
import os
import re
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
PAGES = "https://jamesnicholsworley.github.io/civicatlasma"


def pdf_path(stem):
    for p in (os.path.join(DATA, "pdfs", stem + ".pdf"),
              os.path.join(DATA, "pdfs", stem + "_d0.pdf")):
        if os.path.exists(p):
            return p
    return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def text_of(stem):
    """The best reading we hold, and which store it came from.

    Order matters: raw_ocr is a real read of the pixels and beats a text layer
    that extracted to placeholders, which is why `unsearchable-blind-spot`
    exists. markdown is the extraction; pdftext is the fallback.
    """
    for rel in (f"data/raw_ocr/{stem}.txt", f"data/markdown/{stem}.md",
                f"data/pdftext/{stem}.txt"):
        p = os.path.join(BASE, rel)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                t = fh.read()
            # A placeholder-only extraction is not a reading.  Say so rather
            # than handing back something that looks like text and is not.
            stripped = re.sub(r"<!--.*?-->", "", t, flags=re.S).strip()
            if len(stripped) > 40:
                return t, rel
    return None, None


def render(stem, first, last, dpi, out_dir):
    p = pdf_path(stem)
    if not p:
        return []
    os.makedirs(out_dir, exist_ok=True)
    prefix = os.path.join(out_dir, stem)
    try:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png",
                        "-f", str(first), "-l", str(last), p, prefix],
                       capture_output=True, timeout=300)
    except FileNotFoundError:
        sys.exit("pdftoppm not found. It comes with poppler-utils, which the "
                 "cloud environment's setup script installs; on a local Windows "
                 "checkout it will not be there.")
    return sorted(glob.glob(prefix + "-*.png"))


def headers(stem, out_dir, dpi=110, fraction=0.20):
    """Top slice of every page, stitched vertically into one image.

    A long document is identified by its headings, not by reading it through.
    One image of twenty-one headings answers "what is this" in a single look.
    """
    try:
        from PIL import Image
    except ImportError:
        sys.exit("Pillow is not installed: pip install pillow")
    n = pages_in(stem)
    if not n:
        return None
    files = render(stem, 1, n, dpi, out_dir)
    if not files:
        return None
    strips = []
    for f in files:
        im = Image.open(f)
        w, h = im.size
        strips.append(im.crop((0, 0, w, int(h * fraction))))
    width = max(s.width for s in strips)
    total = sum(s.height for s in strips)
    sheet = Image.new("RGB", (width, total), "white")
    y = 0
    for s in strips:
        sheet.paste(s, (0, y))
        y += s.height
    out = os.path.join(out_dir, f"{stem}_headers.png")
    sheet.save(out)
    for f in files:
        os.remove(f)
    return out


def pages_in(stem):
    p = pdf_path(stem)
    if not p:
        return 0
    try:
        r = subprocess.run(["pdfinfo", p], capture_output=True, text=True)
    except FileNotFoundError:
        # poppler is installed in the cloud environment by the setup script and
        # is usually absent on a Windows checkout.  Say so instead of crashing:
        # the rest of this tool still works without it.
        return None
    m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stem")
    ap.add_argument("--text", action="store_true")
    ap.add_argument("--headers", action="store_true")
    ap.add_argument("--pages", help="e.g. 1-3")
    ap.add_argument("--dpi", type=int, default=130)
    ap.add_argument("--chars", type=int, default=2000)
    args = ap.parse_args()

    stem = args.stem
    p = pdf_path(stem)
    t, src = text_of(stem)

    if args.text:
        if not t:
            sys.exit(f"no readable text held for {stem}. "
                     f"{'Render the pages: --headers or --pages' if p else 'No document either.'}")
        print(f"# {src}\n")
        print(t[:args.chars])
        return

    out_dir = os.path.join(tempfile.gettempdir(), "qa-doc")

    if args.headers:
        got = headers(stem, out_dir)
        print(got or f"cannot render {stem}: no PDF held")
        return

    if args.pages:
        a, _, b = args.pages.partition("-")
        files = render(stem, int(a), int(b or a), args.dpi, out_dir)
        print("\n".join(files) or f"cannot render {stem}: no PDF held")
        return

    # default: what we hold
    print(f"stem        {stem}")
    print(f"pdf         {p or '(none held)'}")
    if p:
        print(f"sha256      {sha256(p)}")
        n = pages_in(stem)
        print(f"pages       {n if n is not None else '(pdfinfo not installed)'}")
    print(f"text        {src or '(none readable)'}"
          f"{f'  {len(t)} chars' if t else ''}")
    print(f"published   {PAGES}/pdfs/{stem}_d0.pdf")
    if not t and p:
        print()
        print("No text layer. Render it: --headers for the whole document at a "
              "glance, --pages 1-3 for detail. An illegible OCR is not an "
              "illegible document.")


if __name__ == "__main__":
    main()
