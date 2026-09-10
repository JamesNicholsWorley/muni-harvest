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
