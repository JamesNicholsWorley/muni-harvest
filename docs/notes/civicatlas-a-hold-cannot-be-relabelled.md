---
name: civicatlas-a-hold-cannot-be-relabelled
description: "setting coverage_state=no_source on a held row lasts until the next rebuild — reconcile_inventory maps the GATE's verdict back on; to close a hold you must change what the gate looks at (retire the document), not what the inventory says"
metadata:
  node_type: memory
  type: project
---

2026-08-24, closing the 20 holds the Ingest 5/6 batches left. **pending_parse 20 -> 0**,
published 1775, 91.4% town-years / 97.1% people-years.

**THE MECHANISM THAT MATTERS.** I first closed twelve of them by writing
`coverage_state=no_source` onto the inventory row with a reason. It survived exactly until the
next `src/rebuild` -- `reconcile_inventory` maps the GATE's verdict onto the row, the gate
still said HOLD, and eight came straight back. That is the two-authorities rule working: the
gate reads the artifacts and decides, the inventory records what it decided. **A hold cannot
be argued away in the inventory.** To close one you must change what the gate is looking at --
retire the document (and parse) to setaside. `src/retire_unclosable_holds.py`.

Corollary: `data/setaside/register.csv` wants a REAL path per file, not a `stem.*` glob --
`register files are present` is a blocking check and a wildcard fails it. One row per file.

**HOW THE 20 SPLIT.** 8 were fixable, 12 were not:
- 5 printed their own date and were held only because nothing had read it (Hawley 2021,
  Holland 2024, Merrimac 2021, Norton 2021, Rochester 2026)
- 3 news pieces dated by their own publication: each says "Monday's election" and carries a
  machine-readable publish date on a TUESDAY -> the Monday before. Same conjunction reasoning
  as Dracut 2021. Bernardston 2026, Granby 2024 admitted this way; **Hawley 2024 did not**,
  because its article prints no date at all, only the publish stamp -- derived is not read,
  and DATE_NOT_ON_PAGE is right to refuse it.
- 4 wrong documents (a media-access headlines page dated 2015; a crop of a SPECIAL STATE
  election; a news item whose parse claimed 2,678 races from 1,621 characters; a 344-character
  landing page)
- 4 real returns for the right town with no date anywhere and nothing to borrow one from

**A SPECIAL ELECTION THAT MIGHT HAPPEN IS NOT THIS ELECTION.** Rochester 2026's report ends
"If there is still a tie ... the vote will go to a special election or appointment by the
Select Board" -- a future conditional in a piece reporting the annual election. SPECIAL_AMBIGUOUS
fired on the words alone. Added `_FUTURE_SPECIAL` to parse_gate (modal + "go to/require/
trigger ... special election") raising NOTE `SPECIAL_HYPOTHETICAL` instead. Corpus regression:
exactly +1 ADMIT / -1 HOLD, nothing else moved.

**TWO PARSE FAILURES THAT LOOKED LIKE DOCUMENT PROBLEMS.** Merrimac 2021 held EMPTY_PARSE
while its markdown plainly contained "MODERATOR John Santagate 91 120 211" -- a re-parse of
the same bytes gave 12 races and ADMIT, for $0.01. Norton 2021 held at 45% grounding because
its return spans TWO pages and the first is an image; OCR of that page cleared it. Before
condemning a parse, re-run it and check whether the document is half image.

**A FOURTH MARKED BALLOT, and rotation cost four digits.** Holland 2024 read sideways gave
Molle 219 / Alden 227 / Gumlaw 227 / Tax Collector 202; upright they are 216 / 221 / 229 /
209. Always re-render upright before transcribing. Tax Collector 209+53=262 against 263
ballots is the kind of internal check to look for.

Related: [[civicatlas-two-authorities-drift]], [[civicatlas-ungrounded-is-unread]],
[[civicatlas-atr-is-a-town-habit]].
