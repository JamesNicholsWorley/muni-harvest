---
name: civicatlas-two-authorities-drift
description: "coverage.html and the gate had drifted with nothing checking them; a measure-only reconciler found it in minutes, recomputing from the stale adjudicator would have claimed documents that do not exist -- and the drift RECURRED in the rendered HTML because the invariant guarded only the coverage_state column"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CivicAtlasMA had two programs answering "what do we publish" with no link between
them: `reports/coverage.html` counts `coverage_state` in master_urls.csv, while
the gate reads data/json and actually decides `publish/`. Checked 2026-08-19 for
the first time: 10 town-years the gate ADMITs still read `pending_parse`, and 3
the gate HOLDS read `no_election`.

**The denominator is the sneaky direction.** `no_election` rows are excluded from
the denominator entirely, so marking a town-year "no election" while holding that
town's own return does not merely miscount it — it deletes the obligation and
flatters the percentage. Overstating via the denominator is invisible in a
numerator check. Look for both.

**The stale-upstream trap.** `coverage_state` derives from
`logs/adjudication.csv`, which is now 1274 KEEP out of 1275 rows — it approves
nearly everything. Recomputing from it would have moved 12 town-years to
published/pending_parse **with no PDF and no JSON on disk**, including
Phillipston2025, which had just been proved to have no document anywhere (see
[[civicatlas-mine-before-scrape]], [[civicatlas-citation-not-source]]). A
maintained column can be better than a fresh recomputation from a rotted source.

**THE DRIFT CAME BACK ONE LEVEL OUT (2026-08-20), and the guard did not see it.**
The invariant written after the above, `coverage_matches_gate`, checks the
`coverage_state` COLUMN against the gate — only the column. Nothing checked the
**rendered `reports/coverage.html`**, which is a manual
`python src/coverage_report.py` with no trigger behind it. So the column was
correct, `check_invariants` printed a clean 10/10, and the HTML was still
publishing **74.8% / 1451 covered / 307 gaps** against a true **75.2% / 1459 /
302** — eight landed town-years invisible in the one artifact a human opens.
Fixed with a `coverage report is current` blocking invariant (11/11).

Two design points from writing it, both learned by getting it wrong first:
- **Check content, never mtime.** A timestamp fails on any `git checkout` or
  copy, and passes a report regenerated from a stale inventory.
- **Check the numerator only.** The first draft also recomputed the *gap* count
  and failed against a report generated sixty seconds earlier — "302 gaps" is
  not `everything not published` (485), it is the report's own arithmetic
  counting 2026 against 296 even-year towns. Reimplementing that inside the
  checker would plant a second silently-diverging copy of the report's logic in
  the very thing meant to check it. `published` is a literal count, it is what a
  landing moves, and it is what was wrong. **One unambiguous number beats three
  that need interpreting** — and per [[civicatlas-infra-baseline]], suspect the
  CHECK before the corpus.

**Why:** derived stores drift silently, and the drift is always discovered late
and in the flattering direction. Guarding the source column does **not** guard
the rendered view — ask, for every derived artifact, *what regenerates this, and
what fails if nobody does?*

**How to apply:** give every derived store a *measure-only* reconciler that
writes nothing (`src/coverage_vs_gate.py` is the model — it was worth restoring
from bytecode after its source was lost). Then repair by making the newer
authority win only where it has actually ruled, and add an **artifact-grounded
invariant** rather than a mapping: `published` requires `data/json/<stem>.json`
to exist on disk, whatever the claim's provenance. Print every refusal instead of
passing silently. Same pattern applies to publish/ vs data/ and to
deadend_ledger vs verdicts.
