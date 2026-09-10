"""Check our own pre-2021 records against PD43, on the invariant that holds.

OUR FIGURE CAN BE LOWER. IT CANNOT BE HIGHER.

Ballots cast is not printed in an annual town report, so it is derived: the
votes in a contest, divided by the seats it fills. A contest that prints its
Blanks accounts for every mark on every ballot, so cast/seats lands exactly on
the number of people who voted. A contest that does not print Blanks is short by
the undervote, so cast/seats lands below it.

Either way it cannot exceed the number of ballots -- nobody can cast more marks
in a k-seat contest than k times the ballots handed out. So:

    ours <= PD43        expected, and exact where Blanks were printed
    ours >  PD43        one of the two readings is wrong, always

That asymmetry is the whole value of the comparison. It is also how the seats
bug was found: before it was fixed our figure was 2.00 or 3.00 times PD43's,
which is not a rounding difference, it is a contest with two or three seats.

    python tools/pd43_crosscheck.py --pd43 config/pd43_turnout.csv \\
        --records <civicatlasma>/json_pre2021
"""
import argparse
import csv
import glob
import io
import json
import os
import re

USABLE = ('checked', 'single')


def load_pd43(path):
    out = {}
    with io.open(path, encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            if r['level'] != 'total':
                continue
            key = (r['municipality'].lower(), r['year'])
            out[key] = r
    return out


def load_ours(d):
    """stem -> (municipality, year, ballots floor, date). Same derivation the
    published bundle uses, kept here rather than imported so this can run
    against the records alone."""
    out = []
    for f in sorted(glob.glob(os.path.join(d, '*.json'))):
        try:
            doc = json.load(io.open(f, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        els = doc.get('elections') or []
        if not els:
            continue
        muni = (els[0].get('municipality') or '').strip()
        date = els[0].get('date') or ''
        year = date[:4]
        if not (muni and year.isdigit()):
            continue
        peak = 0
        for e in els:
            cast = sum(c['votes'] for c in e.get('candidates') or []
                       if isinstance(c.get('votes'), int) and c['votes'] >= 0)
            seats = e.get('num_winners')
            seats = seats if isinstance(seats, int) and seats > 0 else 1
            peak = max(peak, -(-cast // seats))
        out.append((muni, year, peak, date))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pd43', default='config/pd43_turnout.csv')
    ap.add_argument('--records', required=True)
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    pd43 = load_pd43(a.pd43)
    ours = load_ours(a.records)
    print('PD43 town-year rows : %d' % len(pd43))
    print('our pre-2021 records: %d' % len(ours))

    rows, impossible, exact, low, undated = [], [], 0, 0, []
    for muni, year, peak, date in ours:
        p = pd43.get((muni.lower(), year))
        if not p or p['status'] not in USABLE or not p['voted']:
            continue
        v = int(p['voted'])
        reg = int(p['registered']) if p['registered'] else None
        rows.append((muni, year, peak, v, reg, date, p['date']))
        if peak > v:
            impossible.append((muni, year, peak, v, date, p['date']))
        elif peak == v:
            exact += 1
        else:
            low += 1
        if date and p['date'] and date != p['date']:
            undated.append((muni, year, date, p['date']))

    print('\noverlap: %d town-years' % len(rows))
    if rows:
        print('  ours exactly equals PD43   : %d (%.0f%%)  -- Blanks were printed'
              % (exact, 100.0 * exact / len(rows)))
        print('  ours below PD43            : %d (%.0f%%)  -- expected'
              % (low, 100.0 * low / len(rows)))
        print('  ours ABOVE PD43            : %d (%.0f%%)  -- impossible'
              % (len(impossible), 100.0 * len(impossible) / len(rows)))

    if impossible:
        print('\nimpossible, worst first -- one of the two readings is wrong:')
        for m, y, o, v, d1, d2 in sorted(
                impossible, key=lambda r: -(r[2] / max(1, r[3])))[:25]:
            note = '  dates differ (%s vs %s)' % (d1, d2) if d1 != d2 else ''
            print('  %-22s %s  ours=%-7d PD43=%-7d  x%.1f%s'
                  % (m, y, o, v, o / max(1, v), note))

    if undated:
        print('\n%d town-years where the two sources date the election '
              'differently:' % len(undated))
        for m, y, d1, d2 in undated[:15]:
            print('  %-22s %s  ours=%s  PD43=%s' % (m, y, d1, d2))

    gain = sum(1 for r in rows if r[4])
    print('\n%d town-years would gain a real registered-voter denominator' % gain)

    if a.out and rows:
        with io.open(a.out, 'w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['municipality', 'year', 'ours_ballots_floor',
                        'pd43_voted', 'pd43_registered', 'our_date',
                        'pd43_date', 'verdict'])
            for m, y, o, v, reg, d1, d2 in rows:
                w.writerow([m, y, o, v, reg if reg else '', d1, d2,
                            'impossible' if o > v else
                            'exact' if o == v else 'below'])
        print('wrote %s' % a.out)


if __name__ == '__main__':
    main()
