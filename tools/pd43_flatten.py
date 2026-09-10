"""Turn a sideways two-up scan into an upright one-page-per-page PDF.

THE ODD-YEAR BOOKLETS WERE SCANNED AS SPREADS, ON THEIR SIDE. Each PDF page of
the 1971 booklet holds TWO printed pages, rotated ninety degrees, and carries no
text layer. OCR of such a page returns noise -- not because the scan is poor, it
is perfectly legible, but because it is the wrong way up and two pages wide.

That is why five volumes of the series read as empty. They are the only volumes
covering CITY elections and odd-year town elections, so they are worth
straightening rather than writing off.

This writes a new PDF with one upright printed page per page, which the ordinary
reader then handles with no special cases at all.

    python tools/pd43_flatten.py pd43/pd43-1971.pdf --out pd43/pd43-1971-flat.pdf
"""
import argparse
import io
import os

import pymupdf

pymupdf.TOOLS.mupdf_display_errors(False)

_TESS = os.path.join(r'C:\Program Files', 'Tesseract-OCR', 'tesseract.exe')
try:
    import pytesseract
    if os.path.exists(_TESS):
        pytesseract.pytesseract.tesseract_cmd = _TESS
except ImportError:
    pytesseract = None


def score(page, rot, half):
    """How much readable English a given orientation yields.

    Tesseract on a sideways page returns a page of consonant salad, and on an
    upright one returns words. Counting tokens that look like words separates
    them without anyone having to look.
    """
    if pytesseract is None:
        return 0
    from PIL import Image
    r = page.rect
    clip = (pymupdf.Rect(r.x0, r.y0, r.x1, r.y0 + r.height / 2) if half == 0
            else pymupdf.Rect(r.x0, r.y0 + r.height / 2, r.x1, r.y1))
    m = pymupdf.Matrix(1.6, 1.6).prerotate(rot)
    try:
        pix = page.get_pixmap(matrix=m, clip=clip)
        txt = pytesseract.image_to_string(
            Image.open(io.BytesIO(pix.tobytes('png'))), config='--psm 6')
    except Exception:
        return 0
    import re
    words = re.findall(r'\b[A-Za-z]{4,}\b', txt)
    return len(words)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--out', required=True)
    ap.add_argument('--rotate', type=int, default=None,
                    help='force a rotation instead of detecting one')
    ap.add_argument('--halves', type=int, default=2)
    ap.add_argument('--auto', action='store_true',
                    help='decide whether this volume needs flattening at all, '
                         'and do nothing if it does not')
    a = ap.parse_args()

    src = pymupdf.open(a.pdf)

    if a.auto:
        # ONLY THE SIDEWAYS TWO-UP BOOKLETS NEED THIS. A spread holding two
        # printed pages on its side is markedly wider for its height than a
        # single page: the 1971 booklet is 592x789 where 1973, which is already
        # upright and single, is 282x476. Flattening a volume that does not need
        # it halves every page and destroys it, which is what happened to 1973,
        # 1975, 1977 and 1979 before this test existed.
        r = src[len(src) // 3].rect
        ratio = r.width / r.height
        if not (ratio > 0.70 and len(src) < 200):
            print('[skip] %s is %.0fx%.0f (ratio %.2f, %d pages): upright '
                  'single pages, nothing to flatten'
                  % (os.path.basename(a.pdf), r.width, r.height, ratio,
                     len(src)))
            return
        print('[auto] %s looks like a sideways two-up scan (ratio %.2f)'
              % (os.path.basename(a.pdf), ratio))

    rot = a.rotate
    if rot is None:
        # Decide once, on a page from the middle of the book, and apply it to
        # all: a volume is scanned in one pass and one orientation.
        mid = len(src) // 2
        best = (-1, 0)
        for r in (0, 90, 180, 270):
            s = sum(score(src[mid + k], r, 0) for k in (0, 2, 4)
                    if mid + k < len(src))
            print('   rotation %3d -> %d readable words' % (r, s))
            if s > best[0]:
                best = (s, r)
        rot = best[1]
        print('   using rotation %d' % rot)

    out = pymupdf.open()
    for page in src:
        r = page.rect
        halves = ([r] if a.halves == 1 else
                  [pymupdf.Rect(r.x0, r.y0, r.x1, r.y0 + r.height / 2),
                   pymupdf.Rect(r.x0, r.y0 + r.height / 2, r.x1, r.y1)])
        # Bottom half first when the sheet is rotated 90 degrees clockwise: the
        # printed page order runs up the sheet, not down it.
        if rot == 90:
            halves = halves[::-1]
        for clip in halves:
            w, h = clip.width, clip.height
            if rot in (90, 270):
                w, h = h, w
            new = out.new_page(width=w, height=h)
            new.show_pdf_page(new.rect, src, page.number, clip=clip,
                              rotate=rot)
    out.save(a.out)
    print('[OK] %s: %d pages -> %s: %d pages'
          % (os.path.basename(a.pdf), len(src), os.path.basename(a.out),
             len(out)))


if __name__ == '__main__':
    main()
