"""Read the town-election registration table out of a Public Document 43 volume.

WHAT THIS IS FOR. The pre-2021 half of the corpus has no registered-voter figure,
so no turnout can be computed for it and the map has to withdraw the measure for
those years. PD43 -- the Secretary of the Commonwealth's election statistics
volume, published since the nineteenth century -- prints exactly the missing
number, by municipality, by precinct, with the date of the election and the
number of people who voted beside it:

    Abington    April 26, 2008   Pct. 1   2,490    337
                                      2   2,076    337
                                      3   2,329    351
                                      4   2,921    413
                                 TOTALS   9,816  1,438

That is four things this project wants and one it did not know it could have: a
denominator, an independently published ballots-cast figure to check our own
against, the election date to check our parse against, precinct detail, and --
from the towns printed `ODD YEARS ONLY` -- an authoritative statement that a
municipality held NO election that year, which the map currently cannot
distinguish from never having looked.

WHY IT CAN BE TRUSTED WITHOUT A HUMAN READING IT. The precinct rows sum to the
TOTALS row. Every town in the table is self-checking, so a volume read by OCR can
be verified arithmetically town by town, and only the failures need a person.
That is what makes going back decades tractable rather than a transcription
project. The volumes are scans and the text layer is visibly damaged in places --
`1 \\) IAIjO` where a total should be, `totals!!!;!!;;!;;!;;!!` for a row label --
but damage that changes a number breaks the sum and is caught.

HOW THE PAGE IS READ. It is set in two column blocks side by side, and each block
is skewed slightly and independently, so words that belong to one printed row
drift apart in y as x increases. Clustering words into rows by y therefore does
not work, and neither does reading the text stream, which interleaves the blocks.

PyMuPDF's `find_tables(strategy="text")` aligns the numeric columns correctly, so
it does that job. What it will not do is include the leftmost label column: it
computes its own bounding box from the content it finds and starts it at the
precinct numbers, cutting `Abington` to `ton`. So the labels are taken from the
words layer instead, matched to the row bands the table detector found. Each tool
does the part it is good at.

    python tools/pd43_turnout.py <volume.pdf> --year 2008 --out pd43_2008.csv
"""
import argparse
import csv
import io
import os
import re
import sys

import pymupdf

pymupdf.TOOLS.mupdf_display_errors(False)

HEAD = re.compile(r'REGISTERED\s+VOTERS\s+AND\s+PEOPLE\s+WHO\s+VOTED', re.I)
# `Pct.` is printed `Pet.` about as often as not: the scan reads c as e.
# `Pct.` is printed `Pet.` about as often as not: the scan reads c as e. And a
# precinct is not always a number -- Belchertown runs Pct. A, B, C -- so a bare
# letter counts too, which is why the town test has to run first.
PCT = re.compile(r'^P[ce]t\.?\s*([0-9]+|[A-Z])|^([0-9]{1,2})$|^([A-Z])$'
                 r'|^Ward\s*([0-9]+)', re.I)
# DOT LEADERS BELONG TO THE TYPESETTING, NOT THE NAME. The older volumes rule
# every label to its column -- `Bedford ..............`, `Pct. 1.............`,
# `TOTALS ............` -- and with the dots left on, no town name matches, no
# precinct matches, and a volume yields a third of its towns.
LEADER = re.compile(r'[.…]{2,}\s*$|\s*[.…]{2,}')
# A town continued at the top of the next column repeats its name with a note.
CONT = re.compile(r'\s*\((cont|continued)\.?\)\s*$', re.I)


def delead(text):
    return CONT.sub('', LEADER.sub(' ', text or '')).strip(' .')
TOTALS = re.compile(r'TOTALS?|^[LS]{2}$|totals?[!;:.\s]*$', re.I)
# Matched against the row with its spaces removed. The table detector splits a
# cell mid-word, so `ODD YEARS ONLY` reaches us as `ODD YEA` + `RS ONLY`, and any
# pattern with a space in it misses every one of them.
NO_ELECTION = re.compile(r'(ODD|EVEN)YEARS?ONLY|NO(TOWN)?ELECTION', re.I)
def no_election(text):
    return NO_ELECTION.search(re.sub(r'[\s.]+', '', text or ''))
MONTHS = ('January February March April May June July August September '
          'October November December').split()
DATE = re.compile(r'\b(%s)\w*\.?\s*(\d{1,2})\s*,?\s*(\d{2,4})?' % '|'.join(
    m[:3] for m in MONTHS), re.I)
NUM = re.compile(r'^\d[\d,]{0,8}$')
TOWN = re.compile(r"^[A-Z][A-Za-z.'-]{2,}(?:[ -][A-Za-z.'-]+){0,4}$")

# THE VOLUMES ARE NOT ALL THE SAME SIZE. The 2008 scan is 529 points wide, the
# 2000 scan 390 -- the series was rescanned at different times and at different
# scales. Every offset here is therefore a FRACTION of the page, not a number of
# points: with the 2008 figures hardcoded, the 2000 clip fell outside the table
# entirely and the volume yielded no tables at all.
LABEL_FRAC = 0.18          # label column width, as a share of page width
TOP_FRAC = 0.11            # first row, as a share of page height
BOT_FRAC = 0.97            # last row


def label_w(page):
    return page.rect.width * LABEL_FRAC


def num(s):
    s = (s or '').replace(',', '').replace(' ', '').strip()
    return int(s) if s.isdigit() else None


def block_split(page):
    """The x of the gutter between the two column blocks.

    Found as the widest vertical gap in the middle third rather than fixed at
    half the page: the volumes are scans and the gutter wanders, by a few points
    within a volume and a good deal more across decades.
    """
    W = page.rect.width
    xs = sorted(w[0] for w in page.get_text('words'))
    if len(xs) < 2:
        return W / 2
    # SEARCH A NARROW BAND ROUND THE CENTRE, NOT THE MIDDLE THIRD. Inside a
    # block the gap between the precinct numbers and the date column is wider
    # than the gutter between the blocks, so "the widest gap in the middle
    # third" finds a gap inside the right-hand block and splits the page there
    # -- which puts the right block's town column into the left block, and every
    # figure after it against the wrong town.
    gaps = [(xs[i + 1] - xs[i], (xs[i] + xs[i + 1]) / 2)
            for i in range(len(xs) - 1)
            if W * 0.44 < (xs[i] + xs[i + 1]) / 2 < W * 0.56]
    if not gaps:
        return W / 2
    g, at = max(gaps)
    return at if g > 8 else W / 2


def label_lines(page, lo, hi):
    """(y, text) for each printed line of the label column, in order."""
    words = [w for w in page.get_text('words') if lo <= w[0] < hi]
    lines = {}
    for w in words:
        lines.setdefault(round(w[1] / 3.0), []).append(w)
    out = []
    for k in sorted(lines):
        ws = sorted(lines[k], key=lambda w: w[0])
        text = delead(' '.join(w[4] for w in ws))
        if text:
            out.append((ws[0][1], text))
    return out


def skew_offset(labels, bands, cells):
    """How far the label column sits above or below the figures, in points.

    THE SCAN IS SKEWED AND THE SKEW IS MEASURABLE. The label column is at the
    left edge of a block and the figures are 150 points to its right; over that
    distance a printed row drifts by more than a row height, so a label matched
    to the band it geometrically falls in is often the neighbour's.

    The drift is near enough a constant shift within one block, and the table
    hands us a free way to measure it: the figure rows carry their own precinct
    numbers in the first cell, and the same numbers are printed in the label
    column. Try every offset, keep the one where the two agree most often.

    Self-calibrating per page and per block, which matters because the two blocks
    are skewed independently and the volumes span decades of scanning practice.
    """
    anchors = [(bands[i][1], bands[i][3], (cells[i][0] or '').strip())
               for i in range(min(len(bands), len(cells)))
               if (cells[i][0] or '').strip()]
    anchors = [a for a in anchors if PCT.match(a[2]) or TOTALS.search(a[2])]
    if not anchors:
        return 0.0
    best, best_n = 0.0, -1
    for step in range(-30, 31):
        off = step * 1.0
        n = 0
        for y, text in labels:
            yy = y + off
            for y0, y1, want in anchors:
                if y0 - 2 <= yy <= y1 + 2:
                    a = re.sub(r'[^A-Za-z0-9]', '', text).lower()
                    b = re.sub(r'[^A-Za-z0-9]', '', want).lower()
                    if a and b and (a.startswith(b) or b.startswith(a)):
                        n += 1
                    break
        if n > best_n:
            best, best_n = off, n
    return best


def town_at(labels, off, y0, y1):
    """The town name printed against this row band, if any."""
    for y, text in labels:
        if y0 - 3 <= y + off <= y1 + 3:
            clean = re.sub(r'\s*P[ce]t\.?\s*[\dA-Z]*\s*$', '', delead(text))
            clean = re.sub(r'[^A-Za-z .\'-]', '', clean).strip(' .')
            if TOWN.match(clean) and not PCT.match(clean) \
                    and not TOTALS.search(clean):
                return clean
    return None



def parse_block(page, lo, hi, year):
    """One column block -> a list of municipalities."""
    clip = pymupdf.Rect(lo, page.rect.height * TOP_FRAC,
                        hi, page.rect.height * BOT_FRAC)
    try:
        found = page.find_tables(strategy='text', clip=clip)
    except Exception:
        return []
    if not found.tables:
        return []
    table = max(found.tables, key=lambda x: len(x.rows))
    cells = table.extract()
    bands = [r.bbox for r in table.rows]
    labels = label_lines(page, lo, lo + label_w(page))
    off = skew_offset(labels, bands, cells)

    towns, cur = [], None

    def close():
        if cur and (cur['precincts'] or cur['reg'] is not None
                    or cur['no_election']):
            towns.append(cur)

    for ri, row in enumerate(cells):
        band = bands[ri] if ri < len(bands) else (0, 0, 0, 0)
        joined = ' '.join(c for c in row if c).strip()
        if not joined:
            continue
        if re.search(r'Registered|People\s+Who|Date\s+of|^Town\b|Election\s*$',
                     joined, re.I) and not DATE.search(joined):
            continue

        col0 = delead(row[0] or '')
        figs = [num(c) for c in row]
        figs = [f for f in figs if f is not None]

        # A town heading is the row carrying the election date. The second block
        # prints the town's full name in its own first column; the first block
        # has it clipped, so the counted sequence supplies it.
        m = DATE.search(joined)
        if m or no_election(joined):
            close()
            # The second block prints the town's full name in its own first
            # cell; the first block has it clipped by the table detector, so the
            # label column supplies it, matched through the measured skew.
            named = town_at(labels, off, band[1], band[3])
            name = col0 if TOWN.match(col0) and not PCT.match(col0) else None
            if named and (not name or named.startswith(name[:3])
                          or name.endswith(named[-3:])):
                name = named
            cur = new_town(name or 'UNKNOWN')
            if no_election(joined):
                cur['no_election'] = True
                continue
            mon = next((x for x in MONTHS
                        if x.lower().startswith(m.group(1).lower()[:3])), None)
            if mon:
                try:
                    cur['date'] = '%d-%02d-%02d' % (
                        year, MONTHS.index(mon) + 1, int(m.group(2)))
                except ValueError:
                    pass
            # The heading row sometimes carries the first precinct's figures.
            if len(figs) >= 2 and not re.search(r'\d{4}', joined[m.start():]):
                cur['precincts'].append({'precinct': None, 'reg': figs[-2],
                                         'voted': figs[-1]})
            continue

        if cur is None:
            continue

        if TOTALS.search(col0) or (not col0 and TOTALS.search(joined)):
            if len(figs) >= 2:
                cur['reg'], cur['voted'] = figs[-2], figs[-1]
            elif figs:
                cur['reg'] = figs[-1]
            continue

        if figs:
            mp = PCT.match(col0) if col0 else None
            pnum = (mp.group(1) or mp.group(2) or mp.group(3)) if mp else None
            body = figs[-2:] if len(figs) >= 2 else figs
            cur['precincts'].append(
                {'precinct': pnum, 'reg': body[0],
                 'voted': body[1] if len(body) > 1 else None})
    close()
    return towns


def new_town(name):
    return {'municipality': re.sub(r'\s+', ' ', name).strip(' .'),
            'date': None, 'reg': None, 'voted': None,
            'precincts': [], 'no_election': False}


def recover_total(t):
    """A TOTALS row whose label the scan destroyed, recovered by arithmetic.

    Ashland's totals line reads like line noise, and Ayer's reads
    `totals!!!;!!;;!;;!;;!!;;;;;`.
    Nothing matches those, so the row is taken for another precinct and the town
    is left with no total at all -- fifty of them in the 2008 volume.

    But a totals row is recognisable without its label: it is the row equal to
    the sum of the rows above it. That is only claimed when it is exactly true,
    so a damaged FIGURE still fails and is still reported.
    """
    if t['reg'] is not None or len(t['precincts']) < 2:
        return False
    body, last = t['precincts'][:-1], t['precincts'][-1]
    sreg = sum(p['reg'] for p in body if p['reg'] is not None)
    if last['reg'] is None or last['reg'] != sreg:
        return False
    svote = sum(p['voted'] for p in body if p['voted'] is not None)
    t['reg'] = last['reg']
    t['voted'] = last['voted'] if last['voted'] == svote else None
    t['precincts'] = body
    t['recovered'] = True
    return True


def check(t):
    """Does the town's own arithmetic close? -> (status, note)

    The whole reason the series is usable at scale: nobody has to read the page,
    because the page checks itself.
    """
    if t['no_election']:
        return 'no_election', 'the volume states no election was held this year'
    p = t['precincts']
    if not p:
        return ('single' if t['reg'] is not None else 'empty',
                'a single undivided town, or no precinct detail printed')
    sreg = sum(x['reg'] for x in p if x['reg'] is not None)
    svote = sum(x['voted'] for x in p if x['voted'] is not None)
    okr = t['reg'] is not None and sreg == t['reg']
    okv = t['voted'] is not None and svote == t['voted']
    if okr and okv:
        return 'checked', 'precincts sum to both printed totals'
    if okr:
        return 'reg_only', 'registered voters sum; people who voted does not'
    if okv:
        return 'voted_only', 'people who voted sums; registered voters does not'
    if t['reg'] is None:
        return 'no_total', 'no TOTALS row was read'
    return 'mismatch', ('precincts sum to %s registered, the printed total says %s'
                        % (sreg, t['reg']))


def table_pages(doc):
    hits = [i for i, p in enumerate(doc) if HEAD.search(p.get_text())]
    if not hits:
        return []
    # The heading also appears in the contents, and the same words turn up in
    # later section titles. The TABLE is the longest unbroken run of pages
    # carrying it; a contents entry is a run of one.
    runs, run = [], [hits[0]]
    for i in hits[1:]:
        if i == run[-1] + 1:
            run.append(i)
        else:
            runs.append(run)
            run = [i]
    runs.append(run)
    return max(runs, key=len)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    doc = pymupdf.open(a.pdf)
    pages = table_pages(doc)
    if not pages:
        print('no town-election table in %s' % os.path.basename(a.pdf))
        return 1
    print('table pages: %d-%d' % (pages[0] + 1, pages[-1] + 1))

    rows = []
    for i in pages:
        page = doc[i]
        split = block_split(page)
        rows += parse_block(page, 0, split, a.year)
        rows += parse_block(page, split, page.rect.width, a.year)

    # One town can straddle a column or page break; merge fragments by name.
    merged = {}
    for t in rows:
        k = t['municipality'].lower()
        if k in merged:
            m = merged[k]
            m['precincts'] += t['precincts']
            for f in ('date', 'reg', 'voted'):
                if m[f] is None:
                    m[f] = t[f]
            m['no_election'] = m['no_election'] or t['no_election']
        else:
            merged[k] = t

    counts = {}
    with io.open(a.out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['municipality', 'year', 'date', 'registered', 'voted',
                    'precincts', 'status', 'note'])
        for t in sorted(merged.values(), key=lambda x: x['municipality']):
            recover_total(t)
            st, note = check(t)
            if t.get('recovered') and st == 'checked':
                note += '; the TOTALS label was unreadable and was '                         'identified by the sum'
            counts[st] = counts.get(st, 0) + 1
            if a.verbose and st in ('mismatch', 'no_total'):
                print('   ? %-24s %s' % (t['municipality'], note))
            w.writerow([t['municipality'], a.year, t['date'] or '',
                        t['reg'] if t['reg'] is not None else '',
                        t['voted'] if t['voted'] is not None else '',
                        len(t['precincts']), st, note])

    good = counts.get('checked', 0) + counts.get('no_election', 0)
    print('%d municipalities, %d fully checked (%.0f%%)'
          % (len(merged), good, 100.0 * good / max(1, len(merged))))
    for k in sorted(counts, key=lambda x: -counts[x]):
        print('   %-12s %4d' % (k, counts[k]))
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
