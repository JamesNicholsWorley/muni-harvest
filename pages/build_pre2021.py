"""Build the pre-2021 bundle the map loads on demand.

The published app is driven by one object, `window.MVP`, which `build_mvp.py`
writes from the 2021-2026 corpus on the owner's machine. The pre-2021 records
are a different thing with a different history: 961 town-years cut out of annual
town reports, parsed from page images, and gated to `publish` one at a time.

They are emitted as a SECOND object, `window.MVP_PRE`, rather than merged into
the first, for three reasons.

  * `mvp-data.js` is already 12MB. Every visitor pays for it before the map
    draws. Pre-2021 is the smaller and much less used half, and making the
    common case pay for the rare one is the wrong trade.
  * The two are not the same evidence. A 2021-2026 record carries the source
    line each figure was read off; a pre-2021 record cannot, because the pages
    were read as images and the lines were never pooled. Keeping them in
    separate objects keeps the page honest about which it is showing.
  * `build_mvp.py` is 317KB and reads the raw OCR, the extracted text and the
    source PDFs, none of which exist for this corpus. Extending it would mean
    teaching all of that to be optional.

So this reads only what the gate already published, plus the URL manifests, and
is small enough to run anywhere -- including CI, which `build_mvp.py` cannot.

    python pages/build_pre2021.py --json-dir <civicatlasma>/json_pre2021 \
                                  --out <civicatlasma>/mvp/mvp-pre2021.js
"""
import argparse
import csv
import datetime
import glob
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 2000-2020 is the stated scope of the pre-2021 sweep. A handful of sections
# carry a date outside it -- a 1999 report filed late, three 2021 elections that
# the modern corpus already owns and owns better. They are dropped here rather
# than shown twice or shown alone, and the count of what was dropped is printed.
YEAR_MIN, YEAR_MAX = 2000, 2020

# Verbatim from build_mvp.py. A tally row is not a person, and the two corpora
# have to agree on that or the same contest reads as contested in one era and
# uncontested in the other.
NON_CANDIDATE = re.compile(
    r'^\W*(?:(?:the\s+)?(?:number|total|count)\s+of\s+)?'
    r'(blanks?|all\s+other(s|\s+names?)?|others?|other\s+names?'
    r'|scatter(ing|ed)?|write[-\s]?in(s|structions?)?|misc(ellaneous)?'
    r'|void|totals?|invalid|vacan(t|cy)|none|no\s+candidates?'
    r'|under\s*votes?|over\s*votes?|under|over|defective|spoiled|exhausted)'
    r'(\s*[\(\[]?\s*(votes?|ballots?|cast|counted|blanks?)\s*[\)\]]?)*\W*$', re.I)
NON_CANDIDATE_CONTAINS = re.compile(r'\b(write[-\s]?ins?|blanks?|scatter\w*)\b', re.I)
TERM = re.compile(r'for\s+(one|two|three|four|five|six|1|2|3|4|5|6)\s*[-\s]?year', re.I)
WORD_NUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}
OFFICE_ALIAS = {
    'selectmen': 'Select Board', 'selectman': 'Select Board',
    'board of selectmen': 'Select Board', 'select board member': 'Select Board',
    'assessor': 'Board of Assessors', 'assessors': 'Board of Assessors',
    'board of public health': 'Board of Health',
    'trustee of public library': 'Library Trustee',
    'library trustees': 'Library Trustee',
    'trustees of public library': 'Library Trustee',
    'housing authority member': 'Housing Authority',
    'town meeting members': 'Town Meeting Member',
    'school committee member': 'School Committee',
    'planning board member': 'Planning Board',
}

# A candidate is counted toward "contested" only if they cleared this share of
# the ballots. Same threshold the published page uses, so the two eras can be
# compared without a footnote.
CONTEST_FLOOR = 0.05


def is_tally(name):
    n = (name or '').strip()
    return bool(NON_CANDIDATE.match(n) or NON_CANDIDATE_CONTAINS.search(n))


def clean_office(raw):
    """Strip the term clause and normalise the name, keeping the printed form."""
    s = re.sub(r'\s+', ' ', (raw or '').strip())
    s = re.sub(r'\s*[-–]\s*[Ff]or\s+.*$', '', s)
    s = re.sub(r',?\s*[Ff]or\s+(one|two|three|four|five|six|\d)\s*[-\s]?[Yy]ear.*$',
               '', s)
    s = s.strip(' ,-–')
    return OFFICE_ALIAS.get(s.lower(), s) or (raw or '').strip()


def term_of(raw):
    m = TERM.search(raw or '')
    if not m:
        return None
    v = m.group(1).lower()
    return WORD_NUM.get(v, int(v) if v.isdigit() else None)


def load_urls(root):
    """stem -> (url, whether this is the document we actually read).

    The pre-2021 records do not carry a source URL: the gate wrote what the
    document said, not where it came from. It is recoverable from the harvest
    manifests, and worth recovering, because a figure the reader cannot go and
    check against the town's own PDF is worth much less than one they can.

    BUT THE MANIFESTS ARE NOT ALL THE SAME KIND OF THING, and treating them as
    one is how a reader gets sent to the wrong document.

    `atr_section_urls.csv` records what was FETCHED AND SECTIONED: it carries a
    status, a byte count and a page count, so a row in it is an observation. Every
    other `atr_*urls*.csv` is a list of CANDIDATES the crawl might try -- several
    per town-year, most never fetched, and some of them wrong. Boylston's annual
    reports were sectioned under the stem `Marshfield`, and the candidate list for
    Marshfield 2013 also offered a Bell County, Texas election result. Reading
    them in filename order and taking the first hit is close to picking at random.

    So the sectioned manifest is read first and wins, and everything else is a
    fallback that is labelled as one.
    """
    urls, exact = {}, {}
    sectioned = os.path.join(root, 'config', 'atr_section_urls.csv')
    others = [p for p in sorted(glob.glob(os.path.join(root, 'config',
                                                       'atr_*urls*.csv')))
              if os.path.abspath(p) != os.path.abspath(sectioned)]

    for path, is_exact in [(sectioned, True)] + [(p, False) for p in others]:
        if not os.path.exists(path):
            continue
        try:
            with io.open(path, encoding='utf-8', newline='') as fh:
                for row in csv.DictReader(fh):
                    muni, year = row.get('municipality'), row.get('year')
                    url = (row.get('url') or '').strip()
                    if not (muni and year and url):
                        continue
                    stem = re.sub(r'\s+', '', muni) + str(year).strip()
                    if stem in urls:
                        continue
                    urls[stem] = url
                    exact[stem] = is_exact
        except (OSError, ValueError, csv.Error) as exc:
            print('  [skip] %s: %s' % (os.path.basename(path), exc))
    return urls, exact


def build_race(e, ballots):
    """One contest, in the positional shape the page already renders."""
    raw = e.get('office_original') or ''
    cands, extras, cast = [], [], 0
    for c in e.get('candidates') or []:
        name = (c.get('name_original') or '').strip()
        v = c.get('votes')
        if not name:
            continue
        if isinstance(v, int) and v >= 0:
            cast += v
        if is_tally(name):
            extras.append([name, v if isinstance(v, int) else 0])
        else:
            # The same ten slots the 2021-2026 records use, so one render
            # function serves both. The provenance slots are null because this
            # corpus has no pooled source lines to point at -- the drawer reads
            # that as "nothing to show" and says so, rather than showing a
            # confident blank.
            cands.append([name, v if isinstance(v, int) else -1,
                          -1, None, -1, None, None, None, None, None, None])

    seats = e.get('num_winners')
    if not isinstance(seats, int) or seats < 1:
        seats = 1
    floor = (ballots or cast) * CONTEST_FLOOR
    real = [c for c in cands if isinstance(c[1], int) and c[1] > floor]
    return {
        'office': clean_office(raw),
        'raw': raw,
        'scope': (e.get('district_original') or '').strip(),
        'seats': seats,
        'seats_src': e.get('num_winners_source'),
        'term': term_of(raw),
        'cands': cands,
        'extras': extras,
        'cast': cast,
        'conf': e.get('extraction_confidence'),
        'contested': len(real) > seats,
    }


def margin_of(race):
    """Gap between the last winner and the runner-up, as votes and as a share.

    Same definition the published map shades by: the seat that was closest to
    changing hands. A contest with no more candidates than seats has no margin
    at all -- not a margin of zero -- and returns None, because nobody was
    beaten.
    """
    v = sorted((c[1] for c in race['cands'] if isinstance(c[1], int) and c[1] >= 0),
               reverse=True)
    s = race['seats']
    if len(v) <= s or s < 1:
        return None
    gap = v[s - 1] - v[s]
    return (gap, gap / race['cast']) if race['cast'] else None


def build(json_dir, root):
    urls, exact = load_urls(root)
    ty, towns, dropped, tmargin = {}, {}, [], {}
    n_races = n_cands = n_votes = 0

    for path in sorted(glob.glob(os.path.join(json_dir, '*.json'))):
        try:
            doc = json.load(io.open(path, encoding='utf-8'))
        except (OSError, ValueError) as exc:
            print('  [skip] %s: %s' % (os.path.basename(path), exc))
            continue
        if doc.get('_gate') != 'publish':
            dropped.append((os.path.basename(path), 'gate=' + str(doc.get('_gate'))))
            continue
        elections = doc.get('elections') or []
        if not elections:
            dropped.append((os.path.basename(path), 'no elections'))
            continue

        muni = (elections[0].get('municipality') or '').strip()
        date = elections[0].get('date') or ''
        year = date[:4]
        if not muni or not year.isdigit():
            dropped.append((os.path.basename(path), 'no municipality or date'))
            continue
        if not (YEAR_MIN <= int(year) <= YEAR_MAX):
            dropped.append((os.path.basename(path), 'year %s out of scope' % year))
            continue

        # BALLOTS CAST IS MARKS DIVIDED BY SEATS, NOT MARKS.
        #
        # Ballots cast is not printed in these sections, so it has to be derived,
        # and the obvious derivation is wrong. A contest electing k members takes
        # k marks from every ballot, so the votes in a two-seat Select Board race
        # sum to twice the number of people who voted. Taking the busiest contest
        # at face value therefore reported roughly double the truth for most
        # towns and triple it where the biggest race had three seats.
        #
        # Checked against Public Document 43, which prints the real figure: of 30
        # towns overlapping in 2008, 27 were overstated and the ratios were
        # exactly 2.0 and exactly 3.0. The three that agreed were the towns whose
        # largest contest had a single seat.
        #
        # What each contest supports is cast/seats, and the true figure is at
        # least the largest of those -- still a floor, because every contest can
        # be undervoted, but a floor that cannot exceed the truth.
        peak = 0
        races = []
        for e in elections:
            r = build_race(e, 0)
            seats = max(1, r['seats'])
            peak = max(peak, -(-r['cast'] // seats))
            races.append(r)
        # Second pass: the contested test needs the ballot figure, which is only
        # known once every contest has been totalled.
        races = [build_race(e, peak) for e in elections]

        stem = doc.get('_source_stem') or (re.sub(r'\s+', '', muni) + year)
        g = doc.get('_grounded') or {}
        bridge = doc.get('_bridge_problems') or []

        # THE URL IS LOOKED UP BY STEM, NOT BY THE RECORD'S OWN YEAR.
        #
        # An annual report is filed for the year it covers, so the section
        # holding the 2009 election routinely sits in the report harvested as
        # `Barnstable2010`. The bridge already settled which year the ELECTION
        # was, off the printed page, and the stem still names the DOCUMENT the
        # text was read from. Looking the URL up by the election year would find
        # a different report, or none.
        #
        # A record that carries its own `_source_url` -- written when a stem was
        # corrected by hand, with the reason recorded beside it -- outranks any
        # manifest, because somebody has checked that one.
        url = (doc.get('_source_url') or '').strip() or urls.get(stem)
        is_exact = bool(doc.get('_source_url')) or exact.get(stem, False)
        url_withheld = None

        # WHERE THE URL NAMES A TOWN, IT HAS TO BE THIS ONE.
        #
        # 53 of the 4,451 sectioned documents were fetched from a URL naming a
        # different tenant of a shared municipal CMS -- several of them out of
        # state. The publication gate held fifty of them. It cannot hold one
        # whose page names a real Massachusetts town, which is how three
        # Boylston reports came through filed as Marshfield. Rather than trust
        # the join, the URL is asked whether it corroborates the printed name;
        # where it names some other town instead, no link is offered and the
        # reason is carried to the page.
        if url:
            named = re.search(r'/revize/([a-z]+?)(?:ma|tx)?/', url.lower())
            want = re.sub(r'[^a-z]', '', muni.lower())
            if named and want and not named.group(1).startswith(want[:5]):
                url, url_withheld = None, (
                    'The document was fetched from a URL naming %s, and the page '
                    'is printed %s. Which document this record was read from has '
                    'not been confirmed, so no link to it is offered here.'
                    % (named.group(1), muni))

        rec = {
            'n': len(races),
            'races': races,
            'date': date,
            'peak': peak or None,
            'cast': sum(r['cast'] for r in races),
            'seats': sum(r['seats'] for r in races),
            'contested': sum(1 for r in races if r['contested']),
            'unc': sum(1 for r in races if not r['contested']),
            'kind': 'official',
            'pub': 'Annual town report',
            'url': url,
            'url_withheld': url_withheld,
            # True where the URL is the document that was actually fetched and
            # sectioned, rather than a candidate the crawl merely listed.
            'url_exact': is_exact,
            'srcfile': stem,
            'grounded': {'names': g.get('names'), 'figures': g.get('figures')},
            # What the schema bridge could not settle, carried to the page
            # rather than left in the file.
            'bridge': bridge,
            'era': 'pre2021',
            # No denominator exists for these years, so no turnout is claimed.
            'turnout': None,
            'reg': None,
            'has_src': False,
            'lines': [],
            'chain': [],
            'gaps': [],
            'qa': [],
        }

        key = muni + '|' + year
        # The closest seat in the town, for the map's margin shading. Computed
        # here rather than in the browser so the two eras shade by one
        # definition and the page does not carry a second implementation of it.
        gaps = [m for m in (margin_of(r) for r in races) if m]
        if gaps:
            tmargin[key] = min(g[1] for g in gaps)
        ty[key] = rec
        towns.setdefault(muni, 0)
        towns[muni] += 1
        n_races += len(races)
        n_cands += sum(len(r['cands']) for r in races)
        n_votes += sum(c[1] for r in races for c in r['cands']
                       if isinstance(c[1], int) and c[1] > 0)

    years = sorted({k.split('|')[1] for k in ty})
    with_url = sum(1 for r in ty.values() if r['url'])
    withheld = sum(1 for r in ty.values() if r['url_withheld'])
    with_bridge = sum(1 for r in ty.values() if r['bridge'])
    bundle = {
        'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'years': years,
        'ty': ty,
        'tmargin': tmargin,
        'stats': {
            'town_years': len(ty),
            'towns_with': len(towns),
            'races': n_races,
            'cands': n_cands,
            'votes': n_votes,
            'with_url': with_url,
            'url_withheld': withheld,
            'with_bridge': with_bridge,
            'year_min': years[0] if years else None,
            'year_max': years[-1] if years else None,
        },
    }
    return bundle, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json-dir', required=True)
    ap.add_argument('--root', default=ROOT,
                    help='muni-harvest root, for config/atr_*urls*.csv')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    bundle, dropped = build(a.json_dir, a.root)
    with io.open(a.out, 'w', encoding='utf-8') as fh:
        fh.write('window.MVP_PRE = ')
        json.dump(bundle, fh, separators=(',', ':'), ensure_ascii=False)
        fh.write(';\n')

    s = bundle['stats']
    print('[OK] wrote %s  %.2f MB' % (a.out, os.path.getsize(a.out) / 1e6))
    print('     %d town-years, %d municipalities, %s-%s'
          % (s['town_years'], s['towns_with'], s['year_min'], s['year_max']))
    print('     %d contests, %d candidates, %s votes'
          % (s['races'], s['cands'], format(s['votes'], ',')))
    print('     %d of %d town-years carry a source URL (%d withheld as unconfirmed)'
          % (s['with_url'], s['town_years'], s['url_withheld']))
    print('     %d carry a note from the schema bridge' % s['with_bridge'])
    if dropped:
        print('     %d dropped:' % len(dropped))
        seen = {}
        for _, why in dropped:
            key = re.sub(r'\d{4}', 'YYYY', why)
            seen[key] = seen.get(key, 0) + 1
        for why, n in sorted(seen.items(), key=lambda x: -x[1]):
            print('       %4d  %s' % (n, why))


if __name__ == '__main__':
    main()
