"""Cut one town's rows out of a PD43 volume as an image.

A volume is six hundred pages and twenty megabytes. Nothing that wants to check
one town's figures should have to open it, and no agent should be asked to read
a page to find four numbers. This finds the town, works out how far its entry
runs, and writes a tight image of exactly that.

    python tools/pd43_crop.py --year 1996 --town Abington
    python tools/pd43_crop.py --year 1996 --worklist pd43/worklist.csv --limit 20
    python tools/pd43_crop.py --year 2008 --page 20 --block 0      # a whole block

The image is written under pd43/crops/ as <year>-<town>.png, and the path is
printed so a caller can pick it up.
"""
import argparse
import csv
import io
import os
import re
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pymupdf.TOOLS.mupdf_display_errors(False)
from tools.pd43_turnout import (table_pages, block_split, page_blocks,      # noqa: E402
                                label_w)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZOOM = 4.0
# How far below the town's name its entry can run. A town with eighteen
# precincts is the largest in the series; twenty rows of headroom covers it.
ROWS_BELOW = 20


def find_town(doc, pages, town):
    """(page index, y of the name, block bounds) for a town's entry."""
    pat = re.compile(r'\b' + re.escape(town.split()[0]) + r'\b')
    for i in pages:
        page = doc[i]
        for w in page.get_text('words'):
            if pat.match(w[4]) or w[4] == town:
                blocks = page_blocks(page)
                sp = block_split(page)
                if blocks and len(blocks) == 1:
                    lo, hi = 0, page.rect.width
                elif sp:
                    lo, hi = (0, sp) if w[0] < sp else (sp, page.rect.width)
                else:
                    lo, hi = 0, page.rect.width
                return i, w[1], (lo, hi)
    return None, None, None


def row_height(page, lo, hi, y):
    """Roughly how tall a printed row is here, from the words around it."""
    ys = sorted({round(w[1], 1) for w in page.get_text('words')
                 if lo <= w[0] < hi and y - 40 <= w[1] <= y + 120})
    gaps = [b - a for a, b in zip(ys, ys[1:]) if 2 < b - a < 40]
    gaps.sort()
    return gaps[len(gaps) // 2] if gaps else 9.0


def crop(year, town, out_dir, pad_rows=ROWS_BELOW):
    pdf = os.path.join(ROOT, 'pd43', 'pd43-%s.pdf' % year)
    flat = os.path.join(ROOT, 'pd43', 'pd43-%s-flat.pdf' % year)
    src = flat if os.path.exists(flat) else pdf
    if not os.path.exists(src):
        return None, 'no volume for %s' % year
    doc = pymupdf.open(src)
    pages = [i for _k, p in table_pages(doc) for i in p]
    if not pages:
        return None, 'no table pages in %s' % year
    i, y, bounds = find_town(doc, pages, town)
    if i is None:
        return None, '%s not found in %s' % (town, year)

    page = doc[i]
    lo, hi = bounds
    h = row_height(page, lo, hi, y)
    top = max(0, y - h * 1.6)
    bot = min(page.rect.height, y + h * pad_rows)
    # Keep the column headings in view: a reader needs to know which figure is
    # registered voters and which is turnout.
    # ROOM AT THE RIGHT EDGE. The block boundary falls in the gutter, which is
    # about where the People Who Voted column ends, so cutting exactly at it
    # shaves the last digit off that column -- Belmont's 4,771 came out as
    # `4,77`. A few points of margin costs nothing and a clipped digit is
    # unrecoverable by any check, because the figure that survives still looks
    # like a figure.
    hi = min(page.rect.width, hi + 10)
    lo = max(0, lo - 2)
    head = pymupdf.Rect(lo, page.rect.height * 0.10, hi, page.rect.height * 0.16)
    body = pymupdf.Rect(lo, top, hi, bot)

    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r'[^A-Za-z0-9]+', '', town)
    path = os.path.join(out_dir, '%s-%s.png' % (year, slug))

    m = pymupdf.Matrix(ZOOM, ZOOM)
    hpix = page.get_pixmap(matrix=m, clip=head)
    bpix = page.get_pixmap(matrix=m, clip=body)
    # Heading above the rows, in one image.
    out = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(
        0, 0, max(hpix.width, bpix.width), hpix.height + bpix.height), False)
    out.clear_with(255)
    out.copy(hpix, pymupdf.IRect(0, 0, hpix.width, hpix.height))
    bpix.set_origin(0, hpix.height)
    out.copy(bpix, pymupdf.IRect(0, hpix.height, bpix.width,
                                 hpix.height + bpix.height))
    out.save(path)
    return path, 'page %d, block x %.0f-%.0f' % (i + 1, lo, hi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--year')
    ap.add_argument('--town')
    ap.add_argument('--worklist')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--out', default=os.path.join(ROOT, 'pd43', 'crops'))
    a = ap.parse_args()

    if a.worklist:
        rows = list(csv.DictReader(io.open(a.worklist, encoding='utf-8')))
        if a.year:
            rows = [r for r in rows if r['year'] == a.year]
        if a.limit:
            rows = rows[:a.limit]
        for r in rows:
            path, why = crop(r['year'], r['municipality'], a.out)
            print('%-5s %-20s %s' % (r['year'], r['municipality'],
                                     path or ('SKIP ' + why)))
        return

    if not (a.year and a.town):
        ap.error('give --year and --town, or --worklist')
    path, why = crop(a.year, a.town, a.out)
    print(path or ('could not crop: ' + why))
    if path:
        print(why)


if __name__ == '__main__':
    main()
