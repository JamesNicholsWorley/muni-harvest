---
name: civicatlas-arithmetic-cannot-see-a-lost-name
description: "sum==printed proves you read the NUMBERS, never the names; and it is a different test from printed%seats==0 — merging the two lets a clerk's own bad arithmetic suppress a perfect parse"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Writing coordinate parsers for the Needham and Milford 2025 precinct tallies.

**A lost NAME is invisible to an arithmetic check.** Needham Precinct D summed
exactly to the printed TOTAL while "Erin M. Doyle" had been dropped entirely —
her votes were captured, her name was not (name at y=565.4, numbers at y=565.6,
straddling a `round(y/3)` bucket edge). Found by eye, not by the sum. Fix: cluster
lines against a running line top with a tolerance, never bucket by rounding. And
after every such parse, grep the output for empty / address-shaped /
`<unlabelled>` names — the sum will not do it for you.

**Two different tests, do not merge them.** `sum == printed` asks whether *I*
read the block faithfully. `printed % seats == 0` asks whether the *town's*
arithmetic divides. Requiring both let Needham Precinct B's own off-by-two
(prints 6154; not a multiple of 8) suppress a perfectly-read race — the verifier
becoming the bug, cf. [[civicatlas-proximity-not-aboutness]].

Other traps these documents set, all found by dumping words with x/y
(`src/_band_words.py`) before writing any parser:
- an absolute x-window caught the *rank* column in one band — take numbers
  positionally, the column ORDER is constant across bands, coordinates are not;
- a name and its count do not share a line, and the ORDER is not fixed: a ballot
  candidate's 2-line cell puts the number 3.8pt BELOW the name, a write-in's
  1-line cell puts it 4.6pt ABOVE. Pair by NEAREST label in y, not reading order;
- column semantics vary WITHIN one document — Needham's hand count is inside the
  TOTAL where two columns print, outside where one does;
- when a row straddles a page break the PDF may print its number on BOTH halves
  (Milford, 4 precincts, each excess == the duplicated value);
- a running footer ("April 1, 2025") can drop a day-of-month into the number
  column.

Make y global across pages (`y + pno*1000`) before pairing anything.
