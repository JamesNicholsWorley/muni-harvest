"""Defect register for the published corpus.

An INDEPENDENT read of `publish/json/` and `data/inventory/master_urls.csv`, written
to answer the questions the interface portfolio implies a user will ask, and to
record where the data does not survive being asked. It changes nothing: it only
counts, samples and cites.

Every check here is phrased as a question a user would actually ask, because that
is how these were found -- each defect below surfaced from trying to draw a page,
not from staring at a schema.

Writes defects.js (window.DEFECTS) for audit.html.

Run: python research/interface/audit_defects.py
"""
import csv
import json
import glob
import os
import re
import collections
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, 'defects.js')

TALLY = re.compile(
    r'^\W*(blanks?|all\s+other(s|\s+names?)?|others?|scatter\w*|write[-\s]?ins?'
    r'|void|totals?|invalid|vacan\w*|none|under|over|defective)'
    r'(\s+(votes?|ballots?|cast|counted))*\W*$', re.I)
TALLY_IN = re.compile(r'\b(write[-\s]?ins?|blank|scatter\w*)\b', re.I)
MP = re.compile(r'^(town|city)\s+of\s+', re.I)
SUF = re.compile(r',\s*(ma|mass|massachusetts)\.?$', re.I)


def canon(m):
    return SUF.sub('', MP.sub('', str(m or '').strip())).strip()


def is_person(n):
    n = str(n or '').strip()
    return bool(n) and not (TALLY.match(n) or TALLY_IN.search(n))


def votes(c):
    v = c.get('votes')
    if isinstance(v, int):
        return v
    try:
        return int(str(v).replace(',', '').strip())
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------

CANON = {r['Municipality'].upper(): r['Municipality'] for r in csv.DictReader(
    open(os.path.join(ROOT, 'data/inventory/municipalities.csv'), encoding='utf-8'))}

INV = {}
for r in csv.DictReader(
        open(os.path.join(ROOT, 'data/inventory/master_urls.csv'), encoding='utf-8')):
    INV[(r['municipality'], r['year'])] = r

recs = []
for f in sorted(glob.glob(os.path.join(ROOT, 'publish/json/*.json'))):
    stem = os.path.splitext(os.path.basename(f))[0]
    m = re.match(r'^(.*?)(\d{4})$', stem)
    if not m:
        continue
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        recs.append({'stem': stem, 'broken': True, 'elections': []})
        continue
    recs.append({'stem': stem, 'smuni': m.group(1), 'syear': m.group(2),
                 'elections': d.get('elections', []), 'broken': False})

D = []          # the register


def defect(qid, question, title, severity, count, unit, symptom, evidence, note=''):
    D.append({'qid': qid, 'question': question, 'title': title, 'severity': severity,
              'count': count, 'unit': unit, 'symptom': symptom,
              'evidence': evidence[:6], 'note': note})


# --------------------------------------------------------------------------
# Q1  "Show me my town's election."
# --------------------------------------------------------------------------

no_muni, wrong_muni, unknown_muni, prefixed = [], [], [], collections.Counter()
for r in recs:
    for e in r['elections']:
        raw = e.get('municipality')
        if raw is None or not str(raw).strip():
            no_muni.append(r['stem'])
        elif str(raw).strip() == '<UNKNOWN>':
            unknown_muni.append(r['stem'])
        else:
            c = canon(raw)
            if str(raw).strip() != c:
                prefixed[str(raw).strip()] += 1
            if c.replace(' ', '').lower() != r['smuni'].replace(' ', '').lower():
                wrong_muni.append((r['stem'], str(raw).strip()))

defect('Q1', 'Show me my town’s election.',
       'The municipality field is missing, sentinel, or disagrees with the filename',
       'high', len(set(no_muni)) + len(set(unknown_muni)) + len({s for s, _ in wrong_muni}),
       'files',
       'A town lookup keyed on the record’s own municipality drops these silently; '
       'keyed on the filename it returns another town’s election under your town’s name.',
       [{'k': 'field absent', 'v': '%d races in %d files (e.g. %s)'
         % (len(no_muni), len(set(no_muni)), ', '.join(sorted(set(no_muni))[:3]))},
        {'k': 'literal "<UNKNOWN>"', 'v': '%d races in %d files (e.g. %s)'
         % (len(unknown_muni), len(set(unknown_muni)), ', '.join(sorted(set(unknown_muni))[:3]))},
        {'k': 'disagrees with filename', 'v': '%d races across %d files'
         % (len(wrong_muni), len({s for s, _ in wrong_muni}))}] +
       [{'k': s, 'v': 'record says “%s”' % m}
        for s, m in sorted(set(wrong_muni))[:3]],
       'Separately, %d name variants (`Town of X`, `X, MA`, ALL CAPS) split a town’s '
       'own history across keys.' % len(prefixed))

# --------------------------------------------------------------------------
# Q2  "Who won?"  -- ordering, seats, sentinels
# --------------------------------------------------------------------------

neg, zero_all, bad_seats, dup_cand = [], [], [], []
neg_in_slot = 0            # sentinel rows that still land inside a winner slot
for r in recs:
    for e in r['elections']:
        off = (e.get('office_original') or '').strip()
        rows = [c for c in e.get('candidates', []) if c.get('name_original')]
        ppl = [c for c in rows if is_person(c['name_original'])]
        nw = e.get('num_winners')
        if not isinstance(nw, int) or nw < 1:
            bad_seats.append((r['stem'], off[:44], repr(nw)))
        vs = [votes(c) for c in ppl]
        if any(v is not None and v < 0 for v in vs):
            # A sentinel sorts LAST under a descending sort, so a real winner whose
            # count was never published can be rendered as the bottom-placed loser.
            # Measure how often that actually bites rather than asserting it.
            seats = nw if isinstance(nw, int) and nw > 0 else 1
            order = sorted(ppl, key=lambda c: -(votes(c) if votes(c) is not None else -10**9))
            winners = {id(c) for c in order[:seats]}
            for c in ppl:
                v = votes(c)
                if v is not None and v < 0:
                    neg.append((r['stem'], off[:34], str(c['name_original'])[:32], v))
                    if id(c) in winners:
                        neg_in_slot += 1
        if ppl and all(v == 0 for v in vs if v is not None) and vs:
            zero_all.append((r['stem'], off[:44]))
        names = [str(c['name_original']).strip().lower() for c in ppl]
        for n, k in collections.Counter(names).items():
            if k > 1:
                dup_cand.append((r['stem'], off[:30], n[:34]))

defect('Q2', 'Who won?',
       'A sentinel value lives inside the numeric vote field',
       'medium', len(neg), 'candidate rows',
       'Any consumer that sums votes subtracts; any consumer that sorts descending '
       'puts these LAST, which is the opposite of what they mean. The corpus survives '
       'this only by luck: in nearly every affected contest EVERY candidate is a '
       'sentinel, so the degenerate ordering still fills the seats correctly.',
       [{'k': '%s · %s' % (s, o), 'v': '%s = %d' % (n, v)} for s, o, n, v in neg[:4]] +
       [{'k': 'distinct town-years', 'v': str(len({s for s, _, _, _ in neg}))},
        {'k': 'still land in a winner slot', 'v': '%d of %d' % (neg_in_slot, len(neg))}],
       'this is NOT an accident. qa/STANDARD.md rule A3 defines -1 as “elected, no count '
       'published” and -3 as “write-in winner, count not separable”. The defect is that '
       'a sentinel shares a field with real measurements, so it is invisible to every '
       'reader who has not read the standard. A null, or an explicit status field, '
       'would carry the same fact without corrupting arithmetic.')

defect('Q2', 'Who won?',
       'Zero is used to mean “the source never said”',
       'high', len(zero_all), 'contests',
       'The contest renders as a real result in which every candidate received zero '
       'votes — a statement the corpus is making and cannot support. Unlike the -1 '
       'sentinel this one is not signposted anywhere, and 0 is a legal vote count.',
       [{'k': s, 'v': o} for s, o in zero_all[:4]] +
       [{'k': 'distinct town-years', 'v': str(len({s for s, _ in zero_all}))}],
       'these are almost never OCR loss. They are newspaper '
       'write-ups that name uncontested winners without printing counts — Bedford 2021 '
       'gives “won ... by a margin of 135” and “more than 78 percent of the vote” and '
       'no absolute number anywhere. The tell is the source genre: town-years tagged '
       'as news are roughly six times over-represented here against their share of the '
       'corpus. The same fact the -1 sentinel exists to record is, in these records, '
       'written as 0 instead.')

defect('Q2', 'Who won?',
       'Seat count missing, zero or negative',
       'medium', len(bad_seats), 'contests',
       'Seat count decides who is shown as elected. At 0 or -1 nobody is elected; '
       'where it is absent the interface has to guess, and guessing 1 mis-elects '
       'every multi-seat contest.',
       [{'k': '%s · %s' % (s, o), 'v': 'num_winners = %s' % v} for s, o, v in bad_seats[:5]])

if dup_cand:
    defect('Q2', 'Who won?',
           'The same person appears twice in one contest',
           'medium', len(dup_cand), 'contests',
           'The duplicate takes a seat that belongs to someone else, and the '
           'candidate count used to judge "contested" is inflated.',
           [{'k': '%s · %s' % (s, o), 'v': n} for s, o, n in dup_cand[:5]])

# --------------------------------------------------------------------------
# Q3  "How many people ran?"  -- empty and candidate-less contests
# --------------------------------------------------------------------------

no_person, no_rows = [], []
for r in recs:
    for e in r['elections']:
        off = (e.get('office_original') or '').strip()
        rows = [c for c in e.get('candidates', []) if c.get('name_original')]
        ppl = [c for c in rows if is_person(c['name_original'])]
        if not rows:
            no_rows.append((r['stem'], off[:44]))
        elif not ppl:
            no_person.append((r['stem'], off[:44]))

defect('Q3', 'How many people ran?',
       'Offices nobody stood for are not distinguishable from parse failures',
       'medium', len(no_person), 'contests',
       'These render as an office with a Blanks row and no names. A reader cannot tell '
       'whether the town failed to fill the seat or the software lost the candidates.',
       [{'k': s, 'v': o} for s, o in no_person[:4]] +
       [{'k': 'distinct town-years', 'v': str(len({s for s, _ in no_person}))}],
       'sampled against source documents these are overwhelmingly REAL. Massachusetts '
       'returns print “Failure to Elect” and the arithmetic corroborates it (Abington '
       '2025 Sewer Commissioner: write-in 68 + blank 398 = 466, the same ballot total '
       'as every other contest on that ballot). This is therefore mostly a MODELLING '
       'gap, not data loss — “no candidate” is a real and interesting civic outcome '
       'that the schema has no way to assert. It is listed here because the interface '
       'cannot currently tell the two apart, not because the records are wrong.')

defect('Q3', 'How many people ran?',
       'Contests with an entirely empty candidate list',
       'low', len(no_rows), 'contests',
       'An office appears on the ballot with no rows beneath it at all.',
       [{'k': s, 'v': o} for s, o in no_rows[:5]])

# --------------------------------------------------------------------------
# Q4  "Which contest is this?"  -- office identity
# --------------------------------------------------------------------------

collide = collections.Counter()
collide_ex = []
diff_seats = has_term = 0
by_office = collections.Counter()
for r in recs:
    seen = collections.defaultdict(list)
    for e in r['elections']:
        seen[((e.get('office_original') or '').strip().lower(),
              (e.get('date') or '')[:10])].append(e)
    for (off, date), group in seen.items():
        if len(group) > 1:
            collide[r['stem']] += 1
            by_office[off[:40]] += 1
            nws = {g.get('num_winners') for g in group}
            if len(nws) > 1:
                diff_seats += 1
            if re.search(r'(year|yr|unexpired|term)', off, re.I):
                has_term += 1
            if len(collide_ex) < 5:
                collide_ex.append((r['stem'], off[:40], len(group)))

defect('Q4', 'Which contest is this?',
       '(town, year, office, date) is not a unique key for a contest',
       'high', sum(collide.values()), 'collisions',
       'Two different contests carry byte-identical labels. A reader asking for one '
       'office sees two result tables with no way to tell which is which, and any '
       'aggregate keyed on office silently merges them.',
       [{'k': '%s · %s' % (s, o), 'v': '%d contests share this label' % n}
        for s, o, n in collide_ex] +
       [{'k': 'most affected label', 'v': '%s (%d collisions)' % by_office.most_common(1)[0]}],
       'sampled against sources, the cause is label-stripping, not re-parsing. The '
       'office string lost either a TERM qualifier (`ASSESSOR ... Three Year Term` vs '
       '`... Two Year Unexpired Term`) or a PRECINCT (`PRECINCT 1 / Town Meeting '
       'Member` vs `Precinct 2 / ...`), and sometimes both. %d of %d collisions have '
       'differing seat counts between the colliding rows — the signature of a term '
       'split — while only %d carry any term text at all, so roughly nine in ten lost '
       'the qualifier outright. True double-parsing is essentially absent, so statewide '
       'vote totals are NOT corrupted. The damage is downstream: anything that '
       'de-duplicates on this key silently drops real contests (13 of Falmouth 2024’s '
       '14 Town Meeting Member precincts), and anything that aggregates on it sums '
       'votes across different seats. Affects %d town-years.'
       % (diff_seats, sum(collide.values()), has_term, len(collide)))

# --------------------------------------------------------------------------
# Q5  "Is this the same person?"  -- name hygiene
# --------------------------------------------------------------------------

addr, longn, allcap, mixed = [], [], 0, 0
for r in recs:
    for e in r['elections']:
        for c in e.get('candidates', []):
            n = str(c.get('name_original') or '')
            if not is_person(n):
                continue
            if re.search(r'\d+\s+\w+\s+(St|Ave|Rd|Dr|Ln|Way|Street|Road|Avenue|Hill)\b', n):
                addr.append((r['stem'], n[:52]))
            if len(n) > 45:
                longn.append((r['stem'], n[:60]))
            if n.isupper():
                allcap += 1
            elif not n.islower():
                mixed += 1

defect('Q5', 'Is this the same person across years?',
       'Candidate names carry addresses, annotations and inconsistent case',
       'medium', len(addr) + len(longn), 'rows',
       'Names are the only identifier a person has here. With a street address glued '
       'on, the same incumbent is a different string every year they move or the clerk '
       'reformats, so "what has this person run for?" cannot be answered.',
       [{'k': s, 'v': n} for s, n in (addr + longn)[:5]] +
       [{'k': 'case', 'v': '%s ALL CAPS vs %s mixed case, unnormalised'
         % (f'{allcap:,}', f'{mixed:,}')}])

# --------------------------------------------------------------------------
# Q6  "Where did this number come from?"  -- inventory vs publish
# --------------------------------------------------------------------------

published_no_file, file_not_published = [], []
have = {r['stem'] for r in recs}
for (muni, year), row in INV.items():
    stem = muni.replace(' ', '') + year
    if row['coverage_state'] == 'published' and stem not in have:
        published_no_file.append(stem)
for r in recs:
    row = INV.get((r['smuni'], r['syear']))
    if row is None:
        alt = [v for (m, y), v in INV.items()
               if m.replace(' ', '') == r['smuni'] and y == r['syear']]
        row = alt[0] if alt else None
    if row is None:
        file_not_published.append((r['stem'], 'no inventory row'))
    elif row['coverage_state'] != 'published':
        file_not_published.append((r['stem'], 'inventory says ' + row['coverage_state']))
    elif row.get('has_json') == 'no':
        file_not_published.append((r['stem'], 'inventory says has_json=no'))

stale_flag = [x for x in file_not_published if 'has_json' in x[1]]
real_disagree = [x for x in file_not_published if 'has_json' not in x[1]]

defect('Q6', 'Where did this number come from?',
       'The inventory’s own bookkeeping columns have gone stale',
       'medium', len(stale_flag) + len(real_disagree) + len(published_no_file),
       'town-years',
       'The inventory is what the coverage map is drawn from; the files are what a '
       'reader actually sees. A provenance interface has to pick one as authoritative, '
       'and today neither is reliably right.',
       [{'k': 'has_json = "no" but a published file exists', 'v': '%d of %d published '
         'town-years (%d%%)' % (len(stale_flag), len(recs),
                                round(100 * len(stale_flag) / max(1, len(recs))))},
        {'k': 'file exists, coverage_state is not "published"', 'v': '%d%s'
         % (len(real_disagree), (' — e.g. ' + ', '.join('%s (%s)' % x
            for x in sorted(set(real_disagree))[:2])) if real_disagree else '')},
        {'k': 'coverage_state "published", no file on disk', 'v': '%d%s'
         % (len(published_no_file), (' — e.g. ' + ', '.join(sorted(published_no_file)[:3]))
            if published_no_file else '')}],
       'The `has_json` column is simply not maintained; it is not evidence of anything '
       'and should either be recomputed at build time or dropped. The second row is the '
       'one that matters: a file the inventory does not consider published is still '
       'visible to anything that reads the directory.')

# --------------------------------------------------------------------------
# Q7  "Compare two towns."  -- cross-stem duplication
# --------------------------------------------------------------------------

races = collections.defaultdict(list)
for r in recs:
    for e in r['elections']:
        m = canon(e.get('municipality'))
        if not m or m == '<UNKNOWN>':
            continue
        ppl = [c for c in e.get('candidates', []) if is_person(c.get('name_original'))]
        if not ppl:
            continue
        key = (m, (e.get('date') or '')[:10],
               tuple(sorted(str(c['name_original']).split()[-1].lower().strip('.,')
                            for c in ppl)))
        races[key].append((r['stem'], tuple(votes(c) for c in ppl)))

dups = {k: v for k, v in races.items() if len({s for s, _ in v}) > 1}
agree = sum(1 for v in dups.values() if len({x[1] for x in v}) == 1)
conflict = len(dups) - agree
pairs = collections.Counter()
conf_ex = []
for k, v in dups.items():
    pairs[(tuple(sorted({s for s, _ in v})), k[0])] += 1
    if len({x[1] for x in v}) > 1 and len(conf_ex) < 5:
        conf_ex.append((k[0], k[1], v))

defect('Q7', 'Compare two towns.',
       'The same contest is published under two different town-years',
       'high', len(dups), 'races',
       'A statewide count adds these twice. Worse, %d of them disagree with '
       'themselves, so the atlas states two different results for one contest and '
       'offers no way to choose.' % conflict,
       [{'k': ' + '.join(st), 'v': '%s · %d races' % (town, n)}
        for (st, town), n in pairs.most_common(4)] +
       [{'k': '%s %s' % (t, d), 'v': ' vs '.join('%s %s' % (s, list(vv)) for s, vv in v)}
        for t, d, v in conf_ex[:2]],
       'the cause is news sources that cover several towns in one article being filed under '
       'the headline town, and their other towns already exist under their own stems.')

# --------------------------------------------------------------------------
# Q8  "How many voted?"  -- totals that cannot be right
# --------------------------------------------------------------------------

denoms = {}
dp = os.path.join(HERE, 'enrollment/denominators.csv')
if os.path.exists(dp):
    for r in csv.DictReader(open(dp, encoding='utf-8')):
        denoms[(r['municipality'], r['year'])] = int(r['registered'])

over, tiny = [], []
for r in recs:
    peak = 0
    for e in r['elections']:
        nw = e.get('num_winners')
        nw = nw if isinstance(nw, int) and nw > 0 else 1
        cast = sum(v for v in (votes(c) for c in e.get('candidates', [])
                               if c.get('name_original')) if v and v > 0)
        peak = max(peak, cast / nw)
    muni = canon(r['elections'][0].get('municipality')) if r['elections'] else ''
    reg = denoms.get((muni, r['syear'])) or denoms.get((r['smuni'], r['syear']))
    if reg and peak:
        t = peak / reg
        if t > 0.60:
            over.append((r['stem'], round(100 * t), int(peak), reg))
        elif t < 0.02:
            tiny.append((r['stem'], round(100 * t, 1), int(peak), reg))

defect('Q8', 'How many people voted?',
       'Turnout that cannot be true, in both directions',
       'medium', len(over) + len(tiny), 'town-years',
       'These sit at the extremes of any turnout ranking, which is exactly where a '
       'reader looks first. Each one is a parse failure wearing the costume of a '
       'civic finding.',
       [{'k': s, 'v': '%s%% turnout — %s ballots against %s registered'
         % (t, f'{p:,}', f'{g:,}')} for s, t, p, g in
        (sorted(over, key=lambda x: -x[1])[:3] + sorted(tiny, key=lambda x: x[1])[:3])],
       '%d compute above 60%% (seat count wrong, numerator inflated) and %d below 2%% '
       '(only a fragment of the return was captured).' % (len(over), len(tiny)))

# --------------------------------------------------------------------------
# Q9  "What kind of election was this?"
# --------------------------------------------------------------------------

questions, wd = [], collections.Counter()
for r in recs:
    for e in r['elections']:
        off = (e.get('office_original') or '')
        names = {str(c.get('name_original') or '').strip().upper()
                 for c in e.get('candidates', [])}
        if names & {'YES', 'NO'} and names <= {'YES', 'NO', 'YES.', 'NO.',
                                               'BLANKS', 'BLANK', 'OTHERS'}:
            questions.append((r['stem'], off[:50]))
        ds = (e.get('date') or '')[:10]
        try:
            wd[dt.date(*map(int, ds.split('-'))).strftime('%a')] += 1
        except Exception:
            pass

if questions:
    defect('Q9', 'What kind of election was this?',
           'Ballot questions are stored as candidate contests',
           'low', len(questions), 'contests',
           'A yes/no referendum renders as a two-candidate race in which "YES" is '
           'elected to a seat.',
           [{'k': s, 'v': o} for s, o in questions[:5]])

# --------------------------------------------------------------------------
# emit
# --------------------------------------------------------------------------

ORDER = {'high': 0, 'medium': 1, 'low': 2}
D.sort(key=lambda d: (ORDER[d['severity']], -d['count']))

meta = {
    'generated': dt.date.today().isoformat(),
    'files': len(recs),
    'races': sum(len(r['elections']) for r in recs),
    'weekday': dict(wd),
    'severity': collections.Counter(d['severity'] for d in D),
}

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('window.DEFECTS = ')
    json.dump({'meta': meta, 'defects': D}, fh, ensure_ascii=False, separators=(',', ':'))
    fh.write(';\n')

print('[OK] %d defect classes over %d files / %d contests -> %s'
      % (len(D), meta['files'], meta['races'], OUT))
for d in D:
    print('  %-6s %-7s %6d %-14s %s' % (d['qid'], d['severity'], d['count'],
                                        d['unit'], d['title'][:62]))
