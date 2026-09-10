# pd43/

Working directory for the Public Document 43 series. The volumes are large
scans and are not committed; `tools/pd43_fetch.py` re-fetches any of them.

    python tools/pd43_fetch.py --list
    python tools/pd43_fetch.py --years 2000,2002,2008 --dir pd43
    python tools/pd43_turnout.py pd43/pd43-2008.pdf --year 2008 --out pd43/out-2008.csv

## What limits this series is the text layer, not the parser

Measured over the table pages of three volumes:

    2008   13 of 15 pages carry a text layer   ->  253 towns, 83% usable
    2002   12 of 15                            ->  260 towns
    2000    7 of 14                            ->  144 towns

The pages that parse badly are, with few exceptions, pages with nothing to
parse: an image-only page reports about twenty words, all of them the running
head. Half the 2000 volume is like that. No amount of work on the parser reaches
them.

Tesseract is installed on this machine and reads those pages fine -- about three
seconds a page at 3x, and the figures come back right (Belmont 17,243 / 3,483,
Bellingham 8,811 / 2,195, both matching the printed page). At roughly 15 table
pages a volume and 24 volumes, OCR for the whole series is around 350 pages and
under half an hour, at no cost.

So the shape of the work is: use the text layer where there is one, OCR the page
where there is not, and let the arithmetic decide whether either worked.

## Everything is checked by the page's own arithmetic

The precinct rows sum to the TOTALS row, so no one has to read a page to know
whether it was read correctly. `status` in the output CSV is the verdict:

    checked      precincts sum to both printed totals
    single       an undivided town; one figure, nothing to cross-foot
    no_election  the volume states the town does not elect this year
    reg_only     registered voters sum, people who voted do not
    no_total     no TOTALS row could be read
    mismatch     the precincts do not sum to the printed total

Only the last three want a person, and they want the page, not the CSV.

## Cities are not in the biennial volumes

The even-year volumes tabulate town elections only. The 2008 volume's own
summary counts 39 cities and 1,050 city precincts, and then tabulates none of
them: cities elect in odd years. Towns that elect in odd years say so in the
table, printed `ODD YEARS ONLY`, which is worth having -- it is an authoritative
statement that no election was held, which is otherwise indistinguishable from
never having looked.

The 1978-1984 volumes are annual and may carry the odd years. Unchecked.

## Where the series stands

29 of the 32 volumes yield something; `config/pd43_turnout.csv` holds 4,471
town-year rows and 21,692 precinct rows, with 3,969 election dates and 114 towns
stated as holding no election that year.

BUT THE YIELD IS NOT EVEN, and the honest split is by era rather than by volume:

    1981-2018   the working half. 2,478 usable registered-voter figures,
                1,307 verified by their own arithmetic, 1,171 single-precinct
                towns. This is what should be joined to anything.
    1970-1979   read, but almost nothing survives validation. The data is
                extracted -- 1971 alone gives 2,070 precinct rows -- and it is
                marked `hierarchy`, `no_total` or `mismatch`, not `checked`.
                Treat it as located, not as read.

WHAT THE 1970s VOLUMES NEED, specifically:

  * THE SCANS ARE SIDEWAYS AND TWO-UP. Each PDF page of an odd-year booklet
    holds two printed pages rotated ninety degrees, with no text layer, so OCR
    of the page returns consonant salad -- not because the scan is poor, it is
    perfectly legible, but because it is the wrong way up and two pages wide.
    `tools/pd43_flatten.py` straightens them and that part is solved: the
    flattened 1971 page reads cleanly and the city table is found.
  * THE CITY TABLES RUN THREE LEVELS DEEP -- city, ward, precinct -- where every
    other table in the series runs two. Ward subtotals are now collected
    separately rather than counted as precincts, which stops them doubling the
    city, but the arithmetic still does not close on these volumes and until it
    does none of it should be trusted.
  * 1980 and 1984 find no table at all and are undiagnosed.

So: the modern half is finished and checkable; the 1970s half is straightened,
located and extracted, and is not yet worth publishing.

## Older still

The archive holds election statistics volumes back to 1901 -- the search that
found 32 volumes for 1970-2018 returned 184 items overall, with odd years right
through the 1900s to 1940s and beyond. Those are outside what has been fetched
and are a separate piece of work, but they are there, and the 1940s volumes are
the same publication in the same shape as the 1970s ones.

## What it agrees with

Checked against our own pre-2021 records, on 236 overlapping town-years:

    189 (80%)  ours lands EXACTLY on the PD43 figure
     23 (10%)  ours lands below it -- expected where Blanks were not printed
     24 (10%)  ours lands ABOVE it, which is impossible

Two independent sources agreeing exactly on four fifths of the overlap is worth
more than either alone. The 24 impossible rows are in `pd43/crosscheck.csv`,
worst first: Salisbury 2008 at 6.5x, Kingston 2016 at 6.0x, Boylston 2008 at
3.2x. Several also disagree on the date, which suggests the two sources are
describing different elections rather than disagreeing about one.

15 town-years are dated differently by the two sources. That is a free check
nothing else in this project could perform.
