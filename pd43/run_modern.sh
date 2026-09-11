#!/bin/sh
# Re-read every 1986-2018 volume with the current parser, one at a time.
#
# ONE JOB, SEQUENTIALLY. Sixteen parallel shells writing the same CSVs once ran
# for an hour and brought the machine to its knees, and orphaned shells do not
# show up in `ps -ef` under Git Bash, so nobody could see them to stop them.
cd "$(dirname "$0")/.." || exit 1
for y in 1986 1988 1990 1992 1994 1996 1998 2000 2002 2004 \
         2006 2008 2010 2012 2014 2016 2018; do
    f="pd43/pd43-$y.pdf"
    [ -f "$f" ] || { echo "$y  NO VOLUME"; continue; }
    printf '%s  ' "$y"
    python tools/pd43_turnout.py "$f" --year "$y" --out "pd43/out-$y.csv" \
        >"pd43/log-$y.txt" 2>&1
    python - "$y" <<'PY'
import csv, io, sys
y = sys.argv[1]
U = ('checked', 'single', 'derived')
r = [x for x in csv.DictReader(io.open('pd43/out-%s.csv' % y, encoding='utf-8'))
     if x['level'] == 'total']
ne = sum(1 for x in r if x['status'] == 'no_election')
u = sum(1 for x in r if x['status'] in U)
o = sum(1 for x in r if x.get('read_by') == 'ocr')
print('rows=%d usable=%d ocr=%d  %.1f%%'
      % (len(r), u, o, 100.0 * u / max(1, len(r) - ne)))
PY
done
echo "DONE"
