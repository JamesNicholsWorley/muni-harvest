"""Where the town-election table is, how big it should be, and what must be OCR'd.

Three questions have to be answered before a single page is read, and getting
any of them wrong is invisible in the output:

1. HOW MANY TOWNS SHOULD THIS VOLUME YIELD. Every volume prints its own answer
   in the front matter -- `142 towns, one precinct each` and `165 towns divided
   into 783 precincts` -- and those two add to the number of towns that held an
   election that year. Measured against a guessed 300, 1986 scored 52.7%; the
   volume itself says 307. The guess was never the same number twice.

2. WHICH PAGES ARE THE TABLE. The section is ONE CONTIGUOUS RUN of pages, and
   treating it as several was the single largest loss in the older volumes. The
   heading survives on some pages and not others, so a run-of-consecutive-
   headings scan cut 1973's town table into four pieces and dropped the eight
   pages between them -- pages that are unquestionably part of the table,
   because the table is alphabetical and Duxbury does not follow Blackstone.
   Find the first and last page that carry the heading, then take everything in
   between.

3. WHICH PAGES NEED OCR. Not `does the page have text` -- these pages nearly all
   have some -- but DOES ITS TEXT CARRY THE FIGURES. 1973 page 38 extracts 129
   words: every town name, every precinct number, every dash, and exactly one
   number. The labels are there and the figures are not. Counting characters,
   words, or ink all call that page readable. Counting figures against rows does
   not.

   Ink cannot do this job. It was calibrated on the 1986-2018 scans, where a
   table inks 2-9% of the sheet; the 1970s booklets are lighter and smaller, and
   a full table page there measures 0.3% -- less than a blank page in 2008. An
   absolute ink threshold is a threshold on scan quality, not on content.

    python tools/pd43_scope.py                 # every volume
    python tools/pd43_scope.py 1973 1986       # named ones
    python tools/pd43_scope.py --csv pd43/scope.csv
"""
import argparse
import csv
import io
import os
import re
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pymupdf.TOOLS.mupdf_display_errors(False)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The running head of the town table, in every form the series prints it. The
# modern volumes shout `REGISTERED VOTERS AND PEOPLE WHO VOTED AT 1996 TOWN
# ELECTIONS`; the seventies booklets set `Towns and Voting Precincts / Town
# Elections in 1973` in title case, and sometimes only `Towns`.
TOWN_HEAD = re.compile(
    r'TOWN\s+ELECTIONS?\s+IN\s+\d{4}'
    r'|TOWNS?\s+AND\s+VOTING\s+PRECINCTS'
    r'|AT\s+\d{4}\s+TOWN\s+ELECTIONS'
    r'|TOWN\s+ELECTIONS?\s*[-—]?\s*\d{4}\s*$', re.I | re.M)
CITY_HEAD = re.compile(
    r'CITY\s+ELECTIONS?\s+IN\s+\d{4}'
    r'|CITIES,?\s+WARDS\s+AND\s+VOTING\s+PRECINCTS', re.I)
# What comes after the table and must not be swept into it.
SECTION_END = re.compile(
    r'RECAPITULATION|NUMBER\s+OF\s+VOTES\s+RECEIVED|VOTES\s+RECEIVED\s+BY'
    r'|PRESIDENTIAL\s+PRIMAR|STATE\s+PRIMAR|PARTY\s+ENROLLMENT'
    r'|TABLE\s+OF\s+CONTENTS', re.I)

FIG = re.compile(r'\b\d{1,3}(?:[,.]\d{3})+\b|\b\d{2,5}\b')
# A row of this table is a town name or a precinct number with a figure beside
# it. The precinct markers are the cheapest thing to count and the hardest to
# mistake for anything else.
PCT_MARK = re.compile(r'\bPrecinct\b|\bP[ce]t\.', re.I)


def stated_counts(doc):
    """-> {'single': n, 'divided': n, 'towns': n} from the volume's own summary.

    `single + divided` is the number of towns holding an election that year, and
    it agrees with the volume's own `307 towns, 969 precincts` line wherever
    both are legible. The two-part form is used in preference because it is
    specific: the bare `N towns` appears in four other sentences on the same
    page -- the town ballot act, the state election recapitulation -- and
    matching it returned 312 for 1982, 306 for 1990 and 311 for 1996, which
    looked like a trend and was three different sentences.
    """
    out = {}
    for i in range(min(45, doc.page_count)):
        t = ' '.join(doc[i].get_text().split())
        m = re.search(r'([\d,]{2,5})\s+towns?,?\s+(?:with\s+)?one\s+precinct'
                      r'\s+each', t, re.I)
        if m:
            out['single'] = int(m.group(1).replace(',', ''))
        m = re.search(r'([\d,]{2,5})\s+towns?,?\s+divided\s+into\s+([\d,]+)'
                      r'\s+precinct', t, re.I)
        if m:
            out['divided'] = int(m.group(1).replace(',', ''))
        # The seventies word it the other way round: `195 towns, 1 each; 117
        # towns divided into voting precincts, 556`.
        m = re.search(r'([\d,]{2,5})\s+towns?,?\s+1\s+each', t, re.I)
        if m and 'single' not in out:
            out['single'] = int(m.group(1).replace(',', ''))
        m = re.search(r'([\d,]{2,5})\s+towns?\s+divided\s+into\s+voting'
                      r'\s+precincts', t, re.I)
        if m and 'divided' not in out:
            out['divided'] = int(m.group(1).replace(',', ''))
        if 'single' in out and 'divided' in out:
            break
    if 'single' in out and 'divided' in out:
        out['towns'] = out['single'] + out['divided']
    return out


def head_pages(doc, pat):
    return [i for i in range(doc.page_count) if pat.search(doc[i].get_text())]


def looks_like_table(doc, i, other):
    """Is this page a page of the table, judged on content alone? -> bool

    The heading cannot be asked. It is printed on every page of the table and
    survives the scan on some of them: 2018 carries it on ONE page of a
    fourteen-page table, 1973 on ten of twenty-four. Selecting pages by the
    heading therefore selects pages by scan quality, and the pages it discards
    are the ones that most needed reading.

    What every page of the table does have is rows of figures under precinct
    markers. A page with neither, that names another section, is where it stops.
    """
    t = doc[i].get_text()
    if other.search(t) or SECTION_END.search(t):
        return False
    figs, marks = page_figures(doc, i)
    # A SCAN WITH NO TEXT CONTINUES A RUN BUT CANNOT START ONE. In the middle of
    # an alphabetical table an unreadable page is unquestionably part of it; on
    # its own it is any blank sheet in the volume.
    return figs >= 15 or marks >= 4 or len(t.split()) < 60


def section(doc, pat, other):
    """The table, from a heading forward through everything that reads like it.

    -> [page indexes], contiguous

    THE HEADING FINDS THE START AND THE CONTENT FINDS THE END. Taking the
    longest run of consecutive headings instead picked out the CONTENTS page in
    2014 and 2018 -- where the section is listed on two adjacent lines and so
    scores a longer run than the table itself, which prints its heading once.
    """
    best = []
    for start in head_pages(doc, pat):
        if not looks_like_table(doc, start, other) and not (
                start + 1 < doc.page_count
                and looks_like_table(doc, start + 1, other)):
            continue                      # a contents entry, not the section
        # A PAGE THAT DOES NOT READ LIKE THE TABLE IS NOT THE END OF IT. One
        # sheet whose scan produced a heading and nothing else sits inside
        # 1988's table and inside 2000's, and stopping there cut five pages off
        # each. The run ends where the table ends -- at the recapitulation or
        # the next section -- so look past a bad page to see whether the table
        # resumes, and only stop when it does not.
        j, end = start + 1, start + 1
        while j < doc.page_count:
            if looks_like_table(doc, j, other):
                end = j + 1
                j += 1
            elif j - end < 2 and SECTION_END.search(doc[j].get_text()) is None:
                j += 1                    # a bad sheet; see if the table resumes
            else:
                break
        if end - start > len(best):
            best = list(range(start, end))
    return best if len(best) >= 2 else []


def page_figures(doc, i):
    """(figures, precinct markers) in the page's own text layer."""
    t = doc[i].get_text()
    return len(FIG.findall(t)), len(PCT_MARK.findall(t))


def needs_ocr(figs, marks, words):
    """Does this page's text layer carry its figures? -> bool

    Every row of this table has two figures on it. A page whose text holds the
    structure -- the precinct markers -- but not two figures per row has had its
    figures dropped by the extractor, and no amount of re-parsing that text will
    find them. 1973 page 38 scores 129 words, 24 precinct markers and 1 figure.

    A page with no structure and no words is a bare scan and needs OCR for the
    ordinary reason. A page with structure and figures is readable as it stands.
    """
    if words < 40:
        return True                       # nothing there at all
    if marks >= 4 and figs < 1.2 * marks:
        return True                       # labels without their figures
    return figs < 20


def load_sections():
    """The hand-verified section map, if there is one. -> {(year, kind): dict}

    DETECTION WAS WRONG THREE DIFFERENT WAYS ON THIRTY-TWO VOLUMES, and each
    fix broke a volume the previous one had got right: a longest-run-of-headings
    scan picked the contents page in 2014 and 2018, extending on content swept
    1983's city table into its town table, and stopping at the first unreadable
    page cut five pages off 1988 and 2000. Thirty-two volumes is a bounded job
    that can simply be looked at, and a page range someone has read is worth
    more than a rule that is right most of the time and silent when it is not.

    `config/pd43_sections.csv` carries the verified ranges, the volumes that
    have no town table at all, and -- for 1982 -- the year the table actually
    reports, which is not the year on the cover.
    """
    p = os.path.join(ROOT, 'config', 'pd43_sections.csv')
    if not os.path.exists(p):
        return {}
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8')):
        try:
            lo, hi = int(r['first_page']), int(r['last_page'])
        except (ValueError, TypeError):
            lo = hi = None                # a volume with no table, or unscoped
        out[(r['volume'], r['kind'])] = {
            'pages': list(range(lo - 1, hi)) if lo else [],
            'year': r['election_year'] or r['volume'],
            'verified': r['verified'], 'note': r['note']}
    return out


SECTIONS = load_sections()


def survey(year):
    f = os.path.join(ROOT, 'pd43', 'pd43-%s.pdf' % year)
    if not os.path.exists(f):
        return None
    doc = pymupdf.open(f)
    st = stated_counts(doc)
    known = SECTIONS.get((year, 'town'))
    if known is not None:
        town = known['pages']
        city = SECTIONS.get((year, 'city'), {}).get('pages', [])
    else:
        town = section(doc, TOWN_HEAD, CITY_HEAD)
        city = section(doc, CITY_HEAD, TOWN_HEAD)
    # Where both patterns claim the same pages, the town run wins: `Towns and
    # Voting Precincts` and `Cities, Wards and Voting Precincts` end in the same
    # three words, and a bad scan of either can match both.
    city = [i for i in city if i not in set(town)]
    eyear = (known or {}).get('year', year)
    pages = []
    for i in town:
        figs, marks = page_figures(doc, i)
        words = len(doc[i].get_text('words'))
        pages.append({'page': i, 'figs': figs, 'marks': marks, 'words': words,
                      'ocr': needs_ocr(figs, marks, words)})
    doc.close()
    return {'year': year, 'election_year': eyear, 'stated': st,
            'town': town, 'city': city, 'pages': pages}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('years', nargs='*')
    ap.add_argument('--csv', default='')
    a = ap.parse_args()
    years = a.years or sorted(
        re.search(r'(\d{4})', os.path.basename(p)).group(1)
        for p in os.listdir(os.path.join(ROOT, 'pd43'))
        if p.startswith('pd43-') and p.endswith('.pdf') and 'flat' not in p)

    rows, tot_ocr = [], 0
    print('%-6s %-6s %-6s %-11s %-5s %-5s %s'
          % ('vol', 'elec', 'towns', 'town pages', 'n', 'ocr', 'city pages'))
    for y in years:
        s = survey(y)
        if not s:
            continue
        t = s['town']
        ocr = [p['page'] for p in s['pages'] if p['ocr']]
        tot_ocr += len(ocr)
        rows.append(s)
        print('%-6s %-6s %-6s %-11s %-5d %-5d %s'
              % (y, s['election_year'], s['stated'].get('towns', '?'),
                 '%d-%d' % (t[0] + 1, t[-1] + 1) if t else '-',
                 len(t), len(ocr),
                 '%d-%d (%d)' % (s['city'][0] + 1, s['city'][-1] + 1,
                                 len(s['city'])) if s['city'] else '-'))
    print('\n%d town pages need OCR across %d volumes' % (tot_ocr, len(rows)))
    if a.csv:
        with io.open(a.csv, 'w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['year', 'page', 'words', 'figures', 'precinct_marks',
                        'needs_ocr'])
            for s in rows:
                for p in s['pages']:
                    w.writerow([s['year'], p['page'] + 1, p['words'],
                                p['figs'], p['marks'], int(p['ocr'])])
        print('wrote %s' % a.csv)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
