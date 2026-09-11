"""Assemble page-block transcriptions into town-years, and check the arithmetic.

A TOWN CAN STRADDLE A COLUMN BREAK, and no crop boundary avoids it. Belmont's
precincts are printed at the top of one column and its total at the foot of the
one before, so a reader given either block alone returns something that cannot
possibly sum -- precincts with no total, or a total with no precincts. That is
not a transcription error and must not be counted as one. It is fixed here, by
putting the halves back together before anything is checked.

    python tools/pd43_vision_merge.py scratchpad/haiku-*.csv --year 1986 \
        --out pd43/vision-1986.csv

The arithmetic is done HERE and never by the agent that read the page. An agent
asked whether its own figures add up has an obvious way to make them add up.
"""
import argparse
import collections
import csv
import glob
import io
import os


def num(x):
    s = str(x or '').replace(',', '').replace('.', '').strip()
    return int(s) if s.isdigit() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csvs', nargs='+')
    ap.add_argument('--year', default='')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    paths = []
    for pat in a.csvs:
        paths += sorted(glob.glob(pat))
    rows = []
    for p in paths:
        try:
            rows += [dict(r, _src=os.path.basename(p))
                     for r in csv.DictReader(io.open(p, encoding='utf-8'))]
        except Exception as exc:
            print('  [skipped %s: %s]' % (p, exc))
    if not rows:
        print('nothing to merge')
        return 1

    towns = collections.OrderedDict()
    for r in rows:
        m = (r.get('municipality') or '').strip()
        if not m:
            continue
        t = towns.setdefault(m, {'total': None, 'date': '', 'pcts': [],
                                 'srcs': set()})
        t['srcs'].add(r['_src'])
        if (r.get('level') or '').strip() == 'total':
            # KEEP THE FIRST TOTAL AND NOTE A SECOND. Two different totals for
            # one town means two blocks disagree, which is a finding, not
            # something to average away.
            cand = (num(r.get('registered')), num(r.get('voted')))
            if t['total'] and t['total'] != cand and any(cand):
                t.setdefault('conflict', []).append(cand)
            elif any(cand):
                t['total'] = cand
            t['date'] = t['date'] or (r.get('date') or '')
        else:
            t['pcts'].append((r.get('precinct') or '',
                              num(r.get('registered')), num(r.get('voted'))))

    out, n_ok, n_bad, n_single, n_part = [], 0, 0, 0, 0
    for m, t in towns.items():
        tot, pcts = t['total'], t['pcts']
        if t.get('conflict'):
            status, note = 'conflict', ('blocks disagree on the total: %s vs %s'
                                        % (tot, t['conflict'][0]))
        elif not pcts:
            status, note = (('single', 'one undivided town, no precinct detail')
                            if tot else ('empty', 'nothing read'))
            n_single += 1 if tot else 0
        elif not tot:
            status, note = 'no_total', ('%d precincts but no total; the town row '
                                        'is in another block' % len(pcts))
            n_part += 1
        else:
            sr = sum(p[1] for p in pcts if p[1] is not None)
            sv = sum(p[2] for p in pcts if p[2] is not None)
            if sr == tot[0] and sv == tot[1]:
                status, note = 'checked', 'precincts sum to both printed totals'
                n_ok += 1
            else:
                status = 'mismatch'
                note = ('precincts sum to %d/%d, the printed total says %s/%s'
                        % (sr, sv, tot[0], tot[1]))
                n_bad += 1
        out.append((m, t, status, note))

    with io.open(a.out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['municipality', 'year', 'date', 'level', 'precinct',
                    'registered', 'voted', 'status', 'note', 'read_by'])
        for m, t, status, note in out:
            w.writerow([m, a.year, t['date'], 'total', '',
                        t['total'][0] if t['total'] else '',
                        t['total'][1] if t['total'] else '',
                        status, note, 'vision'])
            for lab, reg, vot in t['pcts']:
                w.writerow([m, a.year, '', 'precinct', lab,
                            reg if reg is not None else '',
                            vot if vot is not None else '',
                            status, '', 'vision'])

    print('%d block files -> %d municipalities' % (len(paths), len(towns)))
    print('  %4d closed their own arithmetic' % n_ok)
    print('  %4d undivided towns with a single figure' % n_single)
    print('  %4d precincts with no total yet (town row in a block not read)'
          % n_part)
    print('  %4d did not sum' % n_bad)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
