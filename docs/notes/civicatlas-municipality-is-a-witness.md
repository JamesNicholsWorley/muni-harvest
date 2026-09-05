---
name: civicatlas-municipality-is-a-witness
description: "In CivicAtlas the parse's municipality field exists only to DISAGREE with the filename stem — filling it from the stem silences the corpus's only wrong-town detector"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

`qa/civicqa/model.py` deliberately keeps two town fields apart: `Doc.municipality`,
taken from the filename stem and commented *"authoritative label"*, and
`Doc.parsed_municipality`, taken from the document. **The second exists only to be
able to disagree with the first.** That disagreement IS `check_wrong_town` (D1) in
`qa/civicqa/checks.py`, and it is how Russell2023 — filed under Russell, parse says
"Town of Oxford" — was caught.

So `municipality` inside a parse is not a label to be tidied. It is a witness.
Copying the stem into it guarantees agreement, D1 can never fire on that document
again, and the record then *looks* corroborated while carrying no evidence at all.

**`src/backfill_municipality.py` did exactly that copy, corpus-wide.** Measured
2026-08-20 via `src/municipality_witness.py`: **1279 WITNESS / 299 ECHO**, where an
ECHO asserts a town that appears nowhere in the document text we hold — 261 of them
ADMIT and publishable. Nothing in the record distinguishes an echo from a real
reading. That script is now retired in place and `sys.exit`s if run.

**The right handling of an unreadable town is NULL, not the stem and not
`"<UNKNOWN>"`.** Both D1 and F2 already skip a falsy value, so null reads as "no
witness", which is exactly true; `"<UNKNOWN>"` is a model's shrug that we were
about to publish. `src/fix_placeholders.py` is the replacement — it fills only
where the document itself names the town, keeps the matched span as evidence, and
nulls the rest (35 filled, 438 nulled of 473).

Two traps found alongside it, both in `qa_2025.district_of`:
- **A term length is not an electorate.** 458 races put "Three Year Term" / "3yrs"
  in `district_original`, so each spelling became its own electorate and those
  races never joined their town's ballot reference — no arithmetic could reach
  them. Fixing it moved ARITH_THIN 103→84 and corrected 3 more seat counts.
- **`<UNKNOWN>` in `district_original` means there was NO district**, proved by
  South Hadley 2025 carrying real "Precinct A".."Precinct E" on its 8 TMM races and
  `<UNKNOWN>` on its 10 townwide ones.

Caveat worth keeping: an ECHO is a known *absence of corroboration*, not a known
error — most of these towns are filed correctly and the name simply lives in a
letterhead image rather than the text layer.

Related: [[civicatlas-doc-fingerprints]], [[civicatlas-parse-identity-checks]],
[[civicatlas-silence-is-not-a-default]], [[civicatlas-num-winners-is-the-weak-field]].
