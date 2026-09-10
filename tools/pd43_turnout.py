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

# Tesseract is not on PATH for the python process on this machine.
_TESS = os.path.join(r'C:\Program Files', 'Tesseract-OCR', 'tesseract.exe')
if os.path.exists(_TESS):
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = _TESS
    except ImportError:
        pass

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
OCR_ZOOM = 3.0             # render scale for pages with no text
LABEL_FRAC = 0.18          # label column width, as a share of page width
TOP_FRAC = 0.11            # first row, as a share of page height
BOT_FRAC = 0.97            # last row


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def label_w(page):
    return page.rect.width * LABEL_FRAC


def load_municipalities(root):
    """The 351 names, for snapping an OCR reading to a real town.

    OCR gets these names very nearly right and almost never exactly right:
    `Ambherst`, `Andovet`, `Bernardson`, `Raynhan`, `Shutesbuty`, `Warehan`,
    `West Boyloston`. Left alone, 154 of 174 towns in an OCR'd volume fail to
    join to anything. The list of Massachusetts municipalities is closed and
    known, so the reading is snapped to it and anything that will not snap is
    reported rather than guessed at.
    """
    path = os.path.join(root, 'pages', 'inventory', 'municipalities.csv')
    names = []
    try:
        with io.open(path, encoding='utf-8', newline='') as fh:
            for row in csv.DictReader(fh):
                n = (row.get('Municipality') or '').strip()
                if n:
                    names.append(n)
    except (OSError, ValueError, csv.Error):
        pass
    return names


# The date follows the town on the same printed line, and OCR keeps some of it.
TRAIL = re.compile(
    r'\s*[-\s.]*(%s|ODD|EVEN)\w*\.?\s*$' % '|'.join(
        m[:3] for m in ('January February March April May June July August '
                        'September October November December').split()), re.I)
# Dot leaders read as a run of letters when the scan is soft: `csceeeeeeeee`.
NOISE = re.compile(r'\b[a-z]*(?:eee|sss|ccc|ooo)[a-z]*\b|\s[-.,]+\s*$', re.I)


def snap(name, names):
    """An OCR town name, matched to the closed list. -> (name, how)"""
    import difflib
    raw = NOISE.sub(' ', TRAIL.sub('', name or ''))
    raw = re.sub(r'\s+', ' ', raw).strip(' .-')
    if not raw:
        return None, 'empty'
    for n in names:
        if n.lower() == raw.lower():
            return n, 'exact'
    hit = difflib.get_close_matches(raw, names, n=1, cutoff=0.82)
    if hit:
        return hit[0], 'snapped'
    # A tail of the name survives more often than the head, because the head is
    # what the dot leaders run into: `By-The-Sea` is Manchester-by-the-Sea.
    low = raw.lower()
    tail = [n for n in names if n.lower().endswith(low) or low.endswith(n.lower())]
    if len(tail) == 1:
        return tail[0], 'by tail'
    return raw, 'unmatched'


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



def split_row(tokens):
    """A row of text -> (label, figures, joined).

    The label is what stands before the first figure; the figures are every
    number on the row, in printed order. Both row sources agree on this shape,
    which is the only thing the parser below needs to know about either.
    """
    toks = [t for t in tokens if (t or '').strip()]
    joined = ' '.join(toks).strip()
    figs, lead, seen = [], [], False
    for t in toks:
        v = num(t)
        if v is None:
            if not seen:
                lead.append(t)
        else:
            figs.append(v)
            seen = True
    return delead(' '.join(lead)), figs, joined


def rows_from_cells(page, lo, hi):
    """Rows from the PDF's own text, via the table detector."""
    clip = pymupdf.Rect(lo, page.rect.height * TOP_FRAC,
                        hi, page.rect.height * BOT_FRAC)
    try:
        found = page.find_tables(strategy='text', clip=clip)
    except Exception:
        return [], [], 0.0
    if not found.tables:
        return [], [], 0.0
    table = max(found.tables, key=lambda x: len(x.rows))
    cells = table.extract()
    bands = [r.bbox for r in table.rows]
    labels = label_lines(page, lo, lo + label_w(page))
    off = skew_offset(labels, bands, cells)
    # The table detector clips the leftmost column, so a row's own first cell is
    # not always the whole label; keep the band so the label column can supply it.
    out = []
    for i, row in enumerate(cells):
        label, figs, joined = split_row(row)
        col0 = delead(row[0] or '')
        band = bands[i] if i < len(bands) else (0, 0, 0, 0)
        out.append({'label': col0 or label, 'figs': figs, 'joined': joined,
                    'band': band})
    return out, labels, off


def rows_from_ocr(page, lo, hi):
    """Rows from Tesseract, for a page with no usable text layer.

    The block is cropped BEFORE being read, so a line cannot run across the
    gutter and join two towns into one row -- which is what happens when the
    whole page is given to Tesseract at once.
    """
    import pytesseract
    from PIL import Image
    clip = pymupdf.Rect(lo, page.rect.height * TOP_FRAC,
                        hi, page.rect.height * BOT_FRAC)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(OCR_ZOOM, OCR_ZOOM), clip=clip)
    img = Image.open(io.BytesIO(pix.tobytes('png')))
    # PSM 6 -- "a single uniform block of text" -- because the block has already
    # been cropped out and is exactly that. Tesseract's automatic segmentation
    # (PSM 3, the default) decides the ruled label column is furniture and
    # discards nearly all of it: on the 2008 crop it returns ONE token from that
    # column against 103 under PSM 6, so every town lost its name and the volume
    # returned 75 municipalities instead of 253.
    d = pytesseract.image_to_data(img, config='--psm 6',
                                  output_type=pytesseract.Output.DICT)

    # THE LABEL COLUMN IS READ SEPARATELY, exactly as it is on the text path.
    # Tesseract groups words into lines by proximity, and the gap between a town
    # name and its date is wide enough that it starts a new line -- so a row
    # assembled from Tesseract's own grouping arrives with its figures intact and
    # its name missing. Forcing OCR on the 2008 volume that way returned 36
    # municipalities where the text layer returns 253.
    # In CROP pixels, not page-relative ones: the image is one block, rendered at
    # OCR_ZOOM, so a point is OCR_ZOOM pixels and the block's own left edge is
    # zero. Scaling by the whole page width put the cut at 145px instead of 286
    # and left every label on the wrong side of it.
    cut = label_w(page) * OCR_ZOOM
    lines, labels = {}, {}
    for i, text in enumerate(d['text']):
        text = (text or '').strip()
        if not text:
            continue
        x, y, h = d['left'][i], d['top'][i], d['height'][i]
        key = (d['block_num'][i], d['par_num'][i], d['line_num'][i])
        if x < cut:
            labels.setdefault(key, []).append((x, y + h / 2.0, text))
        else:
            lines.setdefault(key, []).append((x, y + h / 2.0, text))

    lab = []
    for key in labels:
        ws = sorted(labels[key], key=lambda w: w[0])
        lab.append((sum(w[1] for w in ws) / len(ws),
                    delead(' '.join(w[2] for w in ws))))
    lab.sort()

    out = []
    for key in sorted(lines, key=lambda k: min(w[1] for w in lines[k])):
        ws = sorted(lines[key], key=lambda w: w[0])
        mid = sum(w[1] for w in ws) / len(ws)
        _, figs, joined = split_row([w[2] for w in ws])
        # The label whose centre is nearest this row's, within a row height.
        near = [(abs(y - mid), t) for y, t in lab if abs(y - mid) < 14 * OCR_ZOOM]
        label = min(near)[1] if near else ''
        out.append({'label': label, 'figs': figs,
                    'joined': (label + ' ' + joined).strip(),
                    'band': (0, mid, 0, mid)})
    return out, [], 0.0


def parse_block(page, lo, hi, year, force_ocr=False, names=None):
    """One column block -> a list of municipalities."""
    rows, labels, off = ([], [], 0.0) if force_ocr else \
        rows_from_cells(page, lo, hi)
    used_ocr = False
    # A page with almost no text is a scan nobody ran OCR over. It is not a hard
    # page to parse; there is simply nothing on it to parse, and half the 2000
    # volume is like that.
    if force_ocr or len(rows) < 6:
        try:
            rows, labels, off = rows_from_ocr(page, lo, hi)
            used_ocr = True
        except Exception as exc:
            print('   [ocr failed] %s' % exc)
            if not rows:
                return [], False

    towns, cur = [], None

    def close():
        if cur and (cur['precincts'] or cur['reg'] is not None
                    or cur['no_election']):
            towns.append(cur)

    for row in rows:
        joined, figs, col0 = row['joined'], row['figs'], row['label']
        if not joined:
            continue
        if re.search(r'Registered|People\s+Who|Date\s+of|^Town\b|Election\s*$',
                     joined, re.I) and not DATE.search(joined):
            continue

        m = DATE.search(joined)
        # A ROW WHOSE LABEL IS A MASSACHUSETTS TOWN STARTS THAT TOWN, date or no
        # date. The heading was recognised only by its date, so when OCR lost the
        # date -- which it does, the month sitting right where the dot leaders
        # end -- the town never opened and its precincts were appended to the
        # town above. Acton came back with sixteen precincts and Adams's total.
        # A precinct label and a TOTALS label never snap to a town, so this
        # cannot swallow an ordinary row.
        heads = False
        if names and col0 and not PCT.match(col0) and not TOTALS.search(col0):
            cand, how_c = snap(col0, names)
            heads = how_c in ('exact', 'snapped')

        if m or no_election(joined) or heads:
            close()
            # Where the row's own label is clipped, the label column supplies the
            # name, matched through the measured skew. The OCR path has no such
            # column and does not need one: it never clips.
            named = town_at(labels, off, row['band'][1], row['band'][3]) \
                if labels else None
            name = col0 if TOWN.match(col0 or '') and not PCT.match(col0 or '') \
                else None
            if named and (not name or named.startswith(name[:3])
                          or name.endswith(named[-3:])):
                name = named
            how = ''
            if names:
                snapped, how = snap(name or col0 or '', names)
                if how in ('exact', 'snapped', 'by tail'):
                    name = snapped
                elif heads:
                    name = cand
            cur = new_town(name or 'UNKNOWN')
            cur['name_how'] = how
            if no_election(joined):
                cur['no_election'] = True
                continue
            if not m:
                continue
            mon = next((x for x in MONTHS
                        if x.lower().startswith(m.group(1).lower()[:3])), None)
            if mon:
                try:
                    cur['date'] = '%d-%02d-%02d' % (
                        year, MONTHS.index(mon) + 1, int(m.group(2)))
                except ValueError:
                    pass
            if len(figs) >= 2 and not re.search(r'\d{4}', joined[m.start():]):
                cur['precincts'].append({'precinct': None, 'reg': figs[-2],
                                         'voted': figs[-1]})
            continue

        if cur is None:
            continue

        if TOTALS.search(col0 or '') or (not col0 and TOTALS.search(joined)):
            if len(figs) >= 2:
                cur['reg'], cur['voted'] = figs[-2], figs[-1]
            elif figs:
                cur['reg'] = figs[-1]
            continue

        if figs:
            mp = PCT.match(col0) if col0 else None
            pnum = next((g for g in (mp.groups() if mp else ()) if g), None)
            body = figs[-2:] if len(figs) >= 2 else figs
            cur['precincts'].append(
                {'precinct': pnum, 'reg': body[0],
                 'voted': body[1] if len(body) > 1 else None})
    close()
    return towns, used_ocr


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
    ap.add_argument('--ocr', action='store_true',
                    help='OCR every table page, not only the ones with no text')
    a = ap.parse_args()

    doc = pymupdf.open(a.pdf)
    pages = table_pages(doc)
    if not pages:
        print('no town-election table in %s' % os.path.basename(a.pdf))
        return 1
    print('table pages: %d-%d' % (pages[0] + 1, pages[-1] + 1))

    names = load_municipalities(ROOT)
    print('%d municipalities in the reference list' % len(names))
    rows, ocr_pages = [], set()
    for i in pages:
        page = doc[i]
        split = block_split(page)
        for lo, hi in ((0, split), (split, page.rect.width)):
            got, ocr = parse_block(page, lo, hi, a.year,
                                   force_ocr=a.ocr, names=names)
            for t in got:
                t['by_ocr'] = ocr
            rows += got
            if ocr:
                ocr_pages.add(i)

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
        # EVERYTHING THE PAGE PRINTS, not a summary of it. One row per precinct
        # and one for the town, so the precinct detail survives -- it is the only
        # sub-municipal registration figure this project has any source for, and
        # discarding it to print a total would throw away the more granular half
        # of what was already read. `level` says which kind of row it is; the
        # status is the town's, and repeats on its precincts so either grain can
        # be filtered on its own.
        w.writerow(['municipality', 'year', 'date', 'level', 'precinct',
                    'registered', 'voted', 'status', 'note', 'read_by'])
        n_pct = 0
        for t in sorted(merged.values(), key=lambda x: x['municipality']):
            recover_total(t)
            st, note = check(t)
            if t.get('recovered') and st == 'checked':
                note += ('; the TOTALS label was unreadable and was '
                         'identified by the sum')
            counts[st] = counts.get(st, 0) + 1
            if a.verbose and st in ('mismatch', 'no_total'):
                print('   ? %-24s %s' % (t['municipality'], note))
            how = 'ocr' if t.get('by_ocr') else 'text'
            w.writerow([t['municipality'], a.year, t['date'] or '', 'total', '',
                        t['reg'] if t['reg'] is not None else '',
                        t['voted'] if t['voted'] is not None else '',
                        st, note, how])
            for i, p in enumerate(t['precincts'], 1):
                n_pct += 1
                w.writerow([t['municipality'], a.year, t['date'] or '',
                            'precinct', p.get('precinct') or i,
                            p['reg'] if p['reg'] is not None else '',
                            p['voted'] if p['voted'] is not None else '',
                            st, '', how])

    dated = sum(1 for t in merged.values() if t['date'])
    good = counts.get('checked', 0) + counts.get('no_election', 0)
    print('%d municipalities, %d fully checked (%.0f%%)'
          % (len(merged), good, 100.0 * good / max(1, len(merged))))
    for k in sorted(counts, key=lambda x: -counts[x]):
        print('   %-12s %4d' % (k, counts[k]))
    if ocr_pages:
        print('   %d of %d pages had no text layer and were read by OCR'
              % (len(ocr_pages), len(pages)))
    print('   %d precinct rows, %d town-years with an election date'
          % (n_pct, dated))
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
