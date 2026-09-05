---
name: civicatlas-num-winners-is-the-weak-field
description: "num_winners is the field most likely to be wrong and the hardest to notice: it decides who won, and because it is a single digit a wrong value changes nothing about a file's size or shape, so it survives every diff that looks for scale"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

`num_winners` is the weakest field in the CivicAtlas parse schema, and the most
consequential. It is not a statistic about a race — it is the statement of who
won it. Williamsburg 2025's Board of Library Trustees ran two candidates for two
seats and was recorded as `num_winners=1`, i.e. the record said Sara Barry lost a
seat she had won unopposed.

Two things converged on this on 2026-08-20:

1. **`src/build_publish.py` compared filename + `os.path.getsize` under a comment
   saying "compare bytes, not names."** Size is not bytes. Because `num_winners`
   is a single digit, every disagreement in it left the file size identical — so
   the anti-drift regenerator reported "nothing to do" while 118 town-years'
   `publish/json` disagreed with `data/json`. It now hashes. **A same-size edit is
   the blind spot of every size-based comparison; the field most likely to differ
   by one character is also the field most likely to hide.**
2. `src/adjudicate_seat_divergence.py` settled the 172 disagreements against the
   ballot arithmetic instead of against the "data/ is authoritative" policy:
   **160 to data/, 0 to publish/, 12 with no arithmetic either way.** Deciding it
   by evidence rather than by policy is what made the result worth trusting.

**How to test a seat count without the document.** With a Blanks row present,
every ballot contributes exactly `num_winners` marks, so `sum(votes) == ballots *
seats` *exactly*. Establish `ballots` from ≥3 single-seat races in the same
electorate summing to precisely the same number (equal, not within a tolerance —
a 2% reference cannot certify an exact multiple), then require the disputed total
to divide with remainder zero AND the race to name at least as many candidates as
seats claimed. That last guard is the only one independent of the arithmetic.
On 2025 this corrected 9 races exactly and correctly refused 17.

**Do NOT expect the town's printed "Vote for two" to corroborate it.** I built
`src/read_seat_instructions.py` to find it and it mostly is not there: of 27 towns
with a seat finding, 8 published scans with no text layer and only 6 print the
instruction anywhere. **A return reports what was counted; the "vote for N"
instruction lives on the ballot, which is a different document.**

Related: [[civicatlas-store-divergence]], [[civicatlas-publish-derived]],
[[civicatlas-doc-fingerprints]], [[civicatlas-uncontested-and-gaps]].
