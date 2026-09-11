# Reading PD43, and what it cost to learn

Public Document 43 is the Secretary of the Commonwealth's printed election
statistics: 32 volumes, 1970-2018, in the State Library's DSpace. Town tables
from 1986; cities only in the annual volumes to 1983. It is the only source this
project has for municipal registration and turnout before 2012.

Each of the following was a day's confusion, and each looked like something else
first.

## A silent failure reports a percentage

Tesseract is installed on this machine but the Windows installer leaves it off
PATH, so every OCR call raised `STATUS_DLL_INIT_FAILED`. The parser caught that
per block and logged it, so runs finished and printed a completion figure. 1986
reported **73.3%** while five of the eleven pages of its town table -- every page
that exists only as an image -- had produced nothing at all. Forty-two
consecutive towns were missing, Chelsea through Florida, and no number said so.

**A page that needed OCR and did not get it is not a gap, it is a lie.**
`pd43_turnout` now locates the binary itself and exits non-zero with a banner
rather than letting the run look complete.

## Measure against the towns, not against the rows you managed to produce

`usable / rows produced` only counts municipalities that got as far as producing
a row. A town whose page was never read produces nothing, never enters the
denominator, and its absence reads as success. That is how 1986 scored 73.3%
while holding 121 of about 300 towns.

About 300 Massachusetts towns hold an annual election. That is the denominator,
and it does not depend on how much of the volume we managed to read.

## Missing towns cluster alphabetically when you are losing PAGES

The table is alphabetical, so the shape of what is missing names the cause. 191
of 1986's 235 missing towns sat in consecutive runs -- one of 42, one of 33.
Individual parse failures do not do that. Scattered singles mean the parser;
long runs mean whole pages or blocks were never read.

## Ink distinguishes a blank page from an unread one

Two very different pages both have no text layer. 2008 page 34 carries two
characters because it is a **blank sheet** with a running head and bleed-through.
1986 page 17 carries 123 because it is a **full table printed as an image**.
Counting characters cannot tell them apart, and selecting on the character count
puts the blank pages at the top of the list of pages to investigate -- and
overstates every image-only statistic, because empty sheets get counted as
unread tables.

A printed table inks 2-9% of the sheet; a blank page a fraction of one per cent.
Across 1986-2018 there are **eight** genuine image-only table pages, not dozens.

## The figures are never the problem. The names are.

On every page tried, OCR reads the numbers accurately and the trouble is always
the label column. That asymmetry drives everything:

- A row whose name is lost does not vanish quietly -- it becomes a **precinct of
  the town above**, so one lost name costs two towns and breaks an arithmetic
  check that would otherwise have passed.
- `rows_from_ocr` once took the single label token nearest in y, so a row's name
  was whichever of `Abington`, `May` and `24` sat closest. When it took the
  month, `TOWN.match` accepted it and a heading called `May` opened. 1986 held
  four such phantoms -- March with 78 precincts, April 59, May 38, UNKNOWN 38 --
  213 rows swallowed between them. Those are precisely the undivided towns the
  volume says are there: *"single-precinct towns: 44 found, the volume states
  142"*. That log line is the single best indicator of this failure.
- The dot leaders (`Abington .......... May 9`) look like the culprit and are
  not. Cropped to its own column the name reads cleanly; it is only when the
  whole block is read at once that the columns bleed and the name is lost. What
  the leaders do mangle is `Pct. 1`, which costs a precinct number and nothing
  else.

## Find the columns from the figures, not from the heading

`ocr_column_bands` read the heading, and on a page whose heading is illegible it
returned x 80-402 of a 668-wide block -- the width of the heading text, not of a
column of numbers. That left a 70px label column holding only margin, so a page
whose 84 rows of figures OCR'd perfectly yielded **no towns at all**.

Take the columns from where the numbers are. And cluster rather than splitting at
the widest gap: the widest gap on these pages is between the **precinct numbers**
and the figures, because `Pct. 1, 2, 3` are numbers too. The figure columns are
the two **rightmost** clusters.

## A period is a thousands separator

These tables count people; nothing in them is fractional. The scans render the
comma as a full stop constantly -- `1.639`, `10.385`, `6.946`. `num()` rejected
them, which dropped the figure **silently**: the row survived with a hole in it,
the precincts no longer summed, and the town was discarded for failing a check it
should have passed. 1986 Acton lost two of its six precincts that way.

## A year in a date must follow a comma

The date column prints `May 6` with no year -- the year is in the page heading --
so an optional trailing `(\d{2,4})?` does not find a year, it finds the
registered-voter count in the next column. `Millis May 6 4212` parsed as
"May 6, 4212" and ate the town's own figure. Millis and Monroe were read
perfectly off the page and emitted empty.

## Neither row reader wins everywhere

The words layer rescues volumes whose table detection collapses (1996: 51.6 ->
77.2%) and wrecks the ones where detection was working (2012: 99.3 -> 77.7%,
2006: 91.9 -> 61.4%). Run both and keep whichever closes more of its own
arithmetic. That is the same test used to choose a column split, one level up.

## A check that cannot fire looks exactly like a clean corpus

The population guard in `pd43_outliers` keyed on `(municipality, year)`.
`config/population.csv` is `community,population` and has no year column, so
every lookup missed, the `KeyError` was swallowed, and the check never fired
once. Andover 1988 passed it at 43,351 registered voters. It now refuses to run
rather than parse to nothing.

## What an agent is good for here

- **Text of a broken page: useless, but diagnostic.** Asked to reconstruct 1994
  page 20 from its text layer, a Haiku agent reported 9 towns and 53 precinct
  rows labelled against 9 numbers, and refused to align them. That was correct --
  the figures are not in that text layer -- and it is what exposed the
  figure-starved-page bug.
- **Images: reliable, with the arithmetic done outside the agent.** Given
  cropped pages, agents transcribed exactly, flagged the 1994 volume's own
  `1, 2, 2, 3, 5` precinct typo rather than renumbering it, and matched
  Tesseract digit-for-digit on a page both had read.
- Never ask the agent whether its own figures add up. Compute it outside.
- A town straddling the column break has its precincts in one block and its
  total in the one before. That is not a transcription error and must not be
  scored as one; merge the blocks, then check.

## Odd years

The biennial volumes do carry some odd-year elections -- Barnstable's 1994 entry
is dated `November 02, 1993` -- and they name the towns that never appear:
*"Agawam ... Town election only in odd-numbered years"*.

## Volumes that will not yield

1980 and 1984 have no municipal turnout table in readable form. Their only
legible heading belongs to a **party enrollment** table whose OCR is unusable
(`Hst^NCOOHH`). 1971 and 1979 are image-only throughout.
