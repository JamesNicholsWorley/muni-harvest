"""Cut a page into column zones before reading rows.

A return printed as two or three races side by side defeats every reader that
walks the page in reading order. Cluster the words by y and a row picks up
candidates from two different contests; take the PDF's own text and the columns
interleave. Either way the output is a fused race, and fusion is the one error
the ballot arithmetic can never see: if block A closes at ballots x k1 and B at
ballots x k2, A+B closes at ballots x (k1+k2) exactly.

Geometry settles it where reading order cannot. Races set side by side are
separated by a gutter of whitespace running the full height of the content;
inside a race, no such gutter exists, because every row spans the block. So find
the full-height gutters, cut there, and read each zone on its own. A row then
cannot span two races, and it is the layout that says so rather than a model.
"""
import statistics

MIN_GUTTER = 11.0   # pt. Narrower than this is inter-column spacing in one table.
COVER = 0.72        # a gutter must be clear over this share of the content height
BIN = 2.0


def _rows(words, tol=3.0):
    words = sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    out, cur, ym = [], [], None
    for w in words:
        y = (w[1] + w[3]) / 2
        if ym is None or abs(y - ym) <= tol:
            cur.append(w)
            ym = y if ym is None else ym
        else:
            out.append(cur); cur = [w]; ym = y
    if cur:
        out.append(cur)
    return out


def gutters(words, page_width):
    """x-ranges that no word crosses over most of the content's height."""
    if len(words) < 25:
        return []
    ys = [w[1] for w in words] + [w[3] for w in words]
    top, bot = min(ys), max(ys)
    height = bot - top
    if height <= 0:
        return []
    nb = int(page_width / BIN) + 1
    # For each x bin, the share of the content height that some word occupies.
    rowsets = [set() for _ in range(nb)]
    for w in words:
        a, b = int(w[0] / BIN), min(int(w[2] / BIN) + 1, nb)
        lo, hi = int((w[1] - top) / 6), int((w[3] - top) / 6) + 1
        for i in range(a, b):
            rowsets[i].update(range(lo, hi))
    bands = max(1, int(height / 6))
    clear = [len(s) / bands < (1 - COVER) for s in rowsets]
    out, run = [], None
    for i, c in enumerate(clear):
        if c and run is None:
            run = i
        elif not c and run is not None:
            if (i - run) * BIN >= MIN_GUTTER:
                out.append((run * BIN, i * BIN))
            run = None
    return out


def _standalone(words):
    """Does this slice hold a race of its own -- names AND figures?

    The test that decides whether a gutter is worth cutting at. A wide precinct
    table is full of full-height gutters, one between every pair of number
    columns, and cutting at those severs each candidate from their own votes.
    What separates a gutter between RACES from a gutter between COLUMNS is that
    only the first has names on both sides.
    """
    names = sum(1 for w in words
                if len(w[4]) >= 3 and any(c.isalpha() for c in w[4]))
    figs = sum(1 for w in words if w[4].isdigit())
    return names >= 4 and figs >= 3


def zone_text(page):
    """Page text, read zone by zone, each zone row by row.

    Falls back to one zone -- which is ordinary row clustering -- whenever the
    page has no full-height gutter, which is the common case.
    """
    words = page.get_text("words")
    if not words:
        return "", 1
    cuts = [g for g in gutters(words, page.rect.width)]
    edges = [0.0] + [(a + b) / 2 for a, b in cuts] + [page.rect.width]
    slices = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        slices.append([w for w in words if lo <= (w[0] + w[2]) / 2 < hi])
    # Merge left to right: a slice that is not a race in its own right belongs
    # to the one before it. A precinct table collapses back to a single zone;
    # two races side by side stay two.
    zones = []
    for sl in slices:
        if zones and not _standalone(sl):
            zones[-1].extend(sl)
        elif _standalone(sl):
            zones.append(sl)
        elif sl:
            zones.append(sl)
    zones = [z for z in zones if len(z) >= 12] or [words]
    parts = []
    for z in zones:
        for r in _rows(z):
            parts.append(" ".join(w[4] for w in sorted(r, key=lambda w: w[0])))
    return "\n".join(parts), len(zones)


def _intact(text):
    """Rows that survived with a name and a figure still on the same line."""
    n = 0
    for line in text.splitlines():
        toks = line.split()
        if (any(len(t) >= 3 and any(c.isalpha() for c in t) for t in toks)
                and any(t.isdigit() for t in toks)):
            n += 1
    return n


def best_text(page):
    """The reading that keeps the most rows intact, and which one it was.

    Zoning wins on most pages and loses on a few: Gill 2006 has a full-height
    gutter that is not a race boundary, and cutting there drops it from 71% of
    rows intact to 14%. There is no need to predict which case a page is --
    both readings are free, the count of surviving rows is not a matter of
    opinion, and the loser is discarded. What must not happen is a silent
    choice, so the caller is told which reading it got.
    """
    z, nz = zone_text(page)
    raw = page.get_text()
    return (z, "zoned", nz) if _intact(z) >= _intact(raw) else (raw, "raw", 1)
