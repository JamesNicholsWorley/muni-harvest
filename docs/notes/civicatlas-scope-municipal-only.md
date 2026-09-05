---
name: civicatlas-scope-municipal-only
description: "CivicAtlas records ONLY annual town/city elections — state elections and primaries are WRONG-DOC even if a municipal-looking race appears on them; but EVERY local office on a municipal ballot is in scope, fire and water districts included"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CivicAtlas is about **annual town and city elections for municipal offices**. Anything else is
WRONG-DOC, with no balancing test:

- State election / primary returns (`PROCEEDINGS OF STATE ELECTION`, `STATE PRIMARY`) — wrong doc
  **even when they carry a genuine regional school committee race**. A municipal-looking race riding
  along on a state ballot does not convert that ballot into the town's annual election.
- News articles about an election are not returns of it (see [[civicatlas-qa-standard]]).

**CORRECTION, owner decision 2026-08-13 — districts are IN scope.** This memory previously said
special-district ballots were WRONG-DOC. That was wrong, and it generalised from one case. The
owner's rule is: *"we are interested in any local office that appears on a municipal ballot, which
does include fire and water districts; the one we excluded earlier was only because it was a special
election."* `ADAMS FIRE DISTRICT SPECIAL ELECTION` was excluded for the word **SPECIAL**, not the
word **DISTRICT**. Prudential Committee, Water/Fire Commissioner, District Clerk and District
Treasurer are municipal offices and belong in the record — 23 such races already sit in published
town-years (Acton, Dennis, Carver, Northfield) and D5 has correctly never flagged one. Recorded in
`qa/STANDARD.md` under D5. Do not reintroduce a district exclusion.

**Why:** I stalled on Adams2024 and Upton2022 as "standing scope questions" and asked the user to
decide. They were not close calls. The user's reaction: *"this project is so obviously focused on
annual town/city elections for municipal offices."*

**How I made the mistake — the actual failure mode, worth not repeating:** I let a *partial* match
on a secondary attribute outvote the primary one. Upton2022 is headed `PROCEEDINGS OF STATE
ELECTION` — that alone settles it — but I found real BVT Regional School Committee races inside and
treated the document as mixed, so "not a clean WRONG-DOC." I was scoring documents on *how much
municipal-looking content they contain* instead of asking **what election is this a return of**.
That is the wrong question, and it manufactures ambiguity out of documents that state their own
identity in their heading.

**How to apply:** Identify the document by its heading first; that answers scope on its own. Only
then look at contents. Don't escalate a scope call to the user when the heading already answers it
— and don't let interesting contents inside a wrong document argue for keeping it. Corollary that
did work: verify each finding against its own document rather than batch-clearing on a regex. A
sweep for `no winner`/`no candidate` across 11 A3 findings was right for 2 (Ludlow2023, genuine
`NO WINNER`) and wrong for 9 — Acushnet2024's phrase came from a news article, Charlemont2026's
from a campaign-finance $1000 threshold line.
