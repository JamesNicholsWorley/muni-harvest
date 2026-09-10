"""Combine the per-volume PD43 readings into one series, and report coverage.

    python tools/pd43_combine.py pd43/out-*.csv --out config/pd43_turnout.csv
"""
import argparse
import collections
import csv
import glob
import io
import os

# Only these two verdicts are trustworthy enough to become a denominator.
# `checked` closed its own arithmetic; `single` is an undivided town with one
# printed figure and nothing to cross-foot. Everything else is kept in the file
# and marked, so a gap is documented rather than silently filled.
USABLE = ('checked', 'single')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csvs', nargs='+')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    paths = []
    for pat in a.csvs:
        paths += sorted(glob.glob(pat))
    rows = []
    for p in paths:
        with io.open(p, encoding='utf-8', newline='') as fh:
            rows += list(csv.DictReader(fh))
    if not rows:
        print('nothing to combine')
        return 1

    with io.open(a.out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x['year'], x['municipality'],
                                             x['level'] != 'total',
                                             str(x['precinct']).zfill(3))):
            w.writerow(r)

    totals = [r for r in rows if r['level'] == 'total']
    pcts = [r for r in rows if r['level'] == 'precinct']
    usable = [r for r in totals if r['status'] in USABLE and r['registered']]
    dated = [r for r in totals if r['date']]
    noelect = [r for r in totals if r['status'] == 'no_election']
    by_ocr = [r for r in totals if r.get('read_by') == 'ocr']

    print('%d volumes -> %s' % (len(paths), a.out))
    print('  %6d town-year rows' % len(totals))
    print('  %6d precinct rows' % len(pcts))
    print('  %6d with a usable registered-voter figure (%.0f%%)'
          % (len(usable), 100.0 * len(usable) / max(1, len(totals))))
    print('  %6d with an election date' % len(dated))
    print('  %6d stated as holding no election that year' % len(noelect))
    print('  %6d read by OCR rather than a text layer' % len(by_ocr))

    st = collections.Counter(r['status'] for r in totals)
    print('\n  status:')
    for k, n in st.most_common():
        print('    %-12s %5d' % (k, n))

    print('\n  by year:')
    per = collections.defaultdict(lambda: [0, 0, 0])
    for r in totals:
        per[r['year']][0] += 1
        if r['status'] in USABLE and r['registered']:
            per[r['year']][1] += 1
        if r['date']:
            per[r['year']][2] += 1
    print('    %-6s %6s %8s %7s' % ('year', 'towns', 'usable', 'dated'))
    for y in sorted(per):
        n, u, d = per[y]
        print('    %-6s %6d %8d %7d' % (y, n, u, d))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
