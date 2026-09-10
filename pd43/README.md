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

22 of the 32 volumes are read. `config/pd43_turnout.csv` holds 4,322 town-year
rows and 18,486 precinct rows, with 3,927 election dates and 114 towns stated as
holding no election that year.

TEN VOLUMES ARE NOT READ, and each for a nameable reason rather than a general
difficulty:

    1971 1973 1975 1977 1979   the odd-year booklets have NO TEXT LAYER AT ALL --
                               not even a heading to find, so the table cannot be
                               located before OCR rather than after it
    1978 1980 1984             the heading is worded differently: `Number of
                               Persons Registered and People Who Voted At
                               Elections`, not `Registered Voters and People Who
                               Voted`, and in title case
    1972 1976                  a heading is found but the table extent is
                               rejected; undiagnosed

The five odd-year booklets are the ones that matter most, because they are the
only volumes in the series covering CITY elections and odd-year town elections.
Reading them means OCRing a page to decide whether it is part of a table, which
is the reverse of the current order and wants a cheap first pass -- the top strip
of each page is enough to find a heading.

## What it agrees with

Checked against our own pre-2021 records, on 236 overlapping town-years:

    189 (80%)  ours lands EXACTLY on the PD43 figure
     23 (10%)  ours lands below it, which is expected where Blanks were not
               printed and the undervote is therefore missing from the tally
     24 (10%)  ours lands ABOVE it, which is impossible and means one of the two
               readings is wrong

Two independent sources agreeing exactly on four fifths of the overlap is worth
more than either of them alone. The 24 impossible rows are in
`pd43/crosscheck.csv`; the worst are Salisbury 2008 (6.5x), Kingston 2016 (6.0x)
and Boylston 2008 (3.2x), and several of those also disagree on the date, which
suggests the two sources are describing different elections rather than
disagreeing about one.

15 town-years are dated differently by the two sources. That is a free check
nothing else in this project could perform.
