"""Per-volume summary: what we read, against what the volume says it holds.

Every other measure in this project is relative -- how many names we found
against how many we could see -- and none of them can say whether the FIGURES
are right. Each volume prints its own statewide totals on a summary page near
the front:

    Town Elections   300 Towns   Registered Voters 2,070,956   People Who Voted 447,904

That is absolute, and it is the only check here that catches an OVER-count. A
reading that invents figures and a reading that is correct look identical to
every other test in this file.

    python tools/pd43_report.py
"""
import collections
import csv
import glob
import io
import os
import re

import pymupdf

pymupdf.TOOLS.mupdf_display_errors(False)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

USABLE = ('checked', 'single', 'derived')


def stated(path):
    """The volume's own statewide town-election totals, if it prints them."""
    try:
        doc = pymupdf.open(path)
    except Exception:
        return {}
    for page in doc[:40]:
        t = ' '.join(page.get_text().split())
        m = re.search(r'Town\s+Elections?\s+(\d{2,3})\s+Towns?\s+'
                      r'Registered\s+Voters\s+([\d,]+)\s+'
                      r'People\s+Who\s+Voted\s+([\d,]+)', t, re.I)
        if m:
            return {'towns': int(m.group(1)),
                    'reg': int(m.group(2).replace(',', '')),
                    'voted': int(m.group(3).replace(',', ''))}
    return {}


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, 'pd43', 'out-*.csv'))):
        year = os.path.basename(path)[4:-4]
        recs = [r for r in csv.DictReader(io.open(path, encoding='utf-8'))]
        tot = [r for r in recs if r['level'] == 'total']
        if not tot:
            continue
        held = [r for r in tot if r['status'] != 'no_election']
        st = collections.Counter(r['status'] for r in tot)
        usable = sum(st[k] for k in USABLE)
        reg = sum(int(r['registered']) for r in held if r['registered'])
        vot = sum(int(r['voted']) for r in held if r['voted'])
        said = stated(os.path.join(ROOT, 'pd43', 'pd43-%s.pdf' % year))
        rows.append({
            'year': year, 'towns': len(held), 'municipalities': len(tot),
            'usable': usable, 'checked': st['checked'], 'single': st['single'],
            'derived': st['derived'], 'noelect': st['no_election'],
            'failed': len(tot) - usable - st['no_election'],
            'precincts': sum(1 for r in recs if r['level'] == 'precinct'),
            'dates': sum(1 for r in tot if r['date']),
            'reg': reg, 'voted': vot,
            'said_towns': said.get('towns'), 'said_reg': said.get('reg'),
            'said_voted': said.get('voted'),
        })

    print('PD43 volumes read: %d\n' % len(rows))
    print('%-6s %6s %7s %7s %9s %7s   %s'
          % ('year', 'towns', 'usable', 'pcts', 'dates', 'failed',
             'against the volume\'s own summary'))
    print('-' * 92)
    for r in rows:
        if r['said_reg']:
            cmp_ = ('reg %6.1f%%  voted %6.1f%%  towns %d/%d'
                    % (100.0 * r['reg'] / r['said_reg'],
                       100.0 * r['voted'] / max(1, r['said_voted']),
                       r['towns'], r['said_towns']))
        else:
            cmp_ = '(volume prints no summary total)'
        print('%-6s %6d %7d %7d %9d %7d   %s'
              % (r['year'], r['towns'], r['usable'], r['precincts'],
                 r['dates'], r['failed'], cmp_))

    print('\n%-6s %8s %8s %8s %8s %8s'
          % ('year', 'checked', 'single', 'derived', 'noelect', 'failed'))
    print('-' * 52)
    for r in rows:
        print('%-6s %8d %8d %8d %8d %8d'
              % (r['year'], r['checked'], r['single'], r['derived'],
                 r['noelect'], r['failed']))

    print('\nTOTALS across %d volumes' % len(rows))
    print('   town-year rows      %8d' % sum(r['municipalities'] for r in rows))
    print('   precinct rows       %8d' % sum(r['precincts'] for r in rows))
    print('   usable denominators %8d' % sum(r['usable'] for r in rows))
    print('   election dates      %8d' % sum(r['dates'] for r in rows))
    print('   registered voters   %8s'
          % format(sum(r['reg'] for r in rows), ','))
    print('   ballots cast        %8s'
          % format(sum(r['voted'] for r in rows), ','))


if __name__ == '__main__':
    main()
