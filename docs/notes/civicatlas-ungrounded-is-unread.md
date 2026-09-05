---
name: civicatlas-ungrounded-is-unread
description: "vision-reading all 40 name-ungrounded CivicAtlas records found 9 materially FALSE and 3 with specific errors, so a record the surname check cannot ground is unread, not innocent; four named failure modes plus a per-precinct-explosion detector"
metadata: 
  node_type: memory
  type: project
  originSessionId: 57be485a-0d9f-4d72-84e8-24620dfea578
  modified: 2026-08-24T15:19:01.634Z
---

> **Schema note, 2026-09-05.** This note predates the retirement of the `-1` and
> `-3` sentinels. Wherever it says `votes = -1`, the corpus now holds
> `votes: null` with `status: "uncontested"`; `-3` is `status:
> "write_in_winner"`. The reasoning below is unaffected -- only the spelling
> changed.

2026-08-24. All 40 records in `logs/qa_unverified_names.csv` were read with vision
(render page to bitmap, compare published record to the page). Verdicts in
`logs/qa_vision_verdicts.csv`.

**Result: 9 WRONG, 3 with specific errors, 1 structural, 1 with no document, 17
verified exact, 9 not reached.** Roughly one in three of the records that were read
to completion was materially false.

**The lesson.** My earlier note asserted "nothing shows any of them to be wrong."
That was true only because nothing had looked — the check that flagged them is
precisely the check that could not read them. **A record the surname test cannot
ground is UNREAD, not innocent.** Neither "clean" nor "suspect" is the right
posture; the list is short enough to just read.

**Four mechanical failure modes, each detectable:**

1. **Column misread** — a rotated grid read down the wrong column, so every count
   is Precinct 1's figure not the total. Scituate 2022: Moderator published with
   498, true total 2,529.
2. **Per-precinct explosion** — one race becomes N race objects holding district
   counts, and the townwide totals are LOST. Norwood 2023.
3. **Handwriting misread** — hand-marked ballots used as tally sheets. Wales 2021,
   Wales 2023, North Brookfield 2021: essentially every number wrong, leading
   digits dropped (119→19), winners recorded with 0, candidates lost. But Wales
   **2025** is the same town, clerk and format and is perfectly correct — this is
   not a blanket property of hand-marked returns, so never condemn by format.
4. **Row shift** — Southbridge 2021 published the BLANKS figure (2,065) as David
   S. Adams's vote total. Related to the Brockton/Deerfield shift class in
   [[civicatlas-names-are-unchecked]].

Plus two fabrications where the parse invented a slate: New Bedford 2021's
"candidates" are spreadsheet column codes (RVT, EDO, IEA) with 13.75 votes;
Northbridge 2023 has offices named `WHITE IRISES` and `MICHAEL JOSEPH WILES`.
And Rowe 2024, whose whole record is one Governor's Councillor race — a STATE
office — with more votes than the town cast ballots, while 14 real races on a
perfectly legible page are missing.

**CORRECTIONS APPLIED the same day.** 7 records rebuilt from the page (Rowe 2024,
Scituate 2022, Northbridge 2023, Norwood 2023, Wales 2021, Wales 2023, North
Brookfield 2021), 4 repaired in place, 5 name slips fixed, New Bedford's parse
retired. Every rebuild is gated on arithmetic the CLERK printed and the loader
refuses to write a record that does not reproduce it -- Norwood's 35 races each
match its own TOTAL VOTE column. Norwood went 15 races (nine of them one race) ->
35, adding the 27 Town Meeting Member races the old parse omitted.

**THE OVAL IS NOT A DIGIT.** On a hand-marked ballot the write-in line ends with
the printed oval, and at high dpi it reads as a trailing zero (or turns 6 into 8).
I read North Brookfield's write-ins as 182 and 120; they are 162 and 12. The
arithmetic had already said so -- 630 ballots, and both cells overshot -- and I
talked myself past it, attributing one to the clerk and rounding the other. **When
a whole sheet closes exactly and one cell does not, the cell is the suspect, not
the sheet.** Only write-in rows are affected. The owner caught this, not me.

**Two more finds from chasing one hold.** Rowe 2024's return prints "Saturday, May
14, 2024" and 14 May was a TUESDAY; the weekday, the town's filename, and the 13
May town-meeting minutes all say 18 May, so only the day number is wrong. Those
minutes were registered in source_parts.csv as "the election results pages" and
are nothing of the kind -- a `land_atr_finds.py` mis-crop. Because `_pdf_native`
CONCATENATES source parts, `_best_layer` preferred 3,643 chars of town-meeting
prose over the scan's own OCR and the grounding check scored the election against
a document about fire districts. **A bad source part silently becomes the text
every content check reads.** Worth sweeping the register for others.

**ALL THREE HARD CASES CLOSED (same day).** Corpus back to ADMIT 1695 / HOLD 0,
95.2% people-years, blocking 13/13.

**A Diebold NAME HEADING CANVASS is decodable.** New Bedford 2021's headings are
DIAGONAL, not vertical: each WORD of a name is its own diagonal, one letter per
line stepping one character right, and all the words of one name start on the SAME
line. Every race's rightmost column decodes to WRITE-IN, which is how you confirm
the rule before trusting anything else. Read row-wise instead you get "RVT EDO
GTT" -- the fabrication. And the check I thought didn't exist does: beneath
CANDIDATE TOTALS the canvass prints CANDIDATE PERCENT, so recomputing each
candidate's share validates every total (33/33 here). Retiring first and decoding
second was right, but don't assume a canvass is unverifiable -- look for the
percent row.

**Dartmouth 2022: I was wrong TWICE, in opposite directions.** Called it
falsified, then corrected to "faithful, badly modelled" on seeing the document has
no townwide total column -- then actually computed the totals and found the races
that DID carry townwide numbers were wrong (Brooks published 2267, page sums
2766). Lesson: "the document has no totals" does not imply "the record's totals
are honest". Compute before concluding. Now stored with all nine precinct values
per candidate and totals COMPUTED, checked against each race's own printed row.

**A stem can be published with no PDF at all.** Hatfield 2026 had only raw_ocr and
the literal placeholder citation "wayback-recovery"; the document was sitting in
data/setaside/refetch_untestable/ and the town still served it live at the same
sha256. Check that directory before believing a document is lost. Its parse also
carried votes=-1 (the uncontested sentinel) on NINE races the return tallies in
full -- votes=-1 is worth auditing as a fabrication smell, not just a schema.

**MERGE the document block, never replace it.** Rebuilding three records wiped
verified `date_corroboration` that earlier passes had established -- Rowe's
2024-05-18 was already proven from the town's Goal Post newsletter, with the same
typo reasoning I re-derived from scratch. I only noticed because the gate then
held the record. A rebuild replaces the READING; the evidence gathered about a
document is separate and must be carried forward.

**New detector: `src/check_precinct_explosion.py`.** Signature = the same office
label across 3+ race objects that SHARE a candidate. Two races legitimately share
an office label (two seats, or 1-year vs 3-year term) but never a candidate —
nobody runs against themselves. Requiring the shared candidate is what separates
the defect from Town Meeting Member by precinct, which really is one race per
precinct with different people. Found Westport 2023 outside the 40: 72 race
objects for 12 offices because the document prints townwide totals AND five
precincts and both were ingested (inflates, does not falsify).

**Distinguish faithful-but-badly-modelled from wrong.** Dartmouth 2022 looked like
explosion, but its document is a precinct-column sheet with NO townwide total
column, so nine race objects genuinely reproduce nine precincts. Nothing false;
the defect is that one race publishes as nine with no aggregate. I called it wrong
before opening page 8. Open the last page before judging a table's shape.

**Brockton 2025 is now CORRECT** — its Mayor race matches the certified recount
exactly. The standing "Brockton passed clean with 6 of 7 names wrong" warning
describes a record that has been repaired; it still scores 0% only because rotated
column headers defeat OCR. Don't cite it as a live defect.

**Hatfield 2026 has NO PDF on disk** — only raw_ocr and the citation
"wayback-recovery". A published record with no artifact behind it should not sit
in ADMIT; see [[civicatlas-silence-is-not-a-default]].

Related: [[civicatlas-arithmetic-cannot-see-a-lost-name]],
[[civicatlas-ocr-is-not-the-page]], [[civicatlas-two-authorities-drift]].
