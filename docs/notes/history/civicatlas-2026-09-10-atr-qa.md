---
name: civicatlas-2026-09-10-atr-qa
description: "Unattended ATR QA run, 2026-09-10: publish 514 -> 657, nine records withdrawn as the wrong election, the locator re-ranked on ballot vocabulary"
metadata:
  node_type: memory
  type: project
---

# Unattended ATR QA run, 2026-09-10

What this run checked and what it concluded. The rung counts are over the 1,331
parsed pre-2021 sections, taken before and after.

    publish  514 -> 657
    review   328 -> 238
    hold     483 -> 430   (of which 317 still hold no contest at all)

The published folder went from 890 town-years to 961, with nine records
withdrawn from it.

## What moved, and why

**A blanks row turns marks under the line into a closed identity.** The seat
repair fired only ABOVE ballots x seats. Below the line it did nothing,
because marks short of the product is the ordinary shape of a return whose
blanks were never printed -- but that is true only while the blanks are
missing. Once a contest counts them its rows account for every position a
voter had, so the sum owes `candidates + blanks = ballots x seats` exactly,
and landing on `ballots x N` for another integer N is the seat count being
wrong. Amherst 2018 prints "SELECT BOARD ... TOTAL 6043" against 6043 ballots
and the parse recorded three seats. 206 seat counts repaired where 62 were
before.

**A quoted term of office is not a printed seat count.** Hamilton 2014 heads
its races "Selectman 3 years", "Town Clerk 3 years", "Housing AuthoritY 5
years"; all three close at exactly 1016 x ONE and all three were recorded as
printed seat counts of 3, 3 and 5 with the office line quoted as evidence.
Strip the term out of the quote and what is left has to still say how many.

**A column restated against every candidate is not a candidate.** Fairhaven
prints SUB TOT and TOTAL side by side with a Hand Counts line between them.
The parse read the TOTAL column -- which already contains the hand counts --
and each Hand Counts line as well. Worse, the single-row repair fired on
Selectman 2016, where the excess was 2, no Hand Counts row held 2, and the
genuine Write-Ins row did: it deleted two real write-in votes and left the
duplication in place. A name repeated inside one contest is the signal now,
and the group's removal has to close the contest to its own printed total.

**A ward is not the town.** `derive_ballots` excluded a regional district,
which spans several towns, and not a ward or precinct, which divides one.
Marlborough 2011 derived 847 ballots from Councilor Ward Six agreeing with
Ward Seven and then called the city's Mayor impossible -- 6002 marks in a
single-seat race, which IS the city's ballot count. Framingham 2015 prints
nothing but Town Meeting Members by precinct and derived 91 for a town of
72,000.

**A date a clerk actually wrote is a date.** Thirty-two records were withheld
for having no derivable date and most of them printed one: "31-Mar-03",
"15-May-18", "11/5/13", "7 MAY 2019", "Monday, the Second Day of May, 2016",
"TUESDAY, THE TWENTY NINTH DAY OF MARCH 2016". A month NAME between the other
two numbers fixes the order with no convention assumed. What was genuinely not
a date still is not.

**A question has no seats.** 59 contests were held for a null seat count and
are ballot questions. What makes one is on the rows and not the title: it is
answered yes or no. The rest are offices, and where the contest tallies its
blanks its own sum settles the count -- Amherst 2016's Charter Commission
prints "Blank 7666 / TOTAL 31419" against 3491 ballots, which is 3491 x 9.

**Ballot vocabulary decides which page is the return.** A town report names
its election four times: the warrant lists the offices to be filled, the
officers directory lists who holds them, the contents page indexes the result,
the minutes reference the date. All four carry headings and office words in
quantity and the return has no more of either; what it has and they do not is
Blanks, Write-ins, Total Votes, Precinct, Vote For. Measured over the 189 reports
refetched from Wayback and the State Library whose old cut held no contest,
the old order put a page of tallies inside its window 31 times and the new
one 103.

## What was withdrawn, and the line each was read on

Four sections are not annual municipal elections:

- Salem 2010 -- "CITY OF SALEM OFFICIAL ELECTION RESULTS / LIBERTARIAN /
  STATE PRIMARY SEPTEMBER 4, 2018"
- Ayer 2010 -- "Ayer Massachusetts Democratic Party Primary Election Results
  for Tuesday, September 14, 2010"
- Billerica 2020 -- the presidential primary, "PRESIDENT -Vote for One",
  Warren 1124, Sanders 2203, Bloomberg 974
- Palmer 2004 -- the November state ballot (President and Vice President,
  Representative in Congress, Sheriff) alongside Palmer's own council races

Four sections hold almost nothing the record claims:

- Carver 2014 -- the report's INDEX page. 0 of 13 names, 0 of 22 figures
- Barnstable 2018 -- the Town Clerk's vital statistics. 0 of 10, 1 of 20
- Wilbraham 2018 -- the town meeting warrant. 4 of 18, 0 of 18
- Scituate 2017 -- a real return, of the SPECIAL TOWN ELECTION of September
  16, against a record describing the annual one. 1 of 14, 2 of 31

And Fairhaven 2017, whose Commissioner of Trust Funds sums to 560 against the
page's printed 559.

## Belmont 2018 is Holyoke 2021 again

It records "MICHAEL L WINNER 2103, BLANKS 19" for Moderator. Its page reads
"MICHAEL J WIDMER * 2103 99.20% / All Write-in Votes 19 0.90%". For Selectmen
it records Frederick C Minor 1928, Ella Von Brier Cushman 1903, Stephen H
Pore 1836, Frederick P Murphy 868; the page has Thomas Caputo 2107 and
Tommasina Olson 114. Layer 1 locates 2 of its 18 names.

The only thing keeping it out of the published set was three unreadable
figures, which is a bad reason to be safe -- and it is the answer to the
question this run was about to ask. 94 records are held for a single
unreadable figure in a write-in or all-others row that the contest's own
printed total implies is zero. Filling those in would have published Belmont
2018. They are left alone and the decision is the owner's, because it
collides with the rule that a value invented in a blank cell is the one error
arithmetic can never catch.

## What is still open

- **317 sections hold no contest.** 260 of their reports were refetched --
  216 were archive-hosted already and 47 of the 101 municipal URLs resolved to
  a Wayback capture of the same URL; the other 54 have no capture. 188 re-cut
  without OCR and 103 of those now reach a page of tallies. 71 are scans and
  need the OCR pass, which does not finish inside a session here. The cuts
  still have to be parsed, and that needs the API key this session does not
  hold.
- **42 contests quote a printed seat count the arithmetic contradicts.**
  Bourne 2017's "Brd of Health / 3 years vote for 1" runs three candidates and
  blanks summing to exactly 2 x 1103 ballots. The page and the figures cannot
  both be right and only a human decides.
- **102 records hold arithmetically impossible contests.** 46 exceed by twenty
  marks or fewer; 56 by more than 1%.
- **14 duplicate-claim pairs are scans with no text**, so grounding cannot
  break their tie.
