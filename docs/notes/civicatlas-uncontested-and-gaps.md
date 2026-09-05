---
name: civicatlas-uncontested-and-gaps
description: "Leverett 2025 \"disappeared\" because NO_TALLIES fired on an all-uncontested return and reconcile then wrote no_source over 134 town-years whose PDF was on disk; also the Worthington crop lesson"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

> **Schema note, 2026-09-05.** This note predates the retirement of the `-1` and
> `-3` sentinels. Wherever it says `votes = -1`, the corpus now holds
> `votes: null` with `status: "uncontested"`; `-3` is `status:
> "write_in_winner"`. The reasoning below is unaffected -- only the spelling
> changed.

CivicAtlasMA, 2026-08-19. Two rules I wrote took a COMPLETE record out of the corpus,
and it looked like a collection gap.

1. `NO_TALLIES` fired on Leverett 2025. Leverett elects its officers on the floor of
   town meeting, so the return carries twelve names and no counts — every candidate at
   `votes = -1`, which is the schema for an uncontested winner, NOT a missing number.
   `parse_gate._check_substance` now skips NO_TALLIES when EVERY candidate carries -1.
   18 town-years corpus-wide are all-uncontested like this.
2. `reconcile_inventory.py` read that hold as "not a result" and set `no_source` on
   134 town-years whose document is in `data/pdfs`. The NOT_A_RESULT branch is now
   `and not held(stem)`.

**Why:** "this document is not a return" and "we have no document" are different
statements, and only the first is a gate flag's to make. `coverage_state` is about our
holdings; asserting no_source over a file on disk is simply false. See
[[civicatlas-citation-not-source]].

**How to apply:** when a record vanishes, suspect a rule before suspecting the
collection — and check the disk, not a column. Same family as the signature defect in
[[civicatlas-doc-fingerprints]]: a name trusted as the thing.

Worthington 2025 adds the other half: cropping a ballot photograph into overlapping
500-dpi regions made hand-written counts readable and it parsed 9 races — but the
re-parse misread 4 of 11 figures, a surname and the date. **Grounding proves a reader
looked at the page; it does not proofread it.** Verify handwriting digit by digit
against high-dpi crops, keep the crops in `qa/outputs/pages/` as the evidence (the
verifier exempts vision reads from the quoted-span test), and re-run
`qa/fingerprint_sources.py` after replacing ANY document or the old notes report as
false quotes instead of superseded. Also: a crop region that stops short is data loss —
the first cut sliced off the turnout block.
