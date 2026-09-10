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

# `PEOPLE WHO VOTED` on the town table, `PERSONS WHO VOTED` on the city one.
# TWO WORDINGS, AND THE OLDER ONE IS NOT IN CAPITALS. From 1981 on the table is
# headed `REGISTERED VOTERS AND PEOPLE WHO VOTED` (`PERSONS` on the city table).
# The 1970s volumes invert it -- `Number of persons registered and people who
# voted at Elections` -- and set it in title case, so both the wording test and
# the capitals test missed every one of them.
# A THIRD SHAPE: THE HEADING IS THE COLUMN HEADERS, NOT A SENTENCE. The 1973-79
# volumes title the table `City Elections in 1973` and then rule the columns
# `Cities, Wards and Voting Precincts | Date of Election | Registered Voters |
# Persons who voted`. There is no phrase `registered voters and persons who
# voted` anywhere on the page, so both earlier patterns miss it entirely.
HEAD = re.compile(
    r'(?:REGISTERED\s+VOTERS\s+AND\s+PE(?:OPLE|RSONS)'
    r'|PERSONS?\s+REGISTERED\s+AND\s+PE(?:OPLE|RSONS))\s+WHO\s+VOTED'
    r'|(?:CITY|TOWN)\s+ELECTIONS?\s+IN\s+(?:19|20)\d{2}'
    r'|REGISTERED\s+VOTERS[\s\S]{0,80}?PERSONS?\s+WHO\s+VOTED', re.I)
HEAD_CAPS = HEAD
# EVERY TABLE IN THE VOLUME CARRIES THAT HEADING, including the state election
# and the primaries, which are not municipal and must not be read as if they
# were. What separates them is the line under it naming the election.
KIND_STATE = re.compile(r'STATE\s+ELECTION|PRIMAR|PRESIDENTIAL|SPECIAL\s+STATE',
                        re.I)
KIND_CITY = re.compile(r'CIT(?:Y|IES)', re.I)
KIND_TOWN = re.compile(r'TOWN', re.I)
CONTENTS = re.compile(r'TABLE\s+OF\s+CONTENTS', re.I)


def stated_counts(doc):
    """What the volume says it contains. -> {'towns': n, 'cities': n}

    THE VOLUME IS THE AUTHORITY ON ITS OWN YEAR. The number of cities changed
    through the period as towns adopted city forms of government, so 351 split
    into 312 towns and 39 cities in 2008 and differently in 1996. Each volume
    prints its own split in the summary at the front -- `312 towns, 1,118
    precincts`, `39 cities divided into 1,050 precincts` -- and that is the true
    denominator for how much of that year we have.

    Without it, coverage is measured against a guess: reading 284 of 311 looks
    like a shortfall of 27 and reading 284 of 284 does not, and only the volume
    can say which it is.
    """
    out = {}
    for p in doc[:30]:
        t = ' '.join(p.get_text().split())
        # `129 towns, one precinct each` is specific and unambiguous. The bare
        # `312 towns` is not -- it matched three different sentences in three
        # different volumes -- so only the specific one is trusted.
        m = re.search(r'(\d{1,3})\s+towns?,?\s+one\s+precinct\s+each', t, re.I)
        if m:
            out['single'] = int(m.group(1))
        alls = [int(x) for x in re.findall(r'(\d{2,3})\s+towns\b', t, re.I)]
        if alls:
            out['towns'] = max(alls)
        if out:
            break
    return out


def named_in(doc, pages, names):
    """Which municipalities are named anywhere in the table. -> set

    THE DENOMINATOR IS THE NAMES, NOT A COUNT. The volume does print its own
    split in the summary, and the split really does move as towns adopt city
    government -- but that sentence is not reliably machine-readable: the same
    pattern returns 312 for 1982, 306 for 1990 and 311 for 1996, which is not a
    trend, it is three different sentences being matched.

    Municipality NAMES do not change. The list of 351 is fixed and known, so the
    honest measure of how much of a volume was read is how many of those names
    appear anywhere in its table, against how many came out of it. That is a
    measurement rather than an assumption, and it is made per volume.
    """
    text = ' '.join(doc[i].get_text() for i in pages)
    return {n for n in names
            if re.search(r'\b' + re.escape(n) + r'\b', text, re.I)}


def page_kind(text):
    """'town', 'city' or None for a page carrying the heading.

    A combined `STATE, CITY AND TOWN ELECTIONS` table -- the 1970 and 1972 shape
    -- holds municipal rows and is kept. A page that names only a state contest
    is skipped: it is a different election with the same column headings, and
    reading it would file the state's turnout under the town's name.
    """
    if CONTENTS.search(text):
        return None
    town, city = KIND_TOWN.search(text), KIND_CITY.search(text)
    if KIND_STATE.search(text) and not (town or city):
        return None
    if city and not town:
        return 'city'
    if town:
        return 'town'
    return None
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
# A CLIPPED `TOTALS` IS STILL A TOTALS ROW. The table detector cuts the label
# column, and in the right-hand block it cuts from the LEFT, so the word arrives
# as its own tail: `ALS`, and the town names beside it as `mont` for Egremont,
# `ham` for Eastham, `rtown` for Edgartown. The names survive that because the
# label column is read separately; the word TOTALS did not, so twenty towns --
# every one of them a single-precinct town whose only figure is on that row --
# came back as `no_total` with nothing at all.
# A CLIPPED `TOTALS` -- the table detector cuts the right-hand block's label
# column from the left, so the word arrives as `ALS` -- was tried here and is
# NOT worth having. Recognising it converts a few `no_total` rows, and costs
# eleven municipalities and four points of the volume's registered total,
# because the same clipped forms collide with clipped town names and headings
# stop being recognised. Measured both ways against the volume's own printed
# total of 2,070,956: 95.8% without it, 91.6% with.
#
# The right fix for those rows is to stop the label column being clipped at all,
# not to teach every consumer to recognise the debris.
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


def load_population(root):
    """Municipality -> population, as an upper bound on registered voters.

    NOBODY IS REGISTERED WHO DOES NOT LIVE THERE. The arithmetic check asks only
    whether a town's precincts sum to its total, and a garbled figure sums just
    as well as a real one: the 2002 volume came back with Andover holding
    190,941,718 registered voters and the 1977 volume with a town of
    320,930,000, both marked usable, because their parts added up.

    The population file is one snapshot rather than a figure per year, so the
    bound is deliberately loose -- a town can have grown or shrunk a good deal
    across fifty years of volumes. It is not there to catch a figure that is
    slightly wrong. It is there to catch one that is impossible.
    """
    path = os.path.join(root, 'config', 'population.csv')
    pop = {}
    try:
        with io.open(path, encoding='utf-8', newline='') as fh:
            for row in csv.DictReader(fh):
                name = (row.get('community') or '').strip()
                n = (row.get('population') or '').strip()
                if name and n.isdigit():
                    pop[name.lower()] = int(n)
    except (OSError, ValueError, csv.Error):
        pass
    return pop


# A town's registered voters against its population. Registration runs at
# perhaps two thirds of population, so twice it is already far outside anything
# real, and leaves room for a town that has shrunk since the population figure.
POP_FACTOR = 2.0


def implausible(town, pop):
    """Why this town's figures cannot be real, or None."""
    reg, voted = town.get('reg'), town.get('voted')
    if reg is not None and voted is not None and voted > reg:
        return 'more people voted (%s) than were registered (%s)' % (voted, reg)
    if reg is None:
        return None
    cap = pop.get((town.get('municipality') or '').lower())
    if cap and reg > cap * POP_FACTOR:
        return ('%s registered voters against a population of about %s'
                % (format(reg, ','), format(cap, ',')))
    # Even without a population figure, no Massachusetts municipality has ever
    # had half a million registered voters -- Boston, the largest, has around
    # four hundred thousand.
    if reg > 500000:
        return '%s registered voters, more than any municipality has' % format(reg, ',')
    return None


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

    # A TRUNCATED HEAD, WHERE ONLY ONE TOWN COULD FINISH IT. The table detector
    # clips the label column, so names arrive cut: `Royals`, `Belche`, `Bernar`,
    # `Blandf`, `Foxbor`, `Barnst`. Each of those is the start of exactly one
    # Massachusetts municipality and is safe to complete.
    #
    # `North` is the start of five and `New` of several, so those stay as they
    # are and are reported. Completing them by picking the first would silently
    # file five towns' figures under one name, which is worse than a stub -- a
    # stub is visibly wrong, a confident wrong answer is not.
    if len(raw) >= 4:
        pre = [n for n in names if n.lower().startswith(low)]
        if len(pre) == 1:
            return pre[0], 'by head'
    return raw, 'unmatched'


def num(s):
    s = (s or '').replace(',', '').replace(' ', '').strip()
    return int(s) if s.isdigit() else None


def block_split(page, words=None):
    """The x of the gutter between the two column blocks, or None for one block.

    Measured as the widest gap between consecutive word starts in a narrow band
    round the centre. Two better-sounding measures were tried and are worse:

      * The widest gap in the middle THIRD finds a gap INSIDE the right-hand
        block -- between its precinct numbers and its date column -- and splits
        the page there, which puts the right block's town column into the left
        block and files every figure against the wrong town.
      * A profile of how many rows cross each column, which is what a gutter
        really is, lands at 218 on the 2008 table where the gutter sits near
        260. Over sixty rows of dot leaders there is no column the rows leave
        alone, and the quietest one is not the right one.

    So this stays, and the noise in it is handled where it is used: a page whose
    reading is far from its table's median is overruled by the median.
    """
    W = page.rect.width
    if words is None:
        words = page.get_text('words')
    xs = sorted(w[0] for w in words)
    if len(xs) < 2:
        return None
    gaps = [(xs[i + 1] - xs[i], (xs[i] + xs[i + 1]) / 2)
            for i in range(len(xs) - 1)
            if W * 0.44 < (xs[i] + xs[i + 1]) / 2 < W * 0.56]
    if not gaps:
        return None
    g, at = max(gaps)
    # NO GUTTER MEANS ONE COLUMN, NOT A GUESS AT WHERE THE GUTTER WOULD BE. The
    # 1970s volumes set the table as a single block across the page, and falling
    # back to half the width cut every row in two -- the town name and date on
    # one side, its figures on the other. The figures were being read correctly
    # the whole time; they were simply cut off from the names.
    return at if g > 8 else None


def label_lines(page, lo, hi):
    """(y, text) for each printed line of the label column, in order."""
    words = sorted((w for w in page.get_text('words') if lo <= w[0] < hi),
                   key=lambda w: w[1])
    # GROUP BY GAP, NOT BY BUCKET. Rounding y into three-point buckets splits a
    # name whose two words sit three points apart across a bucket boundary --
    # `New` at 468 and `Braintree` at 471 became separate lines, so New
    # Braintree and New Marlborough collapsed into a row called `New` holding
    # the sum of three towns. The rows themselves are twenty-eight points apart
    # here, so grouping words within six points of each other cannot merge two
    # of them.
    lines, cur = [], []
    for w in words:
        if cur and w[1] - cur[-1][1] > 3.5:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)

    out = []
    for ws in lines:
        ws = sorted(ws, key=lambda w: w[0])
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
    """The town name printed against this row band, if any.

    THE NEAREST LABEL, NOT THE FIRST ONE IN A TIGHT WINDOW. This used to take
    whichever town-like label fell inside three points of the band and stop
    there. With the skew that window is often empty, so the row kept the name
    the table detector gave it -- and the table detector clips the label column,
    so that name is a stub.

    `North` was the result, five times over: the label column plainly reads
    `North Attleborough`, `North Brookfield`, `North Reading`, `Northborough`,
    `Northbridge`, and all five collapsed into one row called North holding the
    sum of all of them. Searching a row height either way and taking the closest
    match finds the name that is actually printed there.
    """
    mid = (y0 + y1) / 2.0
    span = max(12.0, (y1 - y0) * 1.5)
    best = None
    for y, text in labels:
        d = abs(y + off - mid)
        if d > span:
            continue
        clean = re.sub(r'\s*P[ce]t\.?\s*[\dA-Z]*\s*$', '', delead(text))
        clean = TRAIL.sub('', clean)
        clean = re.sub(r'[^A-Za-z .\'-]', '', clean).strip(' .')
        if TOWN.match(clean) and not PCT.match(clean) \
                and not TOTALS.search(clean):
            if best is None or d < best[0]:
                best = (d, clean)
    return best[1] if best else None



def column_anchors(page, lo, hi):
    """Where the two figure columns are, in x. -> (reg_span, voted_span) or None

    THE PAGE SAYS WHICH COLUMN A NUMBER IS IN. Every word carries a bounding
    box, the table is a grid, and the column headings are printed at the top of
    it: `Registered Voters` over one column and `People Who Voted` over the
    other. A figure under the first is a registered count and a figure under the
    second is a turnout, and nothing else needs to be inferred.

    Reading the row as an ordered list of numbers and taking the last two
    instead is what produced Norton's 1,225 / 1,225 and Ashland's phantom
    precinct: one stray token on a row and every value shifts a column. Order is
    a guess about position. Position is not.
    """
    ws = [w for w in page.get_text('words') if lo <= w[0] < hi]
    if not ws:
        return None
    # The column-heading row is the one carrying `Town`, below any running head.
    head_y = None
    for w in ws:
        if w[4] == 'Town' and w[1] > page.rect.height * 0.08:
            head_y = w[1]
            break
    if head_y is None:
        return None
    band = [w for w in ws if abs(w[1] - head_y) < 12]

    def span(*names):
        hit = [w for w in band if w[4] in names]
        return (min(w[0] for w in hit), max(w[2] for w in hit)) if hit else None

    reg = span('Registered', 'Voters')
    vot = span('Voted', 'Who')
    if not (reg and vot) or reg[0] >= vot[0]:
        return None
    return reg, vot


def by_column(cells, boxes, reg, vot):
    """Pull the registered and voted figures out by WHERE they sit."""
    got = {'reg': None, 'voted': None}
    for text, box in zip(cells, boxes):
        v = num(text)
        if v is None or box is None:
            continue
        mid = (box[0] + box[2]) / 2.0
        # A cell belongs to the column its centre falls in, and a cell that
        # spans both goes to whichever it overlaps more.
        if reg[0] - 6 <= mid <= reg[1] + 6:
            got['reg'] = v
        elif vot[0] - 6 <= mid <= vot[1] + 10:
            got['voted'] = v
    return got


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
    anchors = column_anchors(page, lo, hi)
    # The table detector clips the leftmost column, so a row's own first cell is
    # not always the whole label; keep the band so the label column can supply it.
    out = []
    for i, row in enumerate(cells):
        label, figs, joined = split_row(row)
        col0 = delead(row[0] or '')
        band = bands[i] if i < len(bands) else (0, 0, 0, 0)
        boxes = table.rows[i].cells if i < len(table.rows) else []
        cols = (by_column(row, boxes, anchors[0], anchors[1])
                if anchors and boxes else None)
        out.append({'label': col0 or label, 'figs': figs, 'joined': joined,
                    'band': band, 'cols': cols})
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

    # TELL TESSERACT THE FIGURE COLUMNS ARE FIGURES.
    #
    # Everything to the right of the label column on this page is a number.
    # Reading it with the full alphabet available invites the letters in, and on
    # a soft scan they come: a 1973 page returned `5006060010000000` for a
    # registered count. Restricted to digits and commas the same page returns
    # `16,535 11,387`, `1,695 1,167`, `1,299 856` -- exactly what is printed.
    #
    # The pass is only worth its seconds where the general one struggled, so it
    # runs when the figures look damaged: a figure column should be nearly all
    # numeric, and when less than four fifths of it is, it is worth re-reading.
    figs = [(d['left'][i], d['text'][i]) for i in range(len(d['text']))
            if (d['text'][i] or '').strip()
            and d['left'][i] >= label_w(page) * OCR_ZOOM]
    numeric = sum(1 for _x, t in figs if re.fullmatch(r'[\d,]+', t))
    if figs and numeric < len(figs) * 0.8:
        cutpx = int(label_w(page) * OCR_ZOOM)
        try:
            right = img.crop((cutpx, 0, img.width, img.height))
            dn = pytesseract.image_to_data(
                right, output_type=pytesseract.Output.DICT,
                config='--psm 6 -c tessedit_char_whitelist=0123456789,')
            # Splice the digit reading back in, shifted to page coordinates, and
            # keep the label column from the general pass.
            merged = {k: list(v) for k, v in
                      (('text', []), ('left', []), ('top', []), ('height', []),
                       ('block_num', []), ('par_num', []), ('line_num', []))}
            for i, t in enumerate(d['text']):
                if (t or '').strip() and d['left'][i] < cutpx:
                    for k in merged:
                        merged[k].append(d[k][i])
            for i, t in enumerate(dn['text']):
                if not (t or '').strip():
                    continue
                merged['text'].append(t)
                merged['left'].append(dn['left'][i] + cutpx)
                for k in ('top', 'height', 'block_num', 'par_num', 'line_num'):
                    merged[k].append(dn[k][i])
            if merged['text']:
                d = merged
        except Exception:
            pass

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
        # `head_figs` counts as data: a single-precinct town in the older
        # layout has nothing else -- its whole entry is the one heading row --
        # and leaving it out of this test silently dropped half of them.
        if cur and (cur['precincts'] or cur['reg'] is not None
                    or cur.get('head_figs') or cur['no_election']):
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
            heads = how_c in ('exact', 'snapped', 'by head')

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
                if how in ('exact', 'snapped', 'by tail', 'by head'):
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
            # IN THE OLDER LAYOUT THE TOTAL SITS ON THE TOWN'S OWN ROW, and
            # there is no TOTALS row at all:
            #
            #     Danvers      May 5    13,751   2,710
            #       Precinct 1           1,924      337
            #                 2          1,895      340
            #
            # 1,924 + 1,895 + ... = 13,751, so the arithmetic still closes -- but
            # only if that first row is read as the total rather than as another
            # precinct. Read as a precinct it both invents a precinct and leaves
            # the town with no total, which is why the 1981 volume verified none
            # of its 239 municipalities.
            #
            # The date is cut out of the row before the figures are counted, so
            # `April 26, 2008` cannot contribute a 26 and a 2008. Whatever is
            # left is data. A later TOTALS row, where one exists, overrides this.
            # WHICH IT IS DEPENDS ON WHETHER A TOTALS ROW TURNS UP LATER, and
            # that is not known yet, so the decision is deferred. Both layouts
            # occur, and in 2008 some towns really do print their first precinct
            # on the heading row: deciding either way here costs about ten
            # verified towns a volume in one direction or the other.
            rest = (joined[:m.start()] + ' ' + joined[m.end():]) if m else joined
            own = [num(x) for x in re.findall(r'[\d,]+', rest)]
            own = [x for x in own if x is not None]
            # A PLAUSIBILITY GUARD, because the year can survive the date
            # match in pieces. The 2008 table detector splits `2008` across two
            # cells as `2` and `008`, so the leftovers read as 2 registered
            # voters and 8 who voted -- a phantom precinct inserted at the head
            # of 140 towns. No municipality has twenty registered voters, and
            # nowhere can more people vote than are registered.
            if len(own) >= 2 and own[-2] >= 20 and own[-2] >= own[-1]:
                cur['head_figs'] = (own[-2], own[-1])
            continue

        if cur is None:
            continue

        if TOTALS.search(col0 or '') or (not col0 and TOTALS.search(joined)):
            # BY COLUMN WHERE THE PAGE SAYS SO, by order only where it does not.
            cols = row.get('cols')
            if cols and (cols['reg'] is not None or cols['voted'] is not None):
                cur['reg'], cur['voted'] = cols['reg'], cols['voted']
            elif len(figs) >= 2:
                cur['reg'], cur['voted'] = figs[-2], figs[-1]
            elif figs:
                cur['reg'] = figs[-1]
            continue

        # A WARD IS A SUBTOTAL, NOT A PRECINCT. The city tables run three deep
        # -- city, ward, precinct -- and the ward line carries the sum of the
        # precincts beneath it. Counted as a precinct it doubles the city, so
        # nothing ever adds up; kept separately it becomes a second arithmetic
        # check rather than a source of noise.
        if figs and re.match(r'^Ward\s*[0-9A-Z]+\s*$', col0 or '', re.I):
            cur.setdefault('wards', []).append(
                {'ward': col0, 'reg': figs[-2] if len(figs) >= 2 else figs[-1],
                 'voted': figs[-1] if len(figs) >= 2 else None})
            continue

        if figs:
            mp = PCT.match(col0) if col0 else None
            pnum = next((g for g in (mp.groups() if mp else ()) if g), None)
            cols = row.get('cols')
            if cols and (cols['reg'] is not None or cols['voted'] is not None):
                cur['precincts'].append(
                    {'precinct': pnum, 'reg': cols['reg'],
                     'voted': cols['voted']})
            else:
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


def settle_head_row(t):
    """Decide what the figures on the town's own row were.

    A TOTALS row later in the town means the heading row held its FIRST
    PRECINCT; no TOTALS row means the heading row held the town's TOTAL, which
    is how the volumes were set before the mid-eighties. Deferring the call
    until the whole town has been read is the only way to tell, and it is worth
    telling: guessing costs about ten verified towns a volume either way.
    """
    head = t.pop('head_figs', None)
    if not head:
        return
    if t['reg'] is None:
        t['reg'], t['voted'] = head
    else:
        t['precincts'].insert(0, {'precinct': None, 'reg': head[0],
                                  'voted': head[1]})


def reconstruct(t):
    """Rebuild what the scan destroyed, from what survived it.

    A page does not have to be re-read to be recovered. The TOTALS row of a town
    IS the sum of its precincts -- that is what the word means -- so a town whose
    precincts came through cleanly and whose totals row did not is not missing
    data, it is missing an addition. Doing that addition is not inventing a
    figure; refusing to do it and calling the town unreadable is throwing one
    away.

    The reverse holds too. Where the total survived and exactly ONE precinct did
    not, that precinct is the total less the others, and there is only one number
    it can be.

    Both are marked `derived`, never `checked`. They are reconstructions, and a
    reader should be able to tell them from a figure the volume printed and this
    parser merely read.
    """
    p = t['precincts']
    if not p:
        return None

    # The total is the sum of the precincts. THE TWO COLUMNS ARE REBUILT
    # INDEPENDENTLY: the registered total and the people-who-voted total are
    # separate figures on the page and the scan damages them separately. Seven
    # towns in the 2008 volume have every precinct intact in both columns, a
    # sound registered total and no voted total at all -- rebuilding only when
    # BOTH were missing left all seven of them with half their data.
    did = []
    if t['reg'] is None:
        sreg = sum(x['reg'] for x in p if x['reg'] is not None)
        if sreg and all(x['reg'] is not None for x in p):
            t['reg'] = sreg
            did.append('registered')
    if t['voted'] is None:
        svote = sum(x['voted'] for x in p if x['voted'] is not None)
        if svote and all(x['voted'] is not None for x in p):
            t['voted'] = svote
            did.append('people who voted')
    if did:
        # NOT a return. Rebuilding one column does not mean the other is sound:
        # Norton's voted total rebuilds cleanly and its registered total is still
        # the voted figure sitting in the wrong column. Returning here left every
        # such town half-repaired and reported as `voted_only`.
        t['derived'] = ('%s total is the sum of its %d precincts'
                        % (' and '.join(did), len(p)))

    # THE TOTALS ROW LOST ITS REGISTERED FIGURE AND KEPT ITS VOTED ONE.
    #
    # Two shapes of the same accident, both found by adding up what is on the
    # page and seeing what is left over.
    #
    # Norton reads 1,225 / 1,225 -- and 281+264+214+269+197 is 1,225, so that is
    # the voted total sitting in both columns, with the registered total gone.
    # Rutland and Sudbury do the same.
    svote = sum(x['voted'] for x in p if x['voted'] is not None)
    sreg = sum(x['reg'] for x in p if x['reg'] is not None)
    if (t['reg'] is not None and t['reg'] == t['voted'] == svote
            and svote and sreg and sreg != svote):
        t['reg'] = sreg
        t['derived'] = ('the totals row kept only its people-who-voted figure; '
                        'registered rebuilt as the sum of %d precincts' % len(p))
        return 'total'

    # Ashland reads four precincts and then a fifth of 4,324 with nothing beside
    # it -- and 1,206+1,250+1,076+792 is 4,324. That is not a precinct, it is the
    # voted total, read into the registered column of a row of its own.
    if len(p) >= 2 and p[-1]['voted'] is None and p[-1]['reg'] is not None:
        body = p[:-1]
        bvote = sum(x['voted'] for x in body if x['voted'] is not None)
        breg = sum(x['reg'] for x in body if x['reg'] is not None)
        if bvote and p[-1]['reg'] == bvote and all(
                x['voted'] is not None for x in body):
            t['precincts'] = body
            t['voted'] = bvote
            t['reg'] = breg
            t['derived'] = ('the voted total was read as a precinct of its own; '
                            'both totals rebuilt from %d precincts' % len(body))
            return 'total'

    # One precinct missing under a total that survived.
    if t['reg'] is not None:
        gaps = [x for x in p if x['reg'] is None]
        if len(gaps) == 1:
            known = sum(x['reg'] for x in p if x['reg'] is not None)
            missing = t['reg'] - known
            if 0 < missing < t['reg']:
                gaps[0]['reg'] = missing
                t['derived'] = ('one precinct rebuilt as the total less the '
                                'other %d' % (len(p) - 1))
                return 'precinct'
    return None


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
    wards = t.get('wards') or []
    if wards:
        # precincts -> wards -> city. Either link closing is worth reporting;
        # both closing is as good as the flat case.
        sp = sum(x['reg'] for x in t['precincts'] if x['reg'] is not None)
        sw = sum(x['reg'] for x in wards if x['reg'] is not None)
        if sp and sp == sw and (t['reg'] is None or t['reg'] == sw):
            return 'checked', ('precincts sum to their wards, and the wards to '
                               'the municipality')
        if t['reg'] is not None and t['reg'] == sw:
            return 'ward_only', 'wards sum to the municipality; precincts do not'
        return 'hierarchy', ('a city table three levels deep; %d precincts sum '
                             'to %s against %s in %d wards'
                             % (len(t['precincts']), sp, sw, len(wards)))

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
    """-> [(kind, [page indexes])], kind being 'town' or 'city'.

    A VOLUME CAN HOLD TWO OF THESE TABLES. Until 1984 the series was annual and
    the odd-year booklets are given over to local elections, tabulating CITY
    elections -- by ward and precinct, with preliminaries -- as well as town
    ones. Cities are absent from every biennial volume, so those booklets are
    the only source in the series for them, and returning just the longest run
    of pages threw one of the two tables away.

    The city heading also says PERSONS WHO VOTED where the town heading says
    PEOPLE, which is why a pattern written against a 2008 volume finds nothing
    in a 1981 one.
    """
    # A TABLE IS A RUN OF HEADINGS, EXTENDED TO THE NEXT SECTION.
    #
    # The modern volumes repeat the full heading on every page of the table, so
    # the run alone is the table. The older ones print it once and then carry a
    # running head that the scan mangles past recognition -- `Tcvvns and Vocisg
    # ?TSC±CtS`, `Cir.es. "vards ana Dace ot` -- and several of those pages have
    # no text layer at all. Requiring consecutive headings found ONE page of the
    # 1981 town table and none of its city table.
    #
    # So the run is found as before and then extended forward until the next
    # thing that is definitely a different section: another table's heading, or
    # the candidate results that follow.
    # THE CONTENTS PAGE SAYS THE SAME WORDS. It lists `Number of Registered
    # Voters and People Who Voted` in title case; the table itself shouts it in
    # capitals. Case is the only thing that separates them, and without it the
    # 2008 contents and summary pages were picked up as a seven-page city table
    # that does not exist in that volume.
    heads = []
    for i, p in enumerate(doc):
        t = p.get_text()
        if HEAD.search(t):
            k = page_kind(t)
            if k:
                heads.append((i, k))

    # A VOLUME CAN HAVE NO TEXT AT ALL, not even a heading to find.
    #
    # The odd-year booklets -- 1971, 1973, 1975, 1977, 1979 -- were scanned
    # without OCR, so every page reports about twenty words of running head or
    # nothing. The table cannot be located before OCR and then read, which is the
    # order everything else here assumes; it has to be located BY OCR.
    #
    # Only the top of each page is read for this, which is where a heading is,
    # and at a lower zoom than the table itself needs. A 60-page booklet costs
    # about twenty seconds to index this way, against several minutes to OCR
    # whole. These five booklets are the only volumes in the series that cover
    # city elections and odd-year town elections at all, so they are worth it.
    if not heads and len(doc) < 200:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return []
        for i, p in enumerate(doc):
            if len(p.get_text('words')) > 60:
                continue
            strip = pymupdf.Rect(0, 0, p.rect.width, p.rect.height * 0.30)
            try:
                pix = p.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), clip=strip)
                txt = pytesseract.image_to_string(
                    Image.open(io.BytesIO(pix.tobytes('png'))), config='--psm 6')
            except Exception:
                continue
            if HEAD.search(txt):
                k = page_kind(txt)
                if k:
                    heads.append((i, k))
        if heads:
            print('   found %d heading(s) by OCR: the volume has no text layer'
                  % len(heads))
    if not heads:
        return []

    runs, run, kind = [], [], None
    for i, k in heads:
        if run and k == kind and i == run[-1] + 1:
            run.append(i)
        else:
            if run:
                runs.append((kind, run))
            run, kind = [i], k
    runs.append((kind, run))

    # Contents entries are runs of one that sit among the front matter; a real
    # table always has figures under it, so a run whose following pages carry no
    # numbers at all is not one.
    ENDS = re.compile(r'VOTES\s+RECE|CANDIDATE|PRESIDENTIAL\s+PRIMAR'
                      r'|STATE\s+PRIMAR|TABLE\s+OF\s+CONTENTS', re.I)
    out = []
    for n, (k, r) in enumerate(runs):
        stop = len(doc)
        for j in range(r[-1] + 1, len(doc)):
            t = doc[j].get_text()
            if ENDS.search(t) or (HEAD_CAPS.search(t) and j not in r):
                stop = j
                break
        pages = list(range(r[0], max(r[-1] + 1, stop)))
        figures = sum(len(re.findall(r'\b\d[\d,]{2,}\b', doc[i].get_text()))
                      for i in pages)
        blank = sum(1 for i in pages if len(doc[i].get_text('words')) < 60)
        # Either it has figures, or its pages are scans that OCR will supply.
        if len(pages) >= 2 and (figures >= 20 or blank >= 2):
            out.append((k, pages))
    return out


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
    tables = table_pages(doc)
    if not tables:
        print('no local-election table in %s' % os.path.basename(a.pdf))
        return 1
    for kind, pp in tables:
        print('%s table: pages %d-%d' % (kind, pp[0] + 1, pp[-1] + 1))
    pages = [i for _k, pp in tables for i in pp]
    kind_of = {i: k for k, pp in tables for i in pp}

    names = load_municipalities(ROOT)
    pop = load_population(ROOT)
    print('%d municipalities in the reference list' % len(names))
    # ONE LAYOUT PER TABLE, SO ONE GUTTER PER TABLE.
    #
    # Measured page by page, the gutter wanders: on the 2008 table it comes out
    # at 258 on most pages and 289 or 293 on three of them, and on those three
    # the left block swallows the right block's label column and every town on
    # it is lost. 59 of the volume's 310 towns went that way.
    #
    # The pages of one table are the same layout, so the per-page reading is a
    # measurement of one quantity with noise on it. The median is that quantity.
    # PER PAGE WHERE THE PAGE AGREES, THE TABLE'S MEDIAN WHERE IT DOES NOT.
    #
    # The gutter is a property of the page and a scanned book does shift, so the
    # page's own reading should win -- but only when it IS a reading. Measured
    # across the 2008 table these come out anywhere from 212 to 315 for a gutter
    # that really sits near 260, and a reading 50 points out does not shift a
    # column, it swallows one: the left block takes the right block's names and
    # every town on that page is lost.
    #
    # The pages of one table share a layout, so the median is the best estimate
    # of the quantity and each page's own reading is that quantity plus noise.
    # A reading close to the median is trusted as a real shift; one far from it
    # is noise and is replaced. Which is not a fudge -- it is what you do with
    # repeated measurements of something that moves slowly.
    splits = [x for x in (block_split(doc[i]) for i in pages) if x]
    median = sorted(splits)[len(splits) // 2] if splits else None
    if median:
        near = sum(1 for x in splits if abs(x - median) <= 6)
        print('   column gutter %.0f; %d of %d pages agree within 6pt'
              % (median, near, len(splits)))

    year = a.year

    def read_page(page, split, kind, force_ocr):
        """Read one page at one candidate split. -> (towns, used_ocr)"""
        blocks = ([(0, page.rect.width)] if split is None
                  else [(0, split), (split, page.rect.width)])
        out, used = [], False
        for lo, hi in blocks:
            got, ocr = parse_block(page, lo, hi, year, force_ocr=force_ocr,
                                   names=names)
            for t in got:
                t['by_ocr'] = ocr
                t['kind'] = kind
            out += got
            used = used or ocr
        return out, used

    def score(towns):
        """How well a reading of a page holds together.

        The arithmetic check is already the thing that decides whether a town
        was read correctly, so it decides this too: a split that carves the page
        in the wrong place produces towns whose precincts do not sum, and one
        that carves it in the right place produces towns that do. Ties go to the
        reading that found more towns, so a split that finds two perfect towns
        does not beat one that finds twenty good ones.
        """
        good, coherent = 0, 0
        for t in towns:
            settle_head_row(t)
            recover_total(t)
            st, _ = check(t)
            if st in ('checked', 'single', 'no_election'):
                good += 1
            # THE SECOND COLUMN HAS TO BE COHERENT TOO. The sum test only looks
            # at registered voters, so a split that clips the `People Who Voted`
            # column scores full marks while half its figures are wrong --
            # Burlington 1996 read 2,119 registered against 26 voted where the
            # page prints 269.
            rows = [(t['reg'], t['voted'])] + [(p['reg'], p['voted'])
                                               for p in t['precincts']]
            for reg, voted in rows:
                if reg and voted and voted <= reg and voted >= reg * 0.02:
                    coherent += 1
        return (good, coherent, len(towns))

    rows, ocr_pages = [], set()
    for i in pages:
        page = doc[i]
        kind = kind_of.get(i, 'town')

        # TRY THE CANDIDATES AND KEEP WHAT READS, rather than tuning one guess.
        #
        # Every rule for placing the gutter from the page alone was wrong
        # somewhere: the widest gap in the middle third splits inside the right
        # block, the quietest column lands at 218 where the gutter is at 260,
        # the page's own reading swings 245-293 across one table, and the
        # table's median throws away the pages that really did shift.
        #
        # But the reading does not have to be decided in advance. The page can
        # be read several ways and scored, and there is an honest scorer to hand
        # -- the same arithmetic that decides whether any town was read
        # correctly. A wrong split produces towns whose precincts do not sum.
        own = block_split(page)
        cands = []
        # READING A TWO-COLUMN PAGE AS ONE BLOCK IS NOT A CANDIDATE.
        #
        # It was, and it won often enough to matter: on a page read whole, the
        # left column's town picks up the right column's figures, and enough of
        # those accidents survive the arithmetic to beat the correct reading.
        # Burlington 1996 came out as 1,616 / 1,372 -- Cohasset's numbers, from
        # the other side of the page -- against a printed 13,290 / 1,703, and
        # Canton's total was Concord's fourth precinct.
        #
        # So one block is offered only when no gutter was found at all, which is
        # the genuine single-column case the 1970s volumes need.
        if own is None and median is None:
            cands = [None]
        else:
            for c in (own, median):
                if c is not None and c not in cands:
                    cands.append(c)
            if median is not None:
                for d in (-10, 10):
                    if median + d not in cands:
                        cands.append(median + d)
        # OCR is seconds a block, so a page without a text layer is read once,
        # at the table's best guess, rather than five times.
        # OCR costs seconds a block, so a page without a text layer tries two
        # candidates rather than five -- enough to rescue a page whose own
        # reading is wrong, without reading the volume five times over.
        # ONE CANDIDATE ON AN OCR PAGE. Reading such a page costs seconds, and
        # it is now read twice over -- once for the labels and once with the
        # figure columns restricted to digits. Trying several splits on top of
        # that put a single 1970s volume past ten minutes.
        if len(page.get_text('words')) < 60 or a.ocr:
            cands = cands[:1] if cands else [None]

        best, best_score = None, (-1, -1)
        for c in cands:
            try:
                got, ocr = read_page(page, c, kind, a.ocr)
            except Exception:
                continue
            sc = score(got)
            if sc > best_score:
                best, best_score, best_ocr = got, sc, ocr
        if best:
            rows += best
            if best_ocr:
                ocr_pages.add(i)

    # One town can straddle a column or page break; merge fragments by name.
    merged = {}
    for t in rows:
        k = (t.get('kind', 'town'), t['municipality'].lower())
        if k in merged:
            m = merged[k]
            m['precincts'] += t['precincts']
            for f in ('date', 'reg', 'voted', 'head_figs'):
                if m.get(f) is None and t.get(f) is not None:
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
        w.writerow(['municipality', 'kind', 'year', 'date', 'level',
                    'precinct', 'registered', 'voted', 'status', 'note',
                    'read_by'])
        n_pct = 0
        for t in sorted(merged.values(), key=lambda x: x['municipality']):
            settle_head_row(t)
            recover_total(t)
            reconstruct(t)
            st, note = check(t)
            # A FIGURE THAT CANNOT BE REAL IS NOT USABLE, however well it adds
            # up. This runs last, after every repair, because a reconstruction
            # can produce an impossible total just as a bad reading can.
            bad = implausible(dict(t, municipality=t['municipality']), pop)
            if bad:
                st, note = 'implausible', bad
            if t.get('derived') and st in ('checked', 'single'):
                st = 'derived'
                note = t['derived']
            if t.get('recovered') and st == 'checked':
                note += ('; the TOTALS label was unreadable and was '
                         'identified by the sum')
            counts[st] = counts.get(st, 0) + 1
            if a.verbose and st in ('mismatch', 'no_total'):
                print('   ? %-24s %s' % (t['municipality'], note))
            how = 'ocr' if t.get('by_ocr') else 'text'
            w.writerow([t['municipality'], t.get('kind', 'town'), a.year,
                        t['date'] or '', 'total', '',
                        t['reg'] if t['reg'] is not None else '',
                        t['voted'] if t['voted'] is not None else '',
                        st, note, how])
            for i, p in enumerate(t['precincts'], 1):
                n_pct += 1
                w.writerow([t['municipality'], t.get('kind', 'town'), a.year,
                            t['date'] or '', 'precinct', p.get('precinct') or i,
                            p['reg'] if p['reg'] is not None else '',
                            p['voted'] if p['voted'] is not None else '',
                            st, '', how])

    dated = sum(1 for t in merged.values() if t['date'])
    # USABLE, NOT `checked`. A `single` is an undivided town with one printed
    # figure and nothing to cross-foot -- it is as good a denominator as a town
    # whose precincts sum, and reporting only `checked` understated 2008 as 54%
    # when 86% of its municipalities are fit to use.
    usable = counts.get('checked', 0) + counts.get('single', 0)
    # Measured against the names actually printed in this volume's table, not
    # against 351 and not against a sentence in the summary. Names are the one
    # thing about a Massachusetts municipality that never changes.
    named = named_in(doc, pages, names)
    of = (' of %d named in it' % len(named)) if named else ''
    print('%d municipalities%s, %d usable (%.0f%%), %d verified by arithmetic'
          % (len(merged), of, usable,
             100.0 * usable / max(1, len(merged)), counts.get('checked', 0)))
    # A SINGLE-PRECINCT TOWN HAS NO ARITHMETIC TO CHECK, so the volume's own
    # count of them is the only check there is. Agreement closes a hole; a
    # shortfall says exactly how many undivided towns were missed, which is
    # otherwise invisible -- they look like successes.
    said_single = stated_counts(doc).get('single')
    if said_single:
        found = counts.get('single', 0)
        verdict = ('matches the volume' if found == said_single
                   else 'the volume states %d, so %d %s'
                   % (said_single, abs(said_single - found),
                      'are missing' if found < said_single else 'are extra'))
        print('   single-precinct towns: %d found, %s' % (found, verdict))
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
