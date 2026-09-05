---
name: civicatlas-silence-is-not-a-default
description: "retiring a wrong document made the gate go SILENT on that stem, and coverage_state's default for silence was pending_parse -- so proving a document wrong made the corpus MORE confident about it; ground every optimistic bucket in an artifact on disk"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CivicAtlasMA, 2026-08-19. I quarantined 23 documents proven (by reading the page
images) not to be election returns. Removing them from `data/pdfs` removed them
from the gate's input, so `gate.get(stem)` became `None`. In
`src/coverage_state.py` a stem with `status: hosted` and no gate verdict falls to
`state = "pending_parse"`, and the stale-adjudicator guard then re-froze the
stored `pending_parse`. Net effect: **the coverage numbers did not move at all.**
Twenty-two town-years we had just proved were gaps still read as "document in
hand, parse queued."

**Why:** `pending_parse` is not a neutral unknown, it is a CLAIM — *we hold a
document and the only outstanding work is reading it*. Absence of a ruling was
being treated as evidence for that claim. There was already an invariant stopping
`published` without a `data/json/<stem>.json`; nothing guarded the bucket one
level down. This is [[civicatlas-two-authorities-drift]] with a new mechanism:
not two authorities disagreeing, but one going quiet and the other reading the
quiet as agreement.

**How to apply:**
- Every state that asserts something must be **grounded in an artifact on disk**,
  not in another authority's opinion. Fix added to `coverage_state.py`:
  `pending_parse` with no pdf AND no json -> `no_source`. Measured first: it moved
  exactly the 22, zero collateral (per
  [[row-predicate-cannot-bound-a-row-set]] — measure the set before mutating).
- When you REMOVE an input, ask what the consumer does with the silence. Deleting
  a row from a checker is not the same as the checker returning "bad".
- Symptom to watch for: a corpus-changing operation that leaves the headline
  numbers **exactly** unchanged. That is not stability, it is a stuck reading.

Result: published 1451 (unchanged — no published record was ever at risk),
pending_parse 206 -> 184, no_source 287 -> 309, reconciler 0/0/0.
