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
    hit = {}
    for n in names:
        c = len(re.findall(r'\b' + re.escape(n) + r'\b', text, re.I))
        if c:
            hit[n] = c
    # A SHORTER NAME INSIDE A LONGER ONE IS NOT A SECOND TOWN. `Marlborough`
    # matches inside `New Marlborough`, `Salem` inside `New Salem`,
    # `Springfield` inside `West Springfield` -- and with word boundaries all
    # three look like municipalities this table names, which is why three cities
    # kept appearing as missing towns. Where every occurrence of the short name
    # is accounted for by longer ones, it is not on the page at all.
    out = set()
    for n, c in hit.items():
        inside = 0
        for m, mc in hit.items():
            if m != n and re.search(r'\b' + re.escape(n) + r'\b', m, re.I):
                inside += mc
        if c > inside:
            out.add(n)
    return out


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
PCT = re.compile(r'^P[ce]t\.?\s*([0-9]+|[A-Z])\b|^([0-9]{1,2})$|^([A-Z])$'
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
# THE YEAR MUST BE PRECEDED BY A COMMA, or it is not a year. The date column in
# these volumes prints `May 6` and nothing more -- the year lives in the page
# heading -- so an optional trailing `(\d{2,4})?` does not find a year, it finds
# the registered-voter count sitting in the next column. `Millis May 6 4212`
# parsed as "May 6, 4212" and swallowed the town's own figure, which is why
# Millis and Monroe were read perfectly and then emitted with nothing in them.
DATE = re.compile(r'\b(%s)\w*\.?\s*(\d{1,2})(?:\s*,\s*(\d{2,4}))?' % '|'.join(
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


NAMED_OK = ('exact', 'snapped', 'by head', 'by tail', 'by position')


def resolve_by_order(towns, names):
    """Settle a stub name by where it sits in an alphabetical table.

    THE TABLE IS IN ALPHABETICAL ORDER, so a row's neighbours say what it is.
    A stub reading `New` between Nahant and New Salem can only be New Ashford,
    New Braintree or New Marlborough; one whose name was lost entirely, sitting
    between Manchester and Marion, can only be Marblehead.

    This is the last resort and it is deliberately strict: it settles a name
    only when exactly ONE municipality fits between the neighbours. `New` with
    two candidates still between them stays a stub and is reported, because a
    confident wrong name is worse than a visible gap -- that is how five towns
    ended up merged into a row called North.
    """
    ordered = sorted(names, key=str.lower)
    for i, t in enumerate(towns):
        if t.get('name_how') in NAMED_OK:
            continue
        prev = nxt = None
        for j in range(i - 1, -1, -1):
            if towns[j].get('name_how') in NAMED_OK:
                prev = towns[j]['municipality']
                break
        for j in range(i + 1, len(towns)):
            if towns[j].get('name_how') in NAMED_OK:
                nxt = towns[j]['municipality']
                break
        if not (prev or nxt):
            continue
        used = {x['municipality'].lower() for x in towns
                if x.get('name_how') in NAMED_OK}
        band = [n for n in ordered
                if (prev is None or n.lower() > prev.lower())
                and (nxt is None or n.lower() < nxt.lower())
                and n.lower() not in used]
        stub = re.sub(r'[^A-Za-z]', '', t['municipality'] or '').lower()
        narrowed = [n for n in band
                    if stub and (n.lower().startswith(stub[:3])
                                 or stub in re.sub(r'[^a-z]', '', n.lower()))]
        pick = narrowed or band
        if len(pick) == 1:
            t['municipality'] = pick[0]
            t['name_how'] = 'by position'


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


# WHAT THE VOLUME PRINTS IS NOT ALWAYS WHAT THE LIST CALLS IT. These are the
# printed forms whose canonical name shares too few characters for any string
# rule to bridge: the volume sets `Manchester-by-the-Sea` and the label column
# keeps only the tail, which has nothing in common with `Manchester`.
PRINTED_AS = {
    'by-the-sea': 'Manchester',
    'bythesea': 'Manchester',
    'manchester-by-the-sea': 'Manchester',
    'manchester by the sea': 'Manchester',
}


def snap(name, names):
    """An OCR town name, matched to the closed list. -> (name, how)"""
    import difflib
    raw = NOISE.sub(' ', TRAIL.sub('', name or ''))
    raw = re.sub(r'\s+', ' ', raw).strip(' .-')
    if not raw:
        return None, 'empty'
    alias = PRINTED_AS.get(re.sub(r'\s+', ' ', raw.lower()).strip())
    if alias and alias in names:
        return alias, 'exact'
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

    # THE PRINTED NAME CAN BE LONGER THAN THE CANONICAL ONE. The volume prints
    # `Manchester-by-the-Sea`; the list of municipalities calls it `Manchester`.
    # So a reading that STARTS WITH a known name is that town, which is the
    # mirror of the clipped case above.
    longer = [n for n in names if low.startswith(n.lower()) and len(n) >= 4]
    if len(longer) == 1:
        return longer[0], 'by head'
    return raw, 'unmatched'


def num(s):
    """A printed count -> an int, or None.

    A PERIOD IS A THOUSANDS SEPARATOR HERE, NOT A DECIMAL POINT. These tables
    count people, so nothing in them is fractional, and the scans render the
    comma as a full stop constantly: `1.639`, `10.385`, `6.946`. Rejecting those
    dropped the figure silently, which is the worst way to lose one -- the row
    survives with a hole in it, the town's precincts no longer sum, and the town
    is discarded for failing a check it should have passed. 1986 Acton lost two
    of its six precincts exactly this way.

    Only a period followed by exactly three digits is treated as a separator, so
    a genuine decimal cannot be silently multiplied by a thousand.
    """
    s = (s or '').replace(',', '').replace(' ', '').strip()
    if s.isdigit():
        return int(s)
    if re.match(r'^\d{1,3}(?:\.\d{3})+$', s):
        return int(s.replace('.', ''))
    return None


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
    # JOINING ADJACENT LABEL LINES WAS TRIED AND IS NOT WORTH IT. It rescues
    # `Manchester-by-the-Sea`, which is set over two lines, and costs seven
    # municipalities: a joined pair beats the correct single line often enough
    # that `North Attleborough` collapses back to `North`. One town is not worth
    # seven, and the wrapped name is caught by the prefix rule in snap() instead.
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



def page_blocks(page):
    """How many column blocks the page has, and where they start. -> [(lo, hi)]

    THE HEADING SAYS HOW MANY COLUMNS THERE ARE. A block is a printed table with
    its own `Registered Voters` heading over it, so counting those headings
    counts the blocks -- two on the modern pages, one on the 1970s ones.

    The gutter heuristic this replaces guessed from whitespace and was wrong in
    both directions: it read 218 on a 2008 page whose gutter is at 260, and it
    read 147 on a 1973 page that has no gutter at all, cutting a single-column
    table in half so that neither half could see both of its columns. Whitespace
    is evidence about the gutter. The heading is a statement about it.
    """
    W = page.rect.width
    heads = sorted(w[0] for w in page.get_text('words')
                   if w[4] in ('Registered', 'Voters')
                   and w[1] < page.rect.height * 0.30)
    if not heads:
        return None
    # Cluster the heading positions: two blocks put them in two groups a long
    # way apart, one block puts them all together.
    groups, cur = [], [heads[0]]
    for x in heads[1:]:
        if x - cur[-1] > W * 0.18:
            groups.append(cur)
            cur = []
        cur.append(x)
    groups.append(cur)
    if len(groups) < 2:
        return [(0, W)]
    edges = [0.0]
    for i in range(len(groups) - 1):
        edges.append((max(groups[i]) + min(groups[i + 1])) / 2.0)
    edges.append(W)
    return [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]


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


# Every OCR failure in this run. A page that needed OCR and did not get it is
# not a page that parsed badly -- it is a page that was never read, and its
# towns are simply absent. That has to end the run loudly rather than appear as
# a slightly lower percentage.
OCR_FAILURES = []


def _find_tesseract():
    """Point pytesseract at the binary, wherever Windows put it.

    THE INSTALLER DOES NOT PUT IT ON PATH. pytesseract then raises on every
    call, and because the OCR failure was caught and logged per block, the run
    finished and reported a completion figure: 1986 came out at "73.3%" while
    five of its eleven table pages -- every page that exists only as an image --
    had produced nothing at all. Whole alphabetical runs of towns were missing,
    Chelsea through Florida among them, and nothing in the summary said so.
    """
    import pytesseract
    import shutil
    if shutil.which('tesseract'):
        return True
    for p in (r'C:\Program Files\Tesseract-OCR\tesseract.exe',
              r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
              os.path.join(os.environ.get('LOCALAPPDATA', ''),
                           'Programs', 'Tesseract-OCR', 'tesseract.exe'),
              os.path.join(os.environ.get('LOCALAPPDATA', ''),
                           'Tesseract-OCR', 'tesseract.exe')):
        if p and os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return False


def _ocr_tokens(img, digits=False, psm=6, minconf=0):
    """(x, y-centre, text) for what Tesseract reads in this image."""
    import pytesseract
    _find_tesseract()
    cfg = '--psm %d' % psm
    if digits:
        # Everything in a figure column is a digit or a comma. Saying so is the
        # difference between `16,535 11,387` and `5006060010000000`.
        cfg += ' -c tessedit_char_whitelist=0123456789,'
    d = pytesseract.image_to_data(img, config=cfg,
                                  output_type=pytesseract.Output.DICT)
    out = []
    for i, t in enumerate(d['text']):
        t = (t or '').strip()
        if not t:
            continue
        try:
            if int(d['conf'][i]) < minconf:
                continue
        except (KeyError, ValueError, TypeError):
            pass
        out.append((d['left'][i], d['top'][i] + d['height'][i] / 2.0, t))
    return out


def ocr_column_bands(img):
    """Where the figure columns are, read off the heading. -> (reg, voted)"""
    from PIL import Image                                        # noqa: F401
    top = img.crop((0, 0, img.width, int(img.height * 0.16)))
    toks = _ocr_tokens(top)

    def span(*names):
        hit = [x for x, _y, t in toks
               if any(t.lower().startswith(n.lower()) for n in names)]
        return (min(hit), max(hit)) if hit else None

    reg, vot = span('Registered', 'Voters'), span('Voted', 'who')
    if not (reg and vot) or reg[0] >= vot[0]:
        return None
    return reg, vot


def rows_from_words(page, lo, hi):
    """Rows from the words layer, each figure in the column it is printed in.

    Returns the same (rows, labels, skew) shape as rows_from_cells.

    Bands are grown around the rows that CARRY FIGURES. A printed row's label
    does not always share a baseline with its numbers -- the `1` of `Pct. 1`
    rides a point high and lands in a band of its own -- so a band holding no
    figures is not a row, it is a piece of the nearest row's label. Attaching it
    rather than emitting it is what keeps `Pct. 1` from arriving as two rows,
    one of which has no numbers at all.
    """
    anchors = column_anchors(page, lo, hi)
    if not anchors:
        return [], [], 0.0
    (reg0, reg1), (vot0, vot1) = anchors
    lab_end = min(reg0, vot0) - 4

    words = [w for w in page.get_text('words')
             if lo <= w[0] < hi
             and page.rect.height * TOP_FRAC <= w[1] <= page.rect.height * BOT_FRAC]
    if len(words) < 12:
        return [], [], 0.0

    ys = sorted({round(w[1], 1) for w in words})
    gaps = sorted(b - a for a, b in zip(ys, ys[1:]) if 1.5 < b - a < 40)
    rh = gaps[len(gaps) // 2] if gaps else 9.0
    tol = max(2.0, rh * 0.4)

    bands = []
    for w in sorted(words, key=lambda w: w[1]):
        if bands and w[1] - bands[-1][0] <= tol:
            bands[-1][1].append(w)
        else:
            bands.append((w[1], [w]))

    def figures(ws, x0, x1):
        got = [num(w[4]) for w in ws
               if x0 - 8 <= (w[0] + w[2]) / 2.0 <= x1 + 10
               and num(w[4]) is not None]
        return got[-1] if got else None

    # Which bands are real rows: the ones carrying a figure, plus any band that
    # states the town held no election (those legitimately have no numbers).
    keep = []
    for y, ws in bands:
        txt = ' '.join(w[4] for w in sorted(ws, key=lambda w: w[0]))
        has = (figures(ws, reg0, reg1) is not None
               or figures(ws, vot0, vot1) is not None)
        keep.append(has or bool(no_election(txt)))

    for i, (y, ws) in enumerate(bands):
        if keep[i]:
            continue
        # Give this fragment to the nearest real row, preferring the one below:
        # a label sits at the top of its entry more often than the bottom.
        best, bd = None, 1e9
        for j, k in enumerate(keep):
            if not k:
                continue
            d = abs(bands[j][0] - y) - (0.6 if bands[j][0] > y else 0.0)
            if d < bd:
                best, bd = j, d
        if best is not None and bd <= rh * 1.6:
            bands[best][1].extend(ws)

    rows = []
    for i, (y, ws) in enumerate(bands):
        if not keep[i]:
            continue
        ws = sorted(ws, key=lambda w: w[0])
        label = ' '.join(w[4] for w in ws if w[0] < lab_end)
        # THE DATE IS ITS OWN PRINTED COLUMN and it sits between the name and
        # the figures, so it lands inside the label span. Left there it makes
        # `Abington May`, which is not a Massachusetts town and snaps to
        # nothing: the town is read perfectly and then thrown away unnamed. Cut
        # it out of the name and keep it in the row text, where DATE still
        # finds it.
        held = ''
        md = DATE.search(label) or re.search(
            r'\b(%s)' % '|'.join(m[:3] for m in MONTHS), label, re.I)
        if md and md.start() > 0:
            held, label = label[md.start():], label[:md.start()]
        reg = figures(ws, reg0, reg1)
        vot = figures(ws, vot0, vot1)
        mid = ' '.join(w[4] for w in ws if lab_end <= w[0] < reg0 - 8)
        mid = (held + ' ' + mid).strip()
        joined = ' '.join(p for p in (label, mid,
                                      '' if reg is None else str(reg),
                                      '' if vot is None else str(vot)) if p)
        figs = [x for x in (reg, vot) if x is not None]
        rows.append({'label': delead(label), 'figs': figs, 'joined': joined,
                     'band': (lo, y, hi, y + rh),
                     'cols': {'reg': reg, 'voted': vot}})
    # The label column still supplies a name where the row's own label is short.
    # No skew correction: these are the page's true coordinates, not a grid's.
    return rows, label_lines(page, lo, lo + label_w(page)), 0.0


def _bands_plausible(bands, width):
    """Do these look like two columns of figures, or like a heading?

    A figure column is narrow and sits in the right-hand half; the names need
    most of the left. A band a third of the page wide starting at x=80 is the
    heading being mistaken for a column, and accepting it leaves no label
    column at all.
    """
    try:
        (r0, r1), (v0, v1) = bands
    except (TypeError, ValueError):
        return False
    if min(r0, v0) < width * 0.30:
        return False                      # nothing left for the names
    for a, b in ((r0, r1), (v0, v1)):
        if not (0 < b - a < width * 0.35):
            return False
    return True


def ocr_bands_from_numbers(img, minconf=25):
    """Locate the two figure columns from the figures, not from the heading.

    The heading is one line and may be illegible; the figures are a hundred
    lines and are the thing being looked for anyway. Their x positions fall into
    tight clusters, one per column, so the columns can be read off the page
    without anything having to be spelled correctly.
    """
    toks = [t for t in _ocr_tokens(img, digits=True, minconf=minconf)
            if num(t[2]) is not None]
    xs = sorted(t[0] for t in toks)
    if len(xs) < 8:
        return None

    # CLUSTER, AND TAKE THE TWO RIGHTMOST. Splitting at the widest gap is wrong,
    # because the widest gap on these pages is between the PRECINCT NUMBERS in
    # the label column and the figures -- `Pct. 1, 2, 3` are numbers too. That
    # split called the precinct labels the registered column. The figure columns
    # are always the last two clusters on the line, whatever else is numeric.
    sep = max(25, img.width * 0.05)
    groups = [[xs[0]]]
    for x in xs[1:]:
        if x - groups[-1][-1] > sep:
            groups.append([x])
        else:
            groups[-1].append(x)
    groups = [g for g in groups if len(g) >= 4]
    if len(groups) < 2:
        return None
    left, right = groups[-2], groups[-1]
    pad = max(6, img.width * 0.02)
    return ((max(0, min(left) - pad), max(left) + pad),
            (max(0, min(right) - pad), max(right) + pad))


def rows_from_ocr(page, lo, hi):
    """Rows from Tesseract, for a page with no usable text layer.

    EACH COLUMN IS CROPPED AND READ ON ITS OWN.

    Reading the whole block and then deciding which column each token fell in
    leaves every token free to land in the wrong one, and on a soft scan they
    do. Cropping the registered column and reading only that means a figure
    CANNOT arrive as a turnout: there is nothing else in the picture.

    It also lets each column be read on its own terms. The label column holds
    words and wants the whole alphabet; the figure columns hold nothing but
    digits and commas and want to be told so. One pass cannot do both, and the
    single pass is why a 1973 page returned `5006060010000000` for a count.
    Read this way the same page returns 16,535 / 11,387, 1,695 / 1,167,
    1,299 / 856 -- every figure exactly as printed, in a volume that had been
    yielding nothing at all.

    The columns are found from the heading, which is read once at the top of the
    block, so nothing here assumes where they are.
    """
    from PIL import Image
    clip = pymupdf.Rect(lo, page.rect.height * TOP_FRAC,
                        hi, page.rect.height * BOT_FRAC)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(OCR_ZOOM, OCR_ZOOM), clip=clip)
    img = Image.open(io.BytesIO(pix.tobytes('png')))

    bands = ocr_column_bands(img)
    # THE HEADING IS NOT ALWAYS READABLE, AND A BAD BAND IS WORSE THAN NONE.
    # On the image-only pages of 1986 the heading OCRs into nothing usable and
    # the registered column comes back as x 80-402 of a 668-wide block -- the
    # width of the heading text, not of a column of numbers. The label column is
    # then 70px of margin, so not one town name is read, and a page whose 84
    # rows of figures OCR perfectly yields no towns at all: figures with no
    # names to hang them on. That is most of what was missing from the older
    # volumes.
    #
    # So a band is checked for plausibility and, failing that, the columns are
    # taken from where the numbers actually are, which needs no heading.
    if not bands or not _bands_plausible(bands, img.width):
        bands = ocr_bands_from_numbers(img)
    if not bands:
        return [], [], 0.0
    (reg0, reg1), (vot0, vot1) = bands
    label_end = max(0, min(reg0, vot0) - 10)

    labels = _ocr_tokens(img.crop((0, 0, int(label_end), img.height)),
                         minconf=25)
    regs = _ocr_tokens(img.crop((max(0, int(reg0) - 20), 0,
                                 min(img.width, int(vot0) - 10), img.height)),
                       digits=True, minconf=25)
    vots = _ocr_tokens(img.crop((max(0, int(vot0) - 10), 0,
                                 img.width, img.height)),
                       digits=True, minconf=25)

    regs = [(x, y, t) for x, y, t in regs if num(t) is not None]
    vots = [(x, y, t) for x, y, t in vots if num(t) is not None]

    # A printed row is a registered figure and whatever sits level with it.
    def nearest(items, y, tol):
        best = None
        for it in items:
            d = abs(it[1] - y)
            if d <= tol and (best is None or d < best[0]):
                best = (d, it)
        return best[1] if best else None

    tol = 9 * OCR_ZOOM
    out, used = [], set()
    for x, y, t in sorted(regs, key=lambda r: r[1]):
        v = nearest(vots, y, tol)
        lab = nearest([l for l in labels if id(l) not in used], y, tol)
        if lab:
            used.add(id(lab))
        joined = ' '.join(p for p in (lab[2] if lab else '', t,
                                      v[2] if v else '') if p)
        out.append({'label': delead(lab[2]) if lab else '',
                    'figs': [x for x in (num(t), num(v[2]) if v else None)
                             if x is not None],
                    'joined': joined,
                    'band': (0, y, 0, y),
                    'cols': {'reg': num(t), 'voted': num(v[2]) if v else None}})

    # The label column also carries the town names and dates, which have no
    # figure beside them and would otherwise never be seen.
    for lx, ly, lt in labels:
        if id((lx, ly, lt)) in used:
            continue
        if DATE.search(lt) or TOWN.match(delead(lt) or ''):
            out.append({'label': delead(lt), 'figs': [], 'joined': lt,
                        'band': (0, ly, 0, ly), 'cols': None})
    out.sort(key=lambda r: r['band'][1])
    return out, [], 0.0


def parse_block_with(page, lo, hi, year, force_ocr=False, names=None,
                     source='words'):
    """One column block -> a list of municipalities, using one row reader."""
    rows, labels, off = [], [], 0.0
    if not force_ocr:
        if source == 'words':
            rows, labels, off = rows_from_words(page, lo, hi)
        if len(rows) < 6:
            rows, labels, off = rows_from_cells(page, lo, hi)
    used_ocr = False
    # A page with almost no text is a scan nobody ran OCR over. It is not a hard
    # page to parse; there is simply nothing on it to parse, and half the 2000
    # volume is like that.
    #
    # A FIGURE-STARVED PAGE IS THE SAME CASE WEARING A DISGUISE. Several volumes
    # carry a text layer that holds every label and almost none of the numbers:
    # 1994 page 20 names nine towns and their fifty-three precincts, then stops
    # dead after nine figures. There is plenty of text, so no row-count test
    # fires, and the page is parsed confidently into towns with nothing in them.
    # Measuring the figures against the labels catches it; measuring the text
    # does not.
    starved = (not force_ocr and labels and len(labels) >= 12
               and len(rows) < 0.45 * len(labels))
    if force_ocr or len(rows) < 6 or starved:
        try:
            rows, labels, off = rows_from_ocr(page, lo, hi)
            used_ocr = True
        except Exception as exc:
            print('   [ocr failed] %s' % exc)
            OCR_FAILURES.append(str(exc))
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
            cur['name_how'] = how if name else 'unresolved'
            if no_election(joined):
                cur['no_election'] = True
                continue
            # A HEADING ROW WITHOUT A READABLE DATE STILL CARRIES ITS FIGURES.
            #
            # This used to skip the row outright, which created the town and
            # threw away its numbers -- and in the older layout the town's TOTAL
            # is printed on that very row. Reading each column separately puts
            # the date in the label band where it may not parse, so `Leominster
            # Nov. 6 16,535 11,387` opened a town called Leominster holding
            # nothing at all. Every city in the 1973 volume went that way.
            mon = next((x for x in MONTHS
                        if m and x.lower().startswith(m.group(1).lower()[:3])),
                       None)
            if mon and m:
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


def block_score(towns):
    """How much of this reading actually closes its own arithmetic.

    The count of towns whose precincts sum to both printed totals, with
    undivided towns -- which have nothing to cross-foot -- counted as half, so a
    reader is not rewarded for reducing a page to a list of single figures.
    """
    n = 0.0
    for t in towns:
        pcs = t.get('precincts') or []
        reg, vot = t.get('reg'), t.get('voted')
        if not pcs:
            if reg is not None:
                n += 0.5
            continue
        sr = sum(p['reg'] for p in pcs if p.get('reg') is not None)
        sv = sum(p['voted'] for p in pcs if p.get('voted') is not None)
        if reg is not None and sr == reg and (vot is None or sv == vot):
            n += 1.0
        elif reg is not None and sr == reg:
            n += 0.75
    return n


def parse_block(page, lo, hi, year, force_ocr=False, names=None):
    """One column block -> a list of municipalities.

    NEITHER ROW READER WINS EVERYWHERE, so the block picks between them on the
    evidence instead of on a preference. The words layer rescues the volumes
    whose table detection collapses -- 1996 goes 51.6 to 77.2% on it -- and
    wrecks the volumes where detection was working: preferring it outright took
    2012 from 99.3 to 77.7% and 2006 from 91.9 to 61.4%.

    What separates them is the arithmetic, which is the one judge that needs no
    outside knowledge: precincts sum to the total or they do not. So both are
    run and the better-closing reading is kept. That is the same test used to
    choose a column split, applied a level up.
    """
    best, best_score = None, None
    for src in ('words', 'cells'):
        got = parse_block_with(page, lo, hi, year, force_ocr=force_ocr,
                               names=names, source=src)
        s = block_score(got[0])
        if best_score is None or s > best_score:
            best, best_score = got, s
        if force_ocr:
            break          # OCR ignores the source; running it twice is waste.
        # A READING THAT ALREADY CLOSES DOES NOT NEED A RIVAL. Where nearly
        # every municipality on the block sums to its own total there is nothing
        # for the second reader to win, and running it anyway doubles the cost
        # of the volumes that were never the problem.
        towns = got[0]
        if towns and s >= 0.9 * len(towns):
            break
    return best


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
    nameset = set(names)
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
    # Only pages that really have two blocks contribute a gutter reading.
    splits = []
    for i in pages:
        hm = page_blocks(doc[i])
        if hm is not None and len(hm) == 1:
            continue
        v = block_split(doc[i])
        if v:
            splits.append(v)
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
        # THE HEADINGS SAY HOW MANY BLOCKS; THE WHITESPACE SAYS WHERE THE GAP IS.
        #
        # Each signal is good at one of those and bad at the other. The heading
        # count is exact -- a block is a table with its own `Registered Voters`
        # printed over it -- but the midpoint between two heading groups sits
        # well right of the real gutter: 302 on a 2008 page whose gutter is at
        # 260, which would file the right block's town column under the left
        # block. The whitespace gap lands on the gutter accurately and invents
        # one where there is none, cutting the single-column 1973 table in half
        # so that neither half could see both of its columns.
        howmany = page_blocks(page)
        own = block_split(page)
        if howmany is not None and len(howmany) == 1:
            own = None                      # one column, whatever the gap says
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

    # THE ALPHABET SETTLES WHAT THE LABEL COLUMN LOST. Done before merging,
    # because merging is by name and a stub merges with the wrong town.
    resolve_by_order(rows, names)

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

    # What the table names, against what came out of it.
    _named = named_in(doc, pages, names) if names else set()
    _have = {t['municipality'] for t in merged.values()}
    missing_names = sorted(n for n in _named if n not in _have)
    unnamed_rows = [t for t in merged.values()
                    if names and t['municipality'] not in set(names)]

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
            # A ROW WHOSE NAME IS NOT A MASSACHUSETTS MUNICIPALITY IS NOT A
            # TOWN, whatever its arithmetic says. `By-The-Sea` is the tail of
            # Manchester-by-the-Sea and `UNKNOWN` is a name the label column
            # lost; both carried real figures and both were being counted as
            # towns. Emitting them as data puts a figure under a name that does
            # not exist, and nothing downstream can tell that from a real one.
            if names and t['municipality'] not in nameset:
                # THE VOLUME NAMES IT EVEN WHERE THE LABEL COLUMN LOST IT.
                # `named` is every municipality printed anywhere in this table.
                # If exactly one of them has no row and exactly one row has no
                # name, they are each other -- Marblehead, whose 15,002
                # registered voters were sitting under `UNKNOWN`.
                fits = list(missing_names)
                if len(fits) > 1 and t.get('reg'):
                    # A TOWN OF TWO HUNDRED PEOPLE DOES NOT HAVE FIFTEEN
                    # THOUSAND REGISTERED VOTERS. Where more than one name is
                    # missing, size says which of them this row is: New Ashford,
                    # which the volume records as failing to respond, cannot be
                    # a row carrying 15,002 registered voters. Marblehead can.
                    fits = [n for n in fits
                            if pop.get(n.lower(), 0) >= t['reg'] * 0.7]
                if len(unnamed_rows) == 1 and len(fits) == 1:
                    t['municipality'] = fits[0]
                    t['name_how'] = 'by elimination'
                    st, note = check(t)
                    note += ('; the label column lost this name, and it is the '
                             'only municipality the table names without a row')
            if names and t['municipality'] not in nameset:
                st = 'unnamed'
                note = ('the label column did not yield a municipality name; '
                        'read as %r' % t['municipality'])
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
    # A PAGE THAT NEEDED OCR AND DID NOT GET IT IS NOT A GAP, IT IS A LIE.
    # These volumes are half image: five of the eleven pages of the 1986 town
    # table carry nothing but a running head. When Tesseract could not be
    # started -- the Windows installer leaves it off PATH -- every one of those
    # pages produced nothing, and the run still printed a completion figure of
    # 73.3%. The towns were not hard to read; they were never looked at.
    if OCR_FAILURES:
        print('\n!! %d PAGES NEEDED OCR AND FAILED: %s'
              % (len(OCR_FAILURES), OCR_FAILURES[0]))
        print('!! Those pages contributed NOTHING. Coverage above is overstated')
        print('!! and whole runs of municipalities are missing from the output.')
        if not _find_tesseract():
            print('!! Tesseract was not found. Install it, or put it on PATH:')
            print('!!   C:\\Program Files\\Tesseract-OCR\\tesseract.exe')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
