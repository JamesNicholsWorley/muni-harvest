"""Check a new reading of PD43 against the old one, town by town.

A COVERAGE FIGURE IS NOT A CORRECTNESS FIGURE. A reader that produced twice as
many rows by reading them twice as badly would score better on every count in
this project, and nothing already written would notice. The two readers here
share no code path -- one keys the table on its labels and one on its arithmetic
-- so where they independently produce the same two numbers for the same town,
that is real evidence about the figures. Where they disagree, one of them is
wrong and the page has to be opened.

    python tools/pd43_agree.py pd43/arith-1986.csv pd43/out-1986.csv
"""
import argparse
import collections
import csv
import io
import sys


def num(x):
    try:
        return int(str(x).replace(',', '').strip())
    except (TypeError, ValueError):
        return None


def load_new(path):
    out = {}
    for r in csv.DictReader(io.open(path, encoding='utf-8')):
        if r.get('municipality'):
            out[r['municipality']] = (num(r['registered']), num(r['voted']))
    return out


def load_old(path):
    out = {}
    for r in csv.DictReader(io.open(path, encoding='utf-8')):
        if r.get('level') == 'total' and r.get('municipality'):
            out[r['municipality']] = (num(r['registered']), num(r['voted']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('new')
    ap.add_argument('old')
    ap.add_argument('--show', type=int, default=12)
    a = ap.parse_args()
    new, old = load_new(a.new), load_old(a.old)
    both = sorted(set(new) & set(old))
    agree = [m for m in both if new[m] == old[m]]
    reg_only = [m for m in both
                if new[m] != old[m] and new[m][0] == old[m][0]]
    differ = [m for m in both if new[m] != old[m] and new[m][0] != old[m][0]]

    print('%d towns in the new reading, %d in the old, %d in both'
          % (len(new), len(old), len(both)))
    if both:
        print('  both figures identical : %4d  (%.1f%% of the overlap)'
              % (len(agree), 100.0 * len(agree) / len(both)))
        print('  registration agrees    : %4d' % len(reg_only))
        print('  disagree               : %4d' % len(differ))
    print('  only in the new reading: %4d' % len(set(new) - set(old)))
    print('  only in the old reading: %4d' % len(set(old) - set(new)))
    for m in differ[:a.show]:
        print('    %-24s new %-16s old %s' % (m, new[m], old[m]))
    lost = sorted(set(old) - set(new))[:a.show]
    if lost:
        print('  lost: %s' % ', '.join(lost))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
