"""Collect the pages the parser does worst on into one small PDF to look at.

Reading a six-hundred-page volume to find the four pages that are failing is not
a thing anyone should do, and describing a page in prose is not the same as
seeing it. This pulls the worst pages out of several volumes, stamps each with
what is wrong with it, and writes one short PDF.

    python tools/pd43_trouble.py --out pd43/trouble-pages.pdf --limit 10

Pages are chosen by measurement, not by hunch: how much text the page carries
against how many municipalities we get off it. A page holding a fifth of a
volume's towns and yielding none of them sorts to the top.
"""
import argparse
import csv
import io
import os
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pymupdf.TOOLS.mupdf_display_errors(False)
from tools.pd43_turnout import table_pages, load_municipalities   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Enough text that the page cannot be a bare scan. Below this a page is an
# image with a running head on it, whatever the table detector claims to find.
TEXT_FLOOR = 800
# Below this the sheet carries a running head and nothing else -- it is blank,
# not unread. Measured: blank pages run about 0.005, full tables above 0.04.
INK_FLOOR = 0.02


def towns_on_page(doc, i, names):
    """How many municipality names the page's own text mentions."""
    t = doc[i].get_text()
    return sum(1 for n in names if n in t)


def ink(doc, i):
    """Fraction of the page that is printed on, from a thumbnail.

    TWO VERY DIFFERENT PAGES BOTH HAVE NO TEXT LAYER, and counting characters
    cannot tell them apart. 2008 page 34 has two characters on it because it is
    a BLANK PAGE -- a running head, and bleed-through from the sheet behind.
    1986 page 17 has a hundred and twenty-three because it is a full table
    printed as an image. Selecting on the text count put the blank pages at the
    top of the list of pages to go and look at, and it inflated every
    image-only percentage I reported, because empty pages were being counted as
    unread tables.

    Ink separates them: a table is several per cent of the sheet, a blank page
    is a fraction of one.
    """
    pix = doc[i].get_pixmap(matrix=pymupdf.Matrix(0.28, 0.28),
                            colorspace=pymupdf.csGRAY)
    data = pix.samples
    if not data:
        return 0.0
    dark = sum(1 for b in data if b < 170)
    return float(dark) / len(data)


def survey(years, names):
    out = []
    for y in years:
        f = os.path.join(ROOT, 'pd43', 'pd43-%s.pdf' % y)
        if not os.path.exists(f):
            continue
        doc = pymupdf.open(f)
        try:
            pages = [(k, i) for k, p in table_pages(doc) for i in p]
        except Exception:
            continue
        for kind, i in pages:
            chars = len(doc[i].get_text().strip())
            out.append({'year': y, 'page': i, 'kind': kind, 'chars': chars,
                        'ink': ink(doc, i),
                        'named': towns_on_page(doc, i, names)})
        doc.close()
    return out


def pick(rows, limit):
    """The worst pages, spread across volumes so one bad year cannot fill it."""
    # A TABLE PRINTED AS AN IMAGE, not a blank sheet. Ink is what tells them
    # apart; the text count cannot.
    blanks = [r for r in rows if r['chars'] < TEXT_FLOOR and r['ink'] > INK_FLOOR]
    blanks.sort(key=lambda r: (-r['ink'], r['year']))
    chosen, per_year = [], {}
    for r in blanks:
        if per_year.get(r['year'], 0) >= 2:
            continue
        chosen.append(r)
        per_year[r['year']] = per_year.get(r['year'], 0) + 1
        if len(chosen) >= limit:
            break
    return chosen


def note_for(r):
    why = ('A FULL TABLE PRINTED AS AN IMAGE: %.1f%% of the sheet is inked but '
           'the text layer holds only %d characters. Every figure here has to '
           'come from OCR.' % (100.0 * r['ink'], r['chars']))
    return '%s  page %d  [%s table]  -  %s' % (r['year'], r['page'] + 1,
                                               r['kind'], why)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'pd43',
                                                  'trouble-pages.pdf'))
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--years', default='')
    a = ap.parse_args()

    years = ([y.strip() for y in a.years.split(',') if y.strip()]
             or [str(y) for y in range(1986, 2019, 2)] + ['1977', '1983'])
    names = load_municipalities(ROOT)
    rows = survey(years, names)
    if not rows:
        print('no table pages found')
        return 1
    chosen = pick(rows, a.limit)
    if not chosen:
        print('no low-text pages found')
        return 1

    out = pymupdf.open()
    for r in chosen:
        src = pymupdf.open(os.path.join(ROOT, 'pd43', 'pd43-%s.pdf' % r['year']))
        out.insert_pdf(src, from_page=r['page'], to_page=r['page'])
        page = out[-1]
        # A caption band at the top, over the margin rather than the table.
        band = pymupdf.Rect(0, 0, page.rect.width, 26)
        page.draw_rect(band, color=None, fill=(1, 1, 0.75), overlay=True)
        page.insert_textbox(pymupdf.Rect(6, 3, page.rect.width - 6, 25),
                            note_for(r), fontsize=6.2, color=(0, 0, 0),
                            overlay=True)
        src.close()
    out.save(a.out)

    print('%d pages -> %s' % (len(chosen), a.out))
    for r in chosen:
        print('   %s' % note_for(r))
    idx = os.path.splitext(a.out)[0] + '.csv'
    with io.open(idx, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year', 'printed_page', 'kind', 'chars_of_text',
                    'ink_fraction', 'municipalities_named_in_text'])
        for r in chosen:
            w.writerow([r['year'], r['page'] + 1, r['kind'], r['chars'],
                        '%.4f' % r['ink'], r['named']])
    print('index -> %s' % idx)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
