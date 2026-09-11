"""Read a PD43 town table by finding the towns in the ARITHMETIC first.

THE FIGURES READ CORRECTLY AND THE NAMES DO NOT. That asymmetry holds on every
page tried, in every volume, from either source -- and every reader written so
far keyed the structure on the names, which puts the whole page at the mercy of
the part that fails. Worse, it fails silently in a way that costs double: a row
whose name is lost does not drop out, it becomes a PRECINCT OF THE TOWN ABOVE.
One lost name costs two towns and breaks an arithmetic check that would
otherwise have passed.

Turned around, the table tells you where the towns are without anything having
to be spelled correctly. Walk down the registered column; wherever a value
equals the sum of the next k values, that value is a town total and those k are
its precincts:

    Abington .......... May 9    7,581      <- 1,922 + 1,887 + 1,864 + 1,908
      Pct. 1 ..........          1,922
          2 ..........           1,887
          3 ..........           1,864
          4 ..........           1,908

BOTH LAYOUTS OCCUR AND THE SERIES NEVER SAYS WHICH IT IS USING. 1986 and 1992
put the total at the head of its precincts; 2000 puts the precincts first and
closes them with a TOTALS line. Scanning forward only, not one sum closed on a
perfectly legible page of 2000 -- the arithmetic was right there and being read
the wrong way round. So both directions are tried at every row.

A run that closes in BOTH columns at once is what makes this safe. A coincidence
in one column is common on a page of four hundred numbers; in two simultaneously
it is not.

Names are then read off the same y and attached to a structure that is already
established. A name that fails to snap costs that one town and nothing else.

    python tools/pd43_read.py 1986 --out pd43/out-1986.csv
    python tools/pd43_read.py 1973 --pages 43 --debug
"""
import argparse
import collections
import csv
import io
import os
import re
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pymupdf.TOOLS.mupdf_display_errors(False)
from tools import pd43_turnout as T                                # noqa: E402
from tools.pd43_scope import SECTIONS, stated_counts, needs_ocr    # noqa: E402
from tools.pd43_scope import section, TOWN_HEAD, CITY_HEAD         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# No town in Massachusetts has had more than this many precincts in the period;
# the largest is Framingham at eighteen. The bound matters because an unbounded
# search will always find SOME run of numbers that happens to sum to a value
# further down the column.
MAX_PCTS = 20
# A date is printed between the name and the figures. Split on it rather than
# trying to describe what a town name looks like -- `W. Bridgewater`, `Manchester
# -by-the-Sea` and `Great Barrington` do not share a shape.
DATEWORD = re.compile(
    r'\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d*.*$',
    re.I)


def tokens_from_text(page, clip):
    """-> [(x, y, text)] from the page's own text layer, in PDF points."""
    out = []
    for x0, y0, x1, y1, w, _b, _l, _n in page.get_text('words'):
        if x0 >= clip.x0 and x1 <= clip.x1 and y0 >= clip.y0 and y1 <= clip.y1:
            out.append((x0, (y0 + y1) / 2.0, w))
    return out


def tokens_from_ocr(page, clip, zoom=T.OCR_ZOOM):
    """-> [(x, y, text)] from Tesseract, in image pixels.

    The two token sources are deliberately the same shape and everything below
    works in whatever space it is handed. Nothing downstream uses an absolute
    distance -- row spacing is measured from the page itself -- so a reader that
    works on points works unchanged on pixels.
    """
    import io as _io
    from PIL import Image
    import pytesseract
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
    img = Image.open(_io.BytesIO(pix.tobytes('png')))
    d = pytesseract.image_to_data(img, config='--psm 6',
                                  output_type=pytesseract.Output.DICT)
    out = []
    for i, t in enumerate(d['text']):
        t = (t or '').strip()
        try:
            conf = int(float(d['conf'][i]))
        except (ValueError, TypeError):
            conf = -1
        if t and conf >= 25:
            out.append((d['left'][i], d['top'][i] + d['height'][i] / 2.0, t))
    return out


def columns(nums, width):
    """Cluster numeric tokens by x. -> [(lo, hi)] left to right.

    THE WIDEST GAP IS NOT BETWEEN THE FIGURE COLUMNS. It falls between the
    precinct numbers and the figures, because `Pct. 1, 2, 3` are numbers too, so
    splitting on it hands back the precinct column and everything else as one.
    Cluster instead, and take the columns as they come.
    """
    if not nums:
        return []
    xs = sorted(x for x, _y, _t in nums)
    gap = max(width * 0.035, 6)
    groups, cur = [], [xs[0]]
    for x in xs[1:]:
        if x - cur[-1] > gap:
            groups.append(cur)
            cur = [x]
        else:
            cur.append(x)
    groups.append(cur)
    return [(g[0], g[-1]) for g in groups if len(g) >= 3]


def row_pitch(ys):
    """The distance between one printed row and the next, from the page itself.

    Every tolerance below is a multiple of this rather than a constant, which is
    what lets one reader work on a 282-point booklet page and on a 3x pixmap of
    a letter sheet without knowing which it has.
    """
    ys = sorted(ys)
    gaps = [b - a for a, b in zip(ys, ys[1:]) if b - a > 0]
    if not gaps:
        return 1.0
    gaps.sort()
    return gaps[len(gaps) // 2] or 1.0


def segment(reg, vot):
    """Where the towns are, from the figures alone.

    -> [(index of the total row, [indexes of its precincts])]

    Both directions are tried at every row because both layouts occur. A run
    that closes in both columns beats one that closes in a single column; among
    equals the longer run wins, because a two-precinct town inside a five-
    precinct one will also sum if the first two happen to.
    """
    out, i, n = [], 0, len(reg)
    while i < n:
        best = None
        for k in range(1, min(MAX_PCTS, n - i - 1) + 1):
            if reg[i] is None or None in reg[i + 1:i + 1 + k]:
                break
            if sum(reg[i + 1:i + 1 + k]) == reg[i]:
                both = (vot[i] is not None
                        and None not in vot[i + 1:i + 1 + k]
                        and sum(vot[i + 1:i + 1 + k]) == vot[i])
                score = (1 if both else 0, k)
                if best is None or score > best[0]:
                    best = (score, k, 'head')
        for k in range(1, min(MAX_PCTS, i) + 1):
            if reg[i] is None or None in reg[i - k:i]:
                break
            if sum(reg[i - k:i]) == reg[i]:
                both = (vot[i] is not None and None not in vot[i - k:i]
                        and sum(vot[i - k:i]) == vot[i])
                score = (1 if both else 0, k)
                if best is None or score > best[0]:
                    best = (score, k, 'foot')
        if best and best[2] == 'head':
            k = best[1]
            out.append((i, list(range(i + 1, i + 1 + k)), 'head'))
            i += k + 1
        elif best and best[2] == 'foot':
            k = best[1]
            # THE ROWS ABOVE WERE THIS TOWN'S PRECINCTS ALL ALONG. In the
            # totals-last layout they have already been emitted as undivided
            # towns; the TOTALS line is what names them, so drop them.
            out = [r for r in out if r[0] < i - k]
            out.append((i, list(range(i - k, i)), 'foot'))
            i += 1
        else:
            out.append((i, [], 'single'))   # undivided, or a row that never closed
            i += 1
    return out


def label_lines(labels, pitch):
    """Group label tokens into printed lines. -> [(y, 'text of the line')]

    TAKING THE NEAREST SINGLE TOKEN OPENED PHANTOM TOWNS. A row's label is
    `Abington ....... May 24`, and the nearest token to the figure was as often
    `May` or `24` as the name. `May` passed for a municipality, a heading called
    May opened, and every undivided town beneath it became one of its precincts
    -- 213 rows swallowed by four phantoms in 1986 alone.
    """
    lines = []
    for x, y, t in sorted(labels, key=lambda l: (l[1], l[0])):
        if lines and y - lines[-1][0] <= pitch * 0.6:
            lines[-1][1].append((x, t))
        else:
            lines.append([y, [(x, t)]])
    return [(y, ' '.join(t for _x, t in sorted(ts))) for y, ts in lines]


def clean_name(raw):
    """`Abington ......... May 24` -> `Abington`."""
    s = T.LEADER.sub(' ', raw or '')
    s = DATEWORD.sub('', s)
    s = re.sub(r'\s+', ' ', s).strip(' .,-')
    return s


def read_block(page, clip, names, use_ocr, year=None, pitch_hint=None):
    """One column block -> [town dicts]. The whole method, in order."""
    toks = tokens_from_ocr(page, clip) if use_ocr \
        else tokens_from_text(page, clip)
    if not toks:
        return [], {}
    nums, labels = [], []
    for x, y, t in toks:
        v = T.num(t)
        # A BARE FOUR-DIGIT YEAR IS A DATE, NOT A FIGURE. From 1994 the date
        # column prints the year -- `....April 3, 2012` -- and that token sits
        # in the same x band a figure would. Twenty-one towns in 2008 and
        # Marblehead in 2012 were emitted registering 2008 and 2012 voters.
        #
        # The table separates its thousands, so a figure of two thousand prints
        # as `2,012` and the year prints as `2012`. That is the difference, and
        # it is the volume's own typography rather than a threshold.
        if v is not None and v == year and re.fullmatch(r'\d{4}', t):
            continue
        if v is not None and not T.PCT.match(t):
            nums.append((x, y, v))
        else:
            labels.append((x, y, t))
    width = max(x for x, _y, _t in toks) - min(x for x, _y, _t in toks) or 1
    cols = columns(nums, width)
    # THE DATE COLUMN IS A COLUMN OF NUMBERS. From 1994 the volumes print the
    # year in the date -- `....April 3, 2012` -- so `2012` clusters into a
    # column of its own, in exactly the place a figure column would be. Towns
    # came out registering 2012 voters and 2008 voters: Marblehead (2012,
    # None), North Attleborough (2008, None), four more on that page alone.
    #
    # A figure column does not print the same value on every row. Drop any
    # column that is mostly the election year, rather than trying to recognise
    # a date from the label beside it.
    if year:
        cols = [c for c in cols
                if sum(1 for x, _y, v in nums
                       if c[0] - 1 <= x <= c[1] + 1 and v == year)
                <= 0.5 * max(1, sum(1 for x, _y, _v in nums
                                    if c[0] - 1 <= x <= c[1] + 1))]
    if len(cols) < 2:
        return [], {'reason': 'fewer than two figure columns'}
    # THE FIGURE COLUMNS ARE THE TWO RIGHTMOST. Everything to their left is
    # precinct numbers and page furniture.
    (r0, r1), (v0, v1) = cols[-2], cols[-1]
    pitch = pitch_hint or row_pitch([y for _x, y, _t in nums])

    regs = sorted((y, v) for x, y, v in nums if r0 - 1 <= x <= r1 + 1)
    vots = sorted((y, v) for x, y, v in nums if v0 - 1 <= x <= v1 + 1)
    rows = []
    for y, r in regs:
        near = [w for w in vots if abs(w[0] - y) <= pitch * 0.6]
        rows.append((y, r, near[0][1] if near else None))

    runs = segment([r for _y, r, _v in rows], [v for _y, _r, v in rows])
    lines = label_lines(labels, pitch)

    def name_at(y):
        near = [ln for ln in lines if abs(ln[0] - y) <= pitch * 0.7]
        return clean_name(near[0][1]) if near else ''

    def name_above(y):
        """The last label line above y that is not itself part of the table.

        IN THE TOTALS-LAST LAYOUT THE LABEL ON THE TOTAL ROW IS THE WORD
        `TOTALS`. The town's name heads its precincts, a row above the first of
        them, and reading the name off the row that carries the figures --
        correct for 1986, where the total heads the block -- returned `TOTALS`
        for every town in 2000, 2012 and 2016. Those volumes produced no
        municipalities at all while their arithmetic was closing perfectly.
        """
        above = [ln for ln in lines if ln[0] < y - pitch * 0.5]
        for _y, txt in reversed(above[-3:]):
            n = clean_name(txt)
            if n and not T.TOTALS.match(n) and not T.PCT.match(n):
                return n
        return ''

    def emit(i, ks, layout, raw, closed):
        y, reg, vot = rows[i]
        snapped, how = T.snap(T.delead(raw), names)
        out.append({'name': snapped if how in T.NAMED_OK else '',
                    'raw': raw, 'how': how, 'registered': reg,
                    'voted': vot, 'precincts': len(ks), 'layout': layout,
                    'closed': closed,
                    'pct_registered': [rows[k][1] for k in ks],
                    'pct_voted': [rows[k][2] for k in ks]})

    # THE ARITHMETIC FINDS THE TOWNS AND THE LABELS FIND THE REST. A run that
    # closes is certain, but a town whose figures carry one bad digit does not
    # stop being a town -- and its TOTAL is printed on the page regardless of
    # whether its precincts add up to it. Framingham's neighbour on 2012 page 20
    # lost the leading 1 of `1,877` in the text layer, so 877 + 1,892 + 1,902
    # missed the printed 5,671 by a thousand; the total itself was read
    # perfectly and was being thrown away.
    #
    # So after the arithmetic, walk the rows it could not claim. A row labelled
    # TOTALS is a town total by the table's own say-so. A row whose label snaps
    # to a municipality is that town. Neither is marked as closed -- the check
    # and the reading stay separate, which is the whole point of having a check.
    out, closed, pending = [], 0, []
    for i, ks, layout in runs:
        y, reg, vot = rows[i]
        if layout != 'single':
            closed += 1
            pending = []
            raw = name_above(rows[ks[0]][0]) if layout == 'foot' else name_at(y)
            emit(i, ks, layout, raw, True)
            continue
        lab = name_at(y)
        if T.TOTALS.match(lab or ''):
            emit(i, pending, 'totals-line',
                 name_above(rows[pending[0]][0]) if pending else name_above(y),
                 False)
            pending = []
            continue
        snapped, how = T.snap(T.delead(lab), names)
        if how in T.NAMED_OK:
            emit(i, [], 'named-row', lab, False)
            pending = []
        else:
            pending.append(i)      # a precinct still waiting for its total
    return out, {'rows': len(rows), 'runs': len(runs), 'closed': closed,
                 'named': sum(1 for t in out if t['name'])}


def score(towns):
    """How well this reading read the page.

    A town that closes its own arithmetic AND carries a name that snaps is worth
    a whole point; one that does only one of the two is worth a third. Both
    signals are needed: a page read as one enormous town closes nothing, and a
    page whose labels came out as months names everything and closes nothing.
    """
    s = 0.0
    for t in towns:
        s += 1.0 if (t['closed'] and t['name']) else \
            (0.34 if (t['closed'] or t['name']) else 0.0)
    return s


def read_page(doc, i, names, year=None, force=None, debug=False):
    """Best reading of one page, text layer against OCR, scored.

    NEITHER SOURCE WINS EVERYWHERE and no rule decided it correctly. Forcing OCR
    where the text looked sparse made 2014 and 2016 worse -- it replaced a text
    reading that was closing its arithmetic with an OCR reading that was not.
    Run both where it is worth it and let the page's own arithmetic choose.
    """
    page = doc[i]
    sp = T.block_split(page) or page.rect.width
    top, bot = page.rect.height * T.TOP_FRAC, page.rect.height * T.BOT_FRAC
    # THE COLUMN SPLIT LANDS INSIDE THE RIGHT BLOCK'S NAMES. It is found from
    # the widest vertical gap in the page's own text, and that gap sits between
    # the left block's last figure column and the right block's dot leaders --
    # a little to the RIGHT of where the right block's names begin. Cutting
    # there beheads every one of them: `Huntington` came out `ngton`, `Ipswich`
    # as `+h`, `Longmeadow` as `neadow`. Sixteen towns on one block of 1986
    # page 20, read perfectly and emitted nameless.
    #
    # The margin is only safe in this direction. Widening the LEFT block the
    # same way would pull the right block's names onto its rows and join the
    # two -- `Hanson Hull` snaps to nothing. Figures that stray in are harmless
    # either way: the figure columns are taken as the two RIGHTMOST clusters, so
    # an intruding column from the block next door sorts to the left and is
    # discarded.
    gutter = page.rect.width * 0.06
    blocks = [pymupdf.Rect(0, top, sp + page.rect.width * 0.01, bot)]
    if sp < page.rect.width - 2:
        blocks.append(pymupdf.Rect(max(0, sp - gutter), top,
                                   page.rect.width, bot))

    figs, marks = len(T.NUM.findall(page.get_text())), 0
    words = len(page.get_text('words'))
    sources = [False, True]
    if force is True:
        sources = [True]
    elif force is False:
        sources = [False]
    elif words < 40:
        sources = [True]          # nothing in the text layer to score

    best, best_s, best_src = [], -1.0, None
    for use_ocr in sources:
        got = []
        for clip in blocks:
            try:
                towns, _info = read_block(page, clip, names, use_ocr, year)
            except Exception as e:                        # noqa: BLE001
                if debug:
                    print('   block failed (%s): %s'
                          % ('ocr' if use_ocr else 'text', e))
                continue
            got += towns
        s = score(got)
        if debug:
            print('   p%-4d %-5s -> %2d towns, %2d closed, %2d named, score %.1f'
                  % (i + 1, 'ocr' if use_ocr else 'text', len(got),
                     sum(1 for t in got if t['closed']),
                     sum(1 for t in got if t['name']), s))
        if s > best_s:
            best, best_s, best_src = got, s, 'ocr' if use_ocr else 'text'
        # A PAGE THAT IS ALREADY READ DOES NOT NEED A SECOND OPINION. OCR is
        # about a second per block and there are some two hundred and fifty
        # pages; running it against a text reading that has named every
        # municipality on the page and closed most of their arithmetic buys
        # nothing. The test is on the reading, not on the page -- `this text
        # layer looks thin` was the rule that made 2014 and 2016 worse.
        if not use_ocr and len(got) >= 16 \
                and sum(1 for t in got if t['name']) >= 0.9 * len(got) \
                and sum(1 for t in got if t['closed']) >= 0.5 * len(got):
            break
    return best, best_src


def read_volume(year, pages=None, debug=False, force=None):
    f = os.path.join(ROOT, 'pd43', 'pd43-%s.pdf' % year)
    doc = pymupdf.open(f)
    known = SECTIONS.get((year, 'town'))
    if known is not None:
        scope = known['pages']
        eyear = known['year']
    else:
        scope = section(doc, TOWN_HEAD, CITY_HEAD)
        eyear = year
    if pages:
        scope = [p - 1 for p in pages]
    if not scope:
        print('%s: no town table in this volume (%s)'
              % (year, (known or {}).get('note', 'not scoped')))
        return [], eyear, 0
    names = T.load_municipalities(ROOT)
    stated = stated_counts(doc).get('towns', 0)

    out, by_src = [], collections.Counter()
    for i in scope:
        towns, src = read_page(doc, i, names, year=int(eyear),
                               force=force, debug=debug)
        by_src[src] += 1
        for t in towns:
            t['page'] = i + 1
            t['source'] = src
        out += towns
    doc.close()
    if debug:
        print('   sources: %s' % dict(by_src))
    return out, eyear, stated


def merge(towns):
    """One row per municipality, with the column break repaired.

    A TOWN STRADDLING THE COLUMN BREAK HAS ITS TOTAL IN ONE BLOCK AND ITS
    PRECINCTS IN THE NEXT, and that is the table's doing, not a misreading. Its
    two halves must be added rather than scored as a contradiction.
    """
    by = collections.OrderedDict()
    for t in towns:
        if not t['name']:
            continue
        k = t['name']
        if k not in by:
            by[k] = dict(t)
        else:
            old = by[k]
            # Keep whichever half actually closed; failing that, the larger
            # registration, which is the town total rather than a precinct.
            if t['closed'] and not old['closed']:
                by[k] = dict(t)
            elif (t['registered'] or 0) > (old['registered'] or 0) \
                    and not old['closed']:
                by[k] = dict(t)
    return list(by.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('years', nargs='+')
    ap.add_argument('--out', default='')
    ap.add_argument('--pages', default='')
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--force', choices=['ocr', 'text'], default=None)
    a = ap.parse_args()
    T._find_tesseract()
    force = {'ocr': True, 'text': False}.get(a.force)
    pages = [int(x) for x in a.pages.split(',') if x.strip()]

    grand = []
    for y in a.years:
        towns, eyear, stated = read_volume(y, pages, a.debug, force)
        rows = merge(towns)
        closed = sum(1 for t in rows if t['closed'])
        den = stated or len(rows) or 1
        print('%-6s (election %s): %3d municipalities of %s stated = %5.1f%%'
              '   %3d close their own arithmetic'
              % (y, eyear, len(rows), stated or '?', 100.0 * len(rows) / den,
                 closed))
        for t in rows:
            t['year'] = eyear
            t['volume'] = y
        grand += rows

    if a.out:
        with io.open(a.out, 'w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['year', 'volume', 'page', 'municipality', 'registered',
                        'voted', 'precincts', 'arithmetic_closes', 'source',
                        'name_matched_by', 'name_as_read'])
            for t in grand:
                w.writerow([t['year'], t['volume'], t['page'], t['name'],
                            t['registered'], t['voted'], t['precincts'],
                            int(t['closed']), t['source'], t['how'],
                            t['raw']])
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
