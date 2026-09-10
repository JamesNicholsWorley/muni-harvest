# pd43/

Public Document 43 is the Secretary of the Commonwealth's printed election
statistics. Its local-election tables give, per municipality and per precinct:
the date of the election, the registered voters, and the number of people who
voted. That is the denominator this project has never had for the years before
2021, an independently published ballots figure to check our own against, a date
to check our parse against, and -- from the towns printed `ODD YEARS ONLY` -- an
authoritative statement that a municipality held no election that year.

The volumes are large scans and are not committed.

    python tools/pd43_fetch.py --list
    python tools/pd43_fetch.py --years 2000,2008 --dir pd43
    python tools/pd43_turnout.py pd43/pd43-2008.pdf --year 2008 --out pd43/out-2008.csv
    sh tools/pd43_all.sh                       # every volume, strong ones first
    python tools/pd43_combine.py "pd43/out-*.csv" --out config/pd43_turnout.csv
    python tools/pd43_crosscheck.py --records <civicatlasma>/json_pre2021

## What the series covers, and what it never will

    1970-1983   annual. The odd-year volumes are given over to local elections
                and tabulate CITY elections -- by ward and precinct, with
                preliminaries -- as well as town ones.
    1986-2018   biennial, even years only, TOWNS ONLY. Each volume covers its
                own even year and no other. Cities elect in odd years and are
                not tabulated at all: the 2008 volume counts 39 cities and 1,050
                city precincts in its summary and prints none of them.
    1985-2019   the odd years are not in the archive. The Secretary's position
                now is that local election turnout is not reported to the
                Elections Division at all.

So odd-year town elections and every city election from 1985 on are not in this
series and are not going to be. That is a permanent gap in this source, not a
backlog.

The archive holds election statistics back to 1901, in the same shape. Those are
a separate piece of work and have not been fetched.

## Everything is checked by the page's own arithmetic

The precinct rows sum to the TOTALS row, so nobody has to read a page to know
whether it was read correctly. `status` in the output is the verdict:

    checked      precincts sum to both printed totals
    single       an undivided town; one figure, nothing to cross-foot
    no_election  the volume states the town does not elect this year
    reg_only     registered voters sum, people who voted do not
    voted_only   the reverse
    no_total     no TOTALS row could be read
    mismatch     the precincts do not sum to the printed total
    hierarchy    a city table three levels deep whose sums do not close

**Only `checked` and `single` are fit to become denominators.** The rest are kept
and marked, because a gap that is written down is not the same as one that is
filled.

## Reading the page: try, don't guess

The hard part is not the figures, it is finding where the columns are. Every
rule for placing the gutter from the page alone was wrong somewhere:

  * the widest gap in the middle third splits INSIDE the right-hand block;
  * a profile of how many rows cross each column -- which is what a gutter
    actually is -- lands at 218 where the gutter sits at 260, because over sixty
    rows of dot leaders no column is left alone and the quietest is not the one;
  * the page's own reading swings 245-293 across one table, and a reading fifty
    points out does not shift a column, it swallows one;
  * the table's median fixes that and discards the pages that really did shift.

So the page is read several ways and scored, and the scorer is the arithmetic
that was already there: a split through the wrong place produces towns whose
precincts do not sum. On 2008 that took 275 municipalities and 127 verified to
308 and 166, against 310 municipalities named anywhere in the volume.

Three other things had to be true before a volume would read at all:

  * SOME PAGES ARE SINGLE-COLUMN. The 1970s volumes set the table as one block
    across the page; halving it cut every row in two, name and date on one side,
    figures on the other. The figures were being read correctly the whole time.
  * SOME SCANS ARE SIDEWAYS AND TWO-UP. Each page of the 1971 booklet holds two
    printed pages rotated ninety degrees with no text layer, so OCR returned
    consonant salad -- a legible scan, the wrong way up and two pages wide.
    `tools/pd43_flatten.py` straightens it.
  * THERE ARE THREE HEADING SHAPES. `REGISTERED VOTERS AND PEOPLE WHO VOTED`
    from 1981; `Number of persons registered and people who voted at Elections`
    in the 1970s, in title case; and in 1973-79 no such phrase at all -- the
    table is titled `City Elections in 1973` and the columns are ruled
    `Registered Voters | Persons who voted`.

Tesseract needs `--psm 6` for these pages. Under its automatic segmentation it
decides the ruled label column is furniture and discards it: one token from that
column against 103, so every town loses its name.

## What it agrees with

Against our own pre-2021 records, on the invariant that our derived ballots
figure can fall below the true one but can never exceed it:

    189 (80%)  ours lands EXACTLY on the PD43 figure
     23 (10%)  ours lands below it -- expected where Blanks were not printed
     24 (10%)  ours lands ABOVE it, which is impossible

Four fifths exact between two sources sharing no code, no method and no author.
The impossible rows are in `pd43/crosscheck.csv`, worst first. Several also
disagree on the date, which suggests the two are describing different elections
rather than disagreeing about one.
