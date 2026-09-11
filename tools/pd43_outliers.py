"""Find the readings that are probably wrong even though they passed.

The arithmetic check is strong but narrow: it says a town's precincts sum to its
printed total, which means the DIGITS were read faithfully. It says nothing
about whether the figures are the right ones. A column swap that is internally
consistent passes. A town read into the wrong row passes. A precinct total
mistaken for a town total passes, as long as it sums.

So these are the checks that ask a different question -- is this figure
believable at all -- using the three things we know independently of the scan:
how many people live there, what the town reported in adjacent years, and what
turnout can physically be.

    python tools/pd43_outliers.py pd43/out-*.csv
    python tools/pd43_outliers.py pd43/out-*.csv --csv pd43/outliers.csv

Nothing here corrects anything. It prints what to go and look at, because a
check has never yet been a good enough reason to change a figure in this corpus.
"""
import argparse
import collections
import csv
import glob
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
USABLE = ('checked', 'single', 'derived')

# Turnout above this is possible but rare enough to be worth a look; above
# 100% it is not possible at all and the reading is wrong.
HIGH_TURNOUT = 0.85
# A town's electorate does not double or halve in two years. It does grow, and
# a new precinct split can move a figure, so this is deliberately loose.
JUMP = 1.8


def load_population():
    """municipality -> population, from a file that has no year column.

    THIS CHECK WAS DEAD AND LOOKED ALIVE. It was written to key on
    (municipality, year); the file is `community,population` and carries no
    year, so every lookup missed, the KeyError was swallowed, and the check
    never fired once. It reported nothing and nothing is what a clean corpus
    reports. Andover 1988 sailed through at 43,351 registered voters.

    The figure is a modern snapshot, which makes it a CONSERVATIVE ceiling for
    these years: Massachusetts towns are larger now than in the eighties, so a
    reading that exceeds today's population certainly exceeded the population
    of the year it claims to describe.
    """
    p = os.path.join(ROOT, 'config', 'population.csv')
    if not os.path.exists(p):
        return {}
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8')):
        name = (r.get('community') or r.get('municipality') or '').strip()
        try:
            out[name] = int(float(r['population']))
        except (KeyError, ValueError, TypeError):
            continue
    if not out:
        raise SystemExit('population.csv parsed to nothing -- refusing to run a '
                         'check that cannot fire')
    return out


def num(x):
    try:
        return int(str(x).replace(',', ''))
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csvs', nargs='+')
    ap.add_argument('--csv', default='')
    a = ap.parse_args()

    paths = []
    for pat in a.csvs:
        paths += sorted(glob.glob(pat))
    rows = []
    for p in paths:
        rows += [r for r in csv.DictReader(io.open(p, encoding='utf-8'))
                 if r['level'] == 'total']
    if not rows:
        print('nothing to check')
        return 1

    pop = load_population()
    series = collections.defaultdict(dict)
    for r in rows:
        reg = num(r['registered'])
        if reg and r['status'] in USABLE:
            series[r['municipality']][int(r['year'])] = reg

    found = []

    def flag(r, kind, why):
        found.append({'year': r['year'], 'municipality': r['municipality'],
                      'status': r['status'], 'registered': r['registered'],
                      'voted': r['voted'], 'check': kind, 'evidence': why})

    for r in rows:
        if r['status'] not in USABLE:
            continue
        reg, vot = num(r['registered']), num(r['voted'])
        muni, yr = r['municipality'], int(r['year'])

        # MORE VOTES THAN VOTERS. Not a judgement call: impossible.
        if reg and vot and vot > reg:
            flag(r, 'impossible_turnout',
                 '%d voted against %d registered' % (vot, reg))
        elif reg and vot and vot > reg * HIGH_TURNOUT:
            flag(r, 'high_turnout',
                 '%.0f%% turnout (%d of %d)' % (100.0 * vot / reg, vot, reg))

        # MORE VOTERS THAN RESIDENTS. Registration cannot exceed population,
        # and in practice runs well under it.
        p = pop.get(muni)
        if p and reg and reg > p:
            flag(r, 'over_population',
                 '%d registered against a population of %d' % (reg, p))

        # A JUMP THE ELECTORATE CANNOT MAKE. Compared against the nearest
        # earlier reading rather than a fixed lag, because the series is
        # biennial and gappy.
        prev = [y for y in series[muni] if y < yr]
        if reg and prev:
            py = max(prev)
            pr = series[muni][py]
            if pr and (reg > pr * JUMP or reg * JUMP < pr):
                flag(r, 'implausible_jump',
                     '%d in %d against %d in %d (x%.1f)'
                     % (reg, yr, pr, py, float(reg) / pr))

    by = collections.Counter(f['check'] for f in found)
    print('%d readings flagged out of %d usable\n'
          % (len(found), sum(1 for r in rows if r['status'] in USABLE)))
    for k, n in by.most_common():
        print('  %-20s %5d' % (k, n))
    print('\n  worst examples:')
    for k, _n in by.most_common():
        ex = [f for f in found if f['check'] == k][:3]
        for f in ex:
            print('    %-18s %-5s %-22s %s'
                  % (k, f['year'], f['municipality'], f['evidence']))

    if a.csv:
        with io.open(a.csv, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=['year', 'municipality', 'status',
                                               'registered', 'voted', 'check',
                                               'evidence'])
            w.writeheader()
            for f in sorted(found, key=lambda x: (x['check'], x['year'],
                                                  x['municipality'])):
                w.writerow(f)
        print('\nwrote %s' % a.csv)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
