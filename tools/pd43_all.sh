#!/bin/sh
# Read every PD43 volume on disk. Skips a volume already read, so an
# interrupted run resumes instead of redoing the OCR.
cd "$(dirname "$0")/.." || exit 1
for f in pd43/pd43-*.pdf; do
    case "$f" in *-flat.pdf) continue;; esac
    y=$(basename "$f" .pdf | sed 's/pd43-//')
    out="pd43/out-$y.csv"
    [ -s "$out" ] && [ "$out" -nt tools/pd43_turnout.py ] && continue
    src="$f"
    [ -f "pd43/pd43-$y-flat.pdf" ] && src="pd43/pd43-$y-flat.pdf"
    printf '%s ' "$y"
    python tools/pd43_turnout.py "$src" --year "$y" --out "$out" 2>&1 \
        | grep -oE "[0-9]+ municipalities, [0-9]+ fully checked \([0-9]+%\)" \
        || echo "no table"
done
echo "ALL VOLUMES DONE"
