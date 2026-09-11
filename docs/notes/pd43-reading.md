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

## Find the towns in the arithmetic, then attach the names

Every reader written for this table keyed its structure on the labels, and the
labels are the part that fails. Walking the registered column instead -- where a
value equals the sum of the next k values, that value is a town total and those
k are its precincts -- establishes the structure without anything having to be
spelled correctly. A name that then fails to snap costs that one town, instead
of turning it into a precinct of the town above and costing two.

**Both layouts occur and the series never says which it is using.** 1986 and
1992 head the precincts with the total; 2000 and 2012 close them with a TOTALS
line. Scanning forward only, not one sum closed on a perfectly legible page of
2000. Try both directions at every row, and prefer a run that closes in BOTH
columns: a coincidence in one column is common on a page of four hundred
numbers, in two at once it is not.

**In the totals-last layout the label on the total row is the word `TOTALS`.**
The town's name heads its precincts. Reading the name off the row that carries
the figures -- correct for 1986 -- returned `TOTALS` for every town in 2000,
2012 and 2016, so those volumes produced no municipalities at all while their
arithmetic was closing perfectly.

**Where the arithmetic cannot close, the labels finish the job.** A row printed
TOTALS is a town total by the table's own say-so, and its figure is printed
whether or not its precincts add up to it. Framingham's neighbour on 2012 page
20 lost the leading 1 of `1,877` in the text layer; the total 5,671 was read
perfectly and was being discarded because the check it failed was being used as
the reading rather than as a check.

## The column split lands inside the right block's names

It is found from the widest vertical gap in the page's text, and that gap sits
between the left block's last figure column and the right block's dot leaders --
a little to the RIGHT of where the right block's names begin. `Huntington` came
out `ngton`, `Ipswich` as `+h`, `Longmeadow` as `neadow`. Sixteen towns on one
block of 1986 page 20, read perfectly and emitted nameless.

The margin is only safe in that direction. Widening the LEFT block the same way
joins the two blocks' names on every row -- `Hanson Hull` snaps to nothing.

## Nine towns contain a month

`snap` strips the election date off a label -- `Abington ..... May 24` --  and
did it by matching three letters of a month followed by `\w*`. Nine
Massachusetts municipalities contain those three letters:

    Marblehead  Marion  Marlborough  Marshfield  Maynard   ->  ''
    Hanover -> 'Ha'     Saugus -> 'S'     New Marlborough -> 'New'

Unreadable in every volume, by both readers, for as long as the pattern existed
-- and silent, because a name that snaps to nothing looks exactly like a name
the scan lost. The month has to be a whole word, not followed by a letter.

## A bare four-digit year is a date -- in the text layer only

From 1994 the date column prints the year, in the x band a figure would occupy.
Twenty-one towns in 2008 and Marblehead in 2012 came out registering 2008 and
2012 voters. The table separates its thousands, so two thousand prints `2,012`
and the year prints `2012`: that is the discriminator, and it is the volume's
own typography.

**It does not survive OCR.** Tesseract drops the comma constantly, so a town
that registered 1,986 voters in 1986 comes back as `1986` and the same rule
deletes a real figure -- which does not cost one row, it breaks the arithmetic
for the whole town. Applied to OCR as well, this took 1986 from 92.8% back to
90.2% and 1992 from 92.2% to 87.6%. On the OCR side the date is caught as a
COLUMN instead: a figure column does not print the same value on every row.

## Section boundaries: thirty-two volumes is a bounded job, so read them

Detection was wrong three different ways and each fix broke a volume the
previous one had got right. The longest run of consecutive headings picked the
CONTENTS page in 2014 and 2018, because the table prints its heading once and
the contents lists it twice. Extending on content swept 1983's city table into
its town table. Stopping at the first unreadable page cut five pages off 1988
and 2000 -- and those are the pages that most needed reading.

`config/pd43_sections.csv` now carries ranges someone has looked at, with what
is on the pages either side. Three things fell out of reading them:

- **The 1982 volume tabulates the 1980 town elections.** Its running head says
  so on every page of the section, and no other volume reports a year other
  than its own. Those rows had been coming out labelled 1982.
- **The 1980 and 1984 volumes have no town table at all.** Both run Summary of
  Election Statistics straight into Party Enrollment. So the 1982 town
  elections are absent from the volumes held -- a fact about the series, not a
  parser failure.
- **1978 and 1979 are printed landscape and stored rotated 90 degrees**, which
  is the whole reason their text layers read as noise (`5)Z ^n-I inncvjo`,
  `00 r- ON c _o o 1) UJ`). Rendered upright they OCR cleanly: 1979's town
  table is p31-p47, 1978's p28-p43. 1978 prints FOUR figure columns -- town
  registered and voted first, state registered and voted second -- so the
  two-rightmost-columns rule would read the state election there.

## Select pages for OCR on whether the text carries the FIGURES

Not on characters, words or ink. 1973 page 38 extracts 129 words: every town
name, every precinct number, every dash, and exactly one number. By every count
of quantity it is a readable page.

Ink cannot do this job across volumes at all. It was calibrated on the
1986-2018 scans, where a table inks 2-9% of the sheet; the 1970s booklets are
lighter and smaller, and a full table page there measures 0.3% -- less than a
blank sheet in 2008. An absolute ink threshold is a threshold on scan quality.
