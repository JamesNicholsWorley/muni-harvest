#!/bin/sh
# Combine every volume read so far, check it against our own records, and show
# where the weak volumes are. Safe to run repeatedly; reads only.
cd "$(dirname "$0")/.." || exit 1

python tools/pd43_combine.py "pd43/out-*.csv" --out config/pd43_turnout.csv || exit 1

echo
echo "=== against our own pre-2021 records ==="
python tools/pd43_crosscheck.py \
    --pd43 config/pd43_turnout.csv \
    --records "$HOME/Documents/civicatlas-site/json_pre2021" \
    --out pd43/crosscheck.csv 2>/dev/null | head -14

echo
echo "=== weakest volumes: where the micro-fixes are worth spending ==="
python - <<'PY'
import collections, csv, io
rows = [r for r in csv.DictReader(io.open('config/pd43_turnout.csv',
                                          encoding='utf-8'))
        if r['level'] == 'total']
per = collections.defaultdict(lambda: collections.Counter())
for r in rows:
    per[r['year']][r['status']] += 1
print('  %-6s %6s %7s %7s   %s' % ('year', 'towns', 'usable', 'rate', 'top failure'))
for y in sorted(per):
    c = per[y]
    n = sum(c.values())
    ok = c['checked'] + c['single']
    bad = [(v, k) for k, v in c.items()
           if k not in ('checked', 'single', 'no_election')]
    worst = max(bad)[1] if bad else '-'
    print('  %-6s %6d %7d %6.0f%%   %s (%d)'
          % (y, n, ok, 100.0 * ok / max(1, n), worst,
             max(bad)[0] if bad else 0))
PY
