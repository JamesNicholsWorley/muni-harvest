#!/bin/sh
# Re-read every 1986-2018 volume with the current parser, one at a time.
#
# ONE WRITER, AND IT PROVES IT. Two copies of this script once ran at the same
# time, on two different parser revisions, both writing the same out-*.csv
# files. Nothing reported it: the harness had said both were "killed", and a
# Git Bash `ps -ef` on Windows does not show an orphaned shell, so they were
# invisible from the side that started them. The lock below is what makes a
# second copy refuse rather than interleave.
#
#   PowerShell is the way to see them:
#   Get-CimInstance Win32_Process -Filter "Name='sh.exe' OR Name='python.exe'"
#
# RESUMABLE, because a volume takes minutes and the run gets interrupted. Each
# volume's output is stamped with the parser revision that produced it, so a
# restart re-reads only what is stale and a mixed-revision corpus cannot
# survive quietly.
cd "$(dirname "$0")/.." || exit 1

LOCK="pd43/.run_modern.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    echo "another run_modern.sh holds $LOCK -- refusing to start a second writer"
    echo "if you are sure none is running:  rmdir $LOCK"
    exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM

REV=$(python -c "import hashlib,io;print(hashlib.sha1(io.open('tools/pd43_turnout.py','rb').read()).hexdigest()[:12])")
echo "parser $REV"

for y in 1986 1988 1990 1992 1994 1996 1998 2000 2002 2004 \
         2006 2008 2010 2012 2014 2016 2018; do
    f="pd43/pd43-$y.pdf"
    [ -f "$f" ] || { echo "$y  NO VOLUME"; continue; }
    stamp="pd43/stamp-$y.txt"
    if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$REV" ] && [ -f "pd43/out-$y.csv" ]; then
        printf '%s  ' "$y"; echo "up to date"
        continue
    fi
    printf '%s  ' "$y"
    if python tools/pd43_turnout.py "$f" --year "$y" --out "pd43/out-$y.csv" \
            >"pd43/log-$y.txt" 2>&1; then
        echo "$REV" >"$stamp"
    else
        echo "FAILED (see pd43/log-$y.txt)"; continue
    fi
    python - "$y" <<'PY'
import csv, io, sys
y = sys.argv[1]
U = ('checked', 'single', 'derived')
r = [x for x in csv.DictReader(io.open('pd43/out-%s.csv' % y, encoding='utf-8'))
     if x['level'] == 'total']
ne = sum(1 for x in r if x['status'] == 'no_election')
u = sum(1 for x in r if x['status'] in U)
print('rows=%d usable=%d  %.1f%%'
      % (len(r), u, 100.0 * u / max(1, len(r) - ne)))
PY
done
echo "DONE"
