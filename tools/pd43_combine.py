"""Combine the two readings of PD43 into one corpus, and say which one spoke.

NEITHER READER WINS EVERYWHERE and the difference is not small. The
arithmetic-first reader takes 1986 from 51.5% to 92.8% and 1990 from 67.2% to
93.1%; the label-first reader still beats it on 2008 and 2012. They share no
code path -- one keys the table on its labels, the other on its arithmetic -- so
a town only one of them found is a town genuinely recovered, and a town both
found with the same two figures is a figure confirmed twice over.

The order of preference is evidential, not a ranking of the readers:

1. A reading whose precincts sum to its own printed total. That is the only
   statement here that is self-checking, and it comes from the arithmetic
   reader by construction.
2. The arithmetic reader's unclosed reading, which is still keyed on structure.
3. The label-first reader, where it passed its own checks.

Where both readers produce a town and disagree about its figures, NEITHER is
written as fact. The row is kept, flagged, and listed for someone to open the
page -- a check has never yet been a good enough reason to change a figure in
this corpus, and it is not one here either.

    python tools/pd43_combine.py --out pd43/pd43-turnout.csv
"""
import argparse
import collections
import csv
import glob
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.pd43_scope import SECTIONS                             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_OK = ('checked', 'single', 'derived')


def num(x):
    try:
        return int(str(x).replace(',', '').strip())
    except (TypeError, ValueError):
        return None


def read_arith(path):
    for r in csv.DictReader(io.open(path, encoding='utf-8')):
        if not r.get('municipality'):
            continue
        yield {'year': int(r['year']), 'volume': r['volume'],
               'municipality': r['municipality'],
               'registered': num(r['registered']), 'voted': num(r['voted']),
               'precincts': num(r['precincts']) or 0,
               'closed': r['arithmetic_closes'] == '1',
               'reader': 'arithmetic', 'page': r['page'],
               'evidence': ('precincts sum to the printed total'
                            if r['arithmetic_closes'] == '1'
                            else 'structure from the figure columns')}


def read_old(path, year, volume):
    for r in csv.DictReader(io.open(path, encoding='utf-8')):
        if r.get('level') != 'total' or not r.get('municipality'):
            continue
        if r.get('status') not in OLD_OK:
            continue
        yield {'year': year, 'volume': volume,
               'municipality': r['municipality'],
               'registered': num(r['registered']), 'voted': num(r['voted']),
               'precincts': num(r.get('precincts')) or 0,
               'closed': r.get('status') == 'checked',
               'reader': 'labels', 'page': r.get('page', ''),
               'evidence': 'label-first reader, status %s' % r.get('status')}


_DEN = {}


def denominator(year):
    """How many towns held an election that year, per the volume that says so.

    Read from the volume's own front matter rather than assumed. `142 towns, one
    precinct each` plus `165 towns divided into 783 precincts` is 307 for 1986;
    the figure this project had been dividing by was 300, and it was never the
    same number two years running.
    """
    if not _DEN:
        import pymupdf
        from tools.pd43_scope import stated_counts
        pymupdf.TOOLS.mupdf_display_errors(False)
        for (vol, kind), s in SECTIONS.items():
            if kind != 'town':
                continue
            p = os.path.join(ROOT, 'pd43', 'pd43-%s.pdf' % vol)
            if not os.path.exists(p):
                continue
            doc = pymupdf.open(p)
            n = stated_counts(doc).get('towns')
            doc.close()
            if n:
                _DEN[int(s['year'])] = n
    return _DEN.get(int(year))


def rank(row):
    """Lower is better. See the module docstring for why this order."""
    if row['closed'] and row['reader'] == 'arithmetic':
        return 0
    if row['reader'] == 'arithmetic':
        return 1
    return 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'pd43',
                                                  'pd43-turnout.csv'))
    ap.add_argument('--conflicts', default=os.path.join(ROOT, 'pd43',
                                                        'pd43-conflicts.csv'))
    a = ap.parse_args()

    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'pd43', 'arith',
                                           'arith-*.csv'))):
        rows += list(read_arith(p))
    for p in sorted(glob.glob(os.path.join(ROOT, 'pd43', 'out-*.csv'))):
        vol = re.search(r'out-(\d{4})', os.path.basename(p)).group(1)
        # THE VOLUME IS NOT ALWAYS THE ELECTION YEAR. The 1982 volume tabulates
        # the 1980 town elections and says so on every page of the section.
        known = SECTIONS.get((vol, 'town'))
        year = int((known or {}).get('year') or vol)
        rows += list(read_old(p, year, vol))

    by = collections.defaultdict(list)
    for r in rows:
        by[(r['year'], r['municipality'])].append(r)

    out, conflicts = [], []
    for key in sorted(by):
        cands = sorted(by[key], key=rank)
        best = cands[0]
        others = [c for c in cands[1:]
                  if (c['registered'], c['voted'])
                  != (best['registered'], best['voted'])]
        agreed = [c for c in cands[1:]
                  if (c['registered'], c['voted'])
                  == (best['registered'], best['voted'])]
        best = dict(best)
        best['confirmed_by'] = 'both readers' if agreed else best['reader']
        best['disputed'] = int(bool(others))
        out.append(best)
        for c in others:
            conflicts.append({'year': key[0], 'municipality': key[1],
                              'kept_reader': best['reader'],
                              'kept_registered': best['registered'],
                              'kept_voted': best['voted'],
                              'other_reader': c['reader'],
                              'other_registered': c['registered'],
                              'other_voted': c['voted'],
                              'kept_because': best['evidence']})

    with io.open(a.out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=[
            'year', 'volume', 'municipality', 'registered', 'voted',
            'precincts', 'closed', 'reader', 'confirmed_by', 'disputed',
            'page', 'evidence'])
        w.writeheader()
        for r in out:
            w.writerow(r)
    with io.open(a.conflicts, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=[
            'year', 'municipality', 'kept_reader', 'kept_registered',
            'kept_voted', 'other_reader', 'other_registered', 'other_voted',
            'kept_because'])
        w.writeheader()
        for r in conflicts:
            w.writerow(r)

    print('%d town-years, %d disputed between the readers\n' % (len(out),
                                                                len(conflicts)))
    print('%-6s %-7s %-7s %-8s %-9s %s'
          % ('year', 'towns', 'stated', 'of them', 'confirmed', 'closes'))
    per = collections.Counter(r['year'] for r in out)
    short = []
    for y in sorted(per):
        stated = denominator(y)
        both = sum(1 for r in out
                   if r['year'] == y and r['confirmed_by'] == 'both readers')
        closed = sum(1 for r in out if r['year'] == y and r['closed'])
        pct = 100.0 * per[y] / stated if stated else 0.0
        if stated and pct < 90:
            short.append((y, pct))
        print('%-6s %-7d %-7s %7.1f%% %-9d %d'
              % (y, per[y], stated or '?', pct, both, closed))
    if short:
        print('\nstill under 90%%: %s'
              % ', '.join('%s (%.1f%%)' % s for s in short))
    print('\nwrote %s and %s' % (a.out, a.conflicts))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
