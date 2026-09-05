---
name: civicatlas-divergence-resolved
description: "CivicAtlas parse divergence largely dissolved - 85 of 180 were identical content; the comparison's office-key had collapsed distinct races. Arithmetic only partly decides the rest."
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

The 180-town-year parse divergence ([[civicatlas-store-divergence]]) was mostly
not a divergence. Resolved 2026-08-19 to: **85 EQUIVALENT, 31 too close, 27
undecidable, 21 data, 8 publish, 5 conflicted, 3 both-wrong.**

**The bug that manufactured it.** `compare_divergent_parses._office_key` keyed a
race by *the longest word in its heading*. Arlington's 26 races -- 21 of them
"Town Meeting Members" -- all collapsed to `MEETING` and overwrote each other
down to 5. Both parses then tallied identically and the script reported "no test
separates them", which is why **78 of 114 "too close" stems had zero testable
items**. It is the project's signature defect one more time: a name was invented
and trusted as an identity. Fixed by matching races **by candidate-set overlap
across the whole election**, with the heading only as a tiebreaker -- headings
genuinely disagree ("TOWN MEETING MEMBERS" vs "Town Meeting Member", and one
parse keeps "PRECINCT n" while the other drops it). Term length and ward/precinct
are identity and must be kept; "(Vote for 2)" is formatting.

Re-running found **8 town-years where the withdrawn parse was better** and
shipping less: Westport2023 (12 races vs 72), Milford2021 (20 vs 31),
Fitchburg2023 (8 vs 13), Montague2024, Dartmouth2024, Chelmsford2024,
Plymouth2024, Cambridge2021. All swapped.

**Why arithmetic only partly settles the rest** (`src/check_parse_arithmetic.py`,
6 decided of 66). The invariant is real -- `sum(votes incl blanks)/seats =
ballots cast`, identical across town-wide races; Needham2022 reads 2874, 2874,
2874, 2875. But it is only sometimes available: multi-seat races need
`num_winners`, which is itself parsed; **precinct and ward races sit in the same
file with a genuinely different denominator** (so the reference must be the
dominant cluster, never the median -- a first version scored a known-good parse
96% defective); and blanks are optional, so where a return omits them the sum is
short by an unknown amount. Only decide when the winner closes *exactly* and both
parses were tested on comparable ground; "27 of 30 off vs 28 of 31" is two broken
parses and a re-parse lead, not a winner.

**How to apply:** `python src/rebuild.py --apply` rebuilds every derived output in
dependency order (gate -> inventory -> publish -> source index -> QA -> verify).
The reports (`reports/coverage.html`, `reports/spot_fixes.html`) regenerate at the
end of a `civicqa.cli` run, but nothing triggers that run on its own.
