#!/bin/sh
# Read every PD43 volume. STRONG VOLUMES FIRST: 1986-2018 have text layers and
# yield usable denominators in seconds, where the 1970s volumes are OCR-bound
# and take minutes for data that does not yet validate. Breadth before depth.
# Skips a volume already read against the current parser, so it resumes.
cd "$(dirname "$0")/.." || exit 1
ORDER="2008 2006 2004 2002 2000 1998 1996 1994 1992 1990 1988 1986 2010 2012 2014 2016 2018 1983 1982 1981 1979 1977 1975 1973 1971 1984 1980 1978 1976 1974 1972 1970"
for y in $ORDER; do
    src="pd43/pd43-$y.pdf"
    [ -f "pd43/pd43-$y-flat.pdf" ] && src="pd43/pd43-$y-flat.pdf"
    [ -f "$src" ] || continue
    out="pd43/out-$y.csv"
    [ -s "$out" ] && [ "$out" -nt tools/pd43_turnout.py ] && continue
    printf '%s ' "$y"
    # Report whatever summary the parser prints, rather than one exact wording.
    # A grep for a fixed phrase printed `no table` the moment that phrase
    # changed, for volumes that had in fact parsed perfectly well -- a reporting
    # bug that reads exactly like a data problem.
    python tools/pd43_turnout.py "$src" --year "$y" --out "$out" 2>&1 \
        | grep -vE "pymupdf_layout|reference list" \
        | grep -E "municipalities|no local-election" \
        | head -1
    [ -s "$out" ] || echo "   (nothing written for $y)"
done
echo "ALL VOLUMES DONE"
