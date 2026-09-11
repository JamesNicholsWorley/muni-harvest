"""What is still missing from 1986-2018, town by town and page by page.

Two things come out of this. The first is a completion figure per volume that is
honest about what `usable` means. The second is a WORKLIST: the specific towns
that failed, with the page each is printed on, so the pages that need a human --
or an agent with a cropping tool -- can be read without opening the volume.

    python tools/pd43_gaps.py                  # summary
    python tools/pd43_gaps.py --worklist pd43/worklist.csv
"""
import argparse
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
MODERN = range(1986, 2019)
# Massachusetts has 351 municipalities; 39 or so are cities, which these
# biennial volumes do not tabulate, and a dozen-odd towns elect only in odd
# years. About three hundred towns are therefore in scope for any given
# even-year volume -- the figure the 2008 volume states for itself.
TOWNS = 300.0


def page_of(doc, pages, town):
    """The 1-based page a town is printed on, for the worklist."""
    for i in pages:
        if re.search(r'\b' + re.escape(town) + r'\b', doc[i].get_text()):
            return i + 1
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--worklist', default='')
    a = ap.parse_args()

    import sys
    sys.path.insert(0, ROOT)
    from tools.pd43_turnout import table_pages, load_municipalities

    names = load_municipalities(ROOT)
    rows, work = [], []
    for path in sorted(glob.glob(os.path.join(ROOT, 'pd43', 'out-*.csv'))):
        year = os.path.basename(path)[4:-4]
        if not year.isdigit() or int(year) not in MODERN:
            continue
        recs = [r for r in csv.DictReader(io.open(path, encoding='utf-8'))
                if r['level'] == 'total']
        if not recs:
            continue
        st = collections.Counter(r['status'] for r in recs)
        usable = sum(st[k] for k in USABLE)
        noel = st['no_election']
        # TWO DENOMINATORS, BECAUSE ONE OF THEM LIES.
        #
        # Rows-produced is what this tool used to report on its own, and it only
        # counts municipalities that got as far as producing a row. A town whose
        # page was never read produces nothing, so it never enters the ratio and
        # its absence reads as success. 1986 scored 73.3% that way while holding
        # 121 of about 300 towns -- five of its eleven pages had failed OCR
        # silently and forty-two consecutive towns were missing.
        #
        # TOWNS is the honest one: roughly three hundred Massachusetts towns
        # hold an annual election, and that number does not depend on how much
        # of the volume we managed to read.
        want = len(recs) - noel
        rows.append((year, len(recs), usable, noel, want,
                     100.0 * usable / max(1, want),
                     100.0 * usable / TOWNS, st))

        bad = [r for r in recs if r['status'] not in USABLE
               and r['status'] != 'no_election']
        if a.worklist and bad:
            pdf = os.path.join(ROOT, 'pd43', 'pd43-%s.pdf' % year)
            if os.path.exists(pdf):
                doc = pymupdf.open(pdf)
                pages = [i for _k, p in table_pages(doc) for i in p]
                for r in bad:
                    work.append({
                        'year': year, 'municipality': r['municipality'],
                        'page': page_of(doc, pages, r['municipality']) or '',
                        'status': r['status'],
                        'registered': r['registered'], 'voted': r['voted'],
                        'note': r['note'][:90],
                    })

    print('%-6s %6s %7s %8s %9s %9s   %s'
          % ('year', 'rows', 'usable', 'no-elec', 'of-rows', 'of-towns',
             'top failures'))
    print('-' * 96)
    tot_u = tot_w = 0
    n_years = 0
    for year, n, usable, noel, want, pct, pct_t, st in rows:
        tot_u += usable
        tot_w += want
        n_years += 1
        top = ', '.join('%s %d' % (k, v) for k, v in st.most_common()
                        if k not in USABLE and k != 'no_election')
        print('%-6s %6d %7d %8d %8.1f%% %8.1f%%   %s'
              % (year, n, usable, noel, pct, pct_t, top))
    print('-' * 96)
    print('%-6s %6s %7d %8s %8.1f%% %8.1f%%'
          % ('ALL', '', tot_u, '', 100.0 * tot_u / max(1, tot_w),
             100.0 * tot_u / max(1.0, TOWNS * n_years)))

    if a.worklist:
        with io.open(a.worklist, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=['year', 'municipality', 'page',
                                               'status', 'registered', 'voted',
                                               'note'])
            w.writeheader()
            for r in sorted(work, key=lambda x: (x['year'], x['page'] or 0,
                                                 x['municipality'])):
                w.writerow(r)
        print('\nworklist: %d towns to read, %s' % (len(work), a.worklist))
        per = collections.Counter(r['year'] for r in work)
        print('   by year: %s'
              % ', '.join('%s:%d' % (y, per[y]) for y in sorted(per)))


if __name__ == '__main__':
    main()
