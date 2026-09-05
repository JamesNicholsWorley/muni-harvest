---
name: civicatlas-date-corroboration
description: "How a dateless CivicAtlas return gets cleared - corroboration is a permanent NOTE not an override, it can confirm a date but never supply one, and it must be read from the ARCHIVED capture because live clerk pages name the next election"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Closing the 2025 DATE holds (2026-08-19) needed a way to clear a return that is
complete and correct but never prints the day it was held. There is deliberately
**no override mechanism** in this project, so the answer was to extend the
existing `DATE_FROM_FILENAME` precedent rather than invent a waiver.

**The mechanism.** `document.date_corroboration = {source, value, detail, quote}`.
`source=filename` was already there (`src/recover_dates.py`); `source=citation`
is new (`src/corroborate_dates.py`). The gate emits `DATE_FROM_CITATION` as a
**NOTE, on every run forever** — a corroborated town-year never stops saying its
date came from off the document. `parse_gate._corroborated` returns the dict now,
not a bool, and **requires both `detail` and `quote` for non-filename sources**:
an outside claim with no citation is not even a citation.

**The load-bearing limit: a corroboration confirms a date, it can never supply
one.** It answers "nothing backs this date," not "there is no date." A record
asserting no date at all (Holbrook 2025 — 24,508 chars, zero dates anywhere)
cannot be corroborated into having one. A source naming a *different* date is a
**contradiction, not a corroboration** — it means the parse is wrong, and it is
refused loudly rather than written quietly.

**Why the live site is the wrong place to look.** A clerk's election page is a
notice board, not an archive. Asked today, hopedale-ma.gov answers `Tuesday, May
12, 2026` — correct and useless for a 2025 town-year. Agawam's answers with a
2026 state primary. Reading a live page for a past date is the same error as
reading a date out of a URL. `src/wayback_election_date.py` reads the **archived
capture** from a window 120 days before to 60 days after the asserted date, and
reuses `parse_gate._date_on_page` so a town-year can never be cleared by a looser
rule than the one that held it. See [[civicatlas-proximity-not-aboutness]] and
[[civicatlas-citation-not-source]].

Two traps hit while building it, both already-known classes recurring:
- The quote window used `str.find`, so it quoted the page's *posting timestamp*
  instead of the occurrence that scored — the identical bug that nearly reverted
  a correct rule a day earlier. Fix it where the quote is produced.
- A rate-limited Wayback query reported twelve towns as "no archived page states
  this date". **An index refusing to answer is not the index saying no.** The
  miss reason now distinguishes unchecked from checked-and-empty.

---

*Revised 2026-09-05 by the owner during the migration review. The correction is his; the note is otherwise as originally written.*
**Correction: corroboration CAN supply a date.** The original rule -- that it may confirm a
date but never supply one -- is too strict. Documents carry dates other than the election's
own heading: a certification date, a date results were published, a clerk's attestation.
Those are evidence of when the election happened, not merely agreement with a date already
held.

Massachusetts municipal election dates are also highly standardised, which narrows the room
for error: a town votes on a known weekday in a known window, and a candidate date that does
not fit that pattern is suspect on its face.

What the original rule was really protecting against still stands: a date read from a LIVE
clerk page, which names the next election rather than the one in hand. Read the archived
capture. The problem was never that corroboration is weak; it is that a live page is.
