#!/bin/sh
# Read every PD43 volume on disk. Skips a volume whose output already exists,
# so an interrupted run resumes instead of redoing forty minutes of OCR.
cd "$(dirname "$0")/.." || exit 1
for f in pd43/pd43-*.pdf; do
    y=$(basename "$f" .pdf | sed 's/pd43-//')
    out="pd43/out-$y.csv"
    if [ -s "$out" ] && [ "$out" -nt "$f" ]; then
        echo "== $y  already read"
        continue
    fi
    echo "== $y"
    python tools/pd43_turnout.py "$f" --year "$y" --out "$out" 2>&1 \
        | grep -v pymupdf_layout \
        | grep -E "table: pages|municipalities,|precinct rows|OCR|^no local"
done
echo "ALL VOLUMES DONE"
