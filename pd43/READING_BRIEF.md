# Reading PD43 turnout figures off a cropped page

This is the whole job, self-contained. You do not need the volume, the parser,
or any knowledge of Massachusetts. Everything you need is in the image.

## What you are reading

Public Document 43 is the Massachusetts Secretary of the Commonwealth's printed
election statistics. The table is headed **Registered Voters / People Who
Voted**, and it lists municipalities alphabetically.

Each municipality appears as:

    Abington .......... May 11          8,060     1,676
      Pct. 1 .........                  1,955       407
          2 .........                   1,672       357
          3 .........                   2,104       451
          4 .........                   2,329       461

- the name, dot leaders, the election date, then **Registered Voters**, then
  **People Who Voted**
- beneath it, indented, its precincts: `Pct. 1`, then bare `2`, `3`, ... Some
  volumes use letters (`Pct. A`, `B`).
- small towns have **no precincts at all** and only the one pair of figures

Two column blocks usually sit side by side, separated by a vertical rule. Read
the left block top to bottom, then the right.

## The check that tells you whether you got it right

**A municipality's precincts sum to its own two figures, in both columns.**

    1,955 + 1,672 + 2,104 + 2,329 = 8,060   registered
      407 +   357 +   451 +   461 = 1,676   voted

If your reading does not add up, you have misread a digit. Go back to the image
and find which one. This check is the entire quality control, so run it on every
municipality that has precincts.

## Rules that matter more than completeness

1. **Never adjust a figure to make a sum work.** If it still does not sum after
   you have looked again, report the figures as printed and say it did not sum.
   A wrong figure reported honestly is far more useful here than a figure
   quietly corrected, because the honest one can be found and fixed and the
   corrected one cannot.
2. **Transcribe what is printed, including mistakes.** The 1994 volume prints
   Bellingham's precincts as `1, 2, 2, 3, 5`. That is the document's own typo.
   Transcribe it as it stands; do not renumber it.
3. **Illegible means ILLEGIBLE.** Write that word rather than guessing. A guess
   that happens to sum is the one error nothing downstream can catch.
4. **Do not drop a municipality** because it is hard. Emit it and say what went
   wrong.
5. **Ignore municipalities that are only partly visible** at the very top or
   bottom edge of the crop — they are there because the crop is rectangular, not
   because they are yours to read. Read only the ones you were asked for.

## Things the scans do

- `Pet.` is `Pct.` — the c scans as an e. Likewise `Pet. 1` for `Pct. 1`.
- Thousands separators are sometimes printed or scanned as a period: `10.385`
  is **10,385**. Normalise to no separator at all in your output.
- A `1` can scan as `l` or `I`, and `0` as `O`.
- Dates may carry no year (`May 6`) or a full one (`May 07, 1994`). Transcribe
  as printed.
- Some entries in a volume are dated in the **previous** year. That is correct
  and not an error: Barnstable's entry in the 1994 volume is dated
  `November 02, 1993`.

## Making a crop

    python tools/pd43_crop.py --year 1994 --town Amherst

writes `pd43/crops/1994-Amherst.png` — that municipality's rows with the column
headings attached above them. Use `--worklist pd43/worklist.csv --limit N` to
cut a batch. Never open the whole volume; it is six hundred pages and you do not
need any of them.

## Output

CSV, one row per municipality and one per precinct:

    municipality,year,date,level,precinct,registered,voted,sums_ok

- `level` is `total` for the municipality's own row, `precinct` for a precinct
- `precinct` empty on total rows, otherwise the printed label
- `date` only on total rows, as printed
- figures with no commas or periods
- `sums_ok` on total rows only: `yes`, `no`, or `n/a` where there are no
  precincts to sum

Report, in your final message: how many municipalities you emitted, how many
have `sums_ok=yes`, the name of every one that did not sum, and anything
illegible or ambiguous. That final text is a data return, not a message to a
person.
