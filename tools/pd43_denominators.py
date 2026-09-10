"""Merge the PD43 registration figures into config/denominators.csv.

WHAT THE SITE ALREADY USES. `config/denominators.csv` is one row per
municipality per year -- municipality, year, election_date, registered, basis --
and it is what `build_mvp.py` turns into the map's turnout. Today it holds
2021-2026 only, and every row of it is INTERPOLATED: the Secretary publishes a
handful of statewide enrollment snapshots and the figure for an election in April
is estimated between the two either side of it.

WHAT PD43 ADDS IS BETTER THAN WHAT IS THERE. Its figures are not interpolated.
The volume prints the registered voters as they stood at that town's own
election, on that town's own date. So the pre-2021 rows this writes carry
`basis: pd43_printed`, which outranks `interpolated` on the two occasions it
matters: when the same town-year arrives from both, and when somebody wants to
know how much the number can be leaned on.

WHAT IS REFUSED. Only `checked` and `single` rows become denominators.
`checked` means the precincts sum to both printed totals; `single` is an
undivided town with one printed figure and nothing to cross-foot. A `mismatch`
or a `no_total` is a figure this project could not confirm, and a turnout
computed from an unconfirmed denominator is worse than no turnout at all --
it looks exactly like a real one.

    python tools/pd43_denominators.py --dry-run
    python tools/pd43_denominators.py --apply
"""
import argparse
import collections
import csv
import io
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DENOM = os.path.join(ROOT, 'config', 'denominators.csv')
PD43 = os.path.join(ROOT, 'config', 'pd43_turnout.csv')
FIELDS = ['municipality', 'year', 'election_date', 'registered', 'basis']
USABLE = ('checked', 'single')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--denominators', default=DENOM)
    ap.add_argument('--pd43', default=PD43)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    have = list(csv.DictReader(io.open(a.denominators, encoding='utf-8')))
    seen = {(r['municipality'].lower(), r['year']) for r in have}
    print('%s: %d rows, %s-%s'
          % (os.path.basename(a.denominators), len(have),
             min(r['year'] for r in have), max(r['year'] for r in have)))

    add, skipped, conflict = [], collections.Counter(), 0
    for r in csv.DictReader(io.open(a.pd43, encoding='utf-8')):
        if r['level'] != 'total':
            continue
        if r['status'] not in USABLE:
            skipped[r['status']] += 1
            continue
        if not r['registered']:
            skipped['no figure'] += 1
            continue
        key = (r['municipality'].lower(), r['year'])
        if key in seen:
            # The modern file already has this town-year. PD43's figure is
            # printed where that one is interpolated, but overwriting a row the
            # site is already serving is not this script's call to make.
            conflict += 1
            continue
        add.append({'municipality': r['municipality'], 'year': r['year'],
                    'election_date': r['date'], 'registered': r['registered'],
                    'basis': 'pd43_printed'})
        seen.add(key)

    per = collections.Counter(r['year'] for r in add)
    print('\nPD43 offers %d new town-year denominators' % len(add))
    print('  by year: %s' % ', '.join('%s:%d' % (y, per[y]) for y in sorted(per)))
    print('  refused: %s'
          % ', '.join('%s %d' % (k, v) for k, v in skipped.most_common()))
    if conflict:
        print('  %d town-years already in the file and left alone' % conflict)

    dated = sum(1 for r in add if r['election_date'])
    print('  %d of the new rows carry the election date the volume printed'
          % dated)

    if not a.apply:
        print('\nDRY RUN. Nothing written. Pass --apply.')
        return

    shutil.copyfile(a.denominators, a.denominators + '.bak')
    rows = have + add
    rows.sort(key=lambda r: (r['municipality'], r['year']))
    with io.open(a.denominators, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in FIELDS})
    print('\nwrote %s: %d rows (%d added). Previous kept as .bak'
          % (a.denominators, len(rows), len(add)))


if __name__ == '__main__':
    main()
