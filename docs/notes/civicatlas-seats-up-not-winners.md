---
name: civicatlas-seats-up-not-winners
description: "num_winners is SEATS UP not people who won; the printed \"vote for no more than N\" IS the seat count and outranks the ballot arithmetic, which is only a lower bound"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CivicAtlasMA, settled 2026-08-20 against the Topsfield 2025 ballot image
(`data/setaside/topsfield2025/p0_bot.png`). Written into DECISIONS.md §5.7.

`num_winners` is the number of seats the town PUT ON THE BALLOT, not the number
of people who won. So `k >= 1` always; `k = 0` would mean the office was not on
the ballot at all. This **retires** the older note that "`num_winners=0` is the
outcome" for failure-to-elect races.

**The two witnesses RANK, they do not vote:**

1. **The printed instruction is the authority.** "Vote for two" *and* "vote for
   **no more than** two" both state the seat count.
2. **The ballot arithmetic is a LOWER BOUND, not a count.**
   `sum(votes) == ballots * seats` holds only where the clerk reported blanks
   per **mark**. Many clerks report blanks per **BALLOT** in an under-subscribed
   race, and the identity silently collapses to the number of seats that drew a
   candidate.

**Why:** Topsfield's Select Board sums to 1285 = exactly one ballot's worth, so
`src/seat_arithmetic.py` said one seat. The photographed ballot prints "(vote for
no more than two)" *inside the Select Board box*, and the sibling Library Trustee
and Elementary School Committee races carry the **same** instruction and sum to
2570 = 1285 x 2. Two seats were up; only one candidate stood. The arithmetic was
never wrong — it was answering a different question.

**How to apply:**
- Never let `seat_arithmetic.py` CONFIRM a seat count against a printed
  instruction. It may raise one; it may not certify one.
- Do not treat "no more than N" as a ballot maximum. That veto in
  `stated_seats()` (`src/check_seats_vs_officials.py`) is exactly what let a
  wrong seat count read as correct, and it suppressed the strongest witness.
- Hand-adjudicated seat rulings live in `src/apply_seat_rulings_2025.py` (a
  fixed 9-row table, each naming its witness, double-guarded on
  office-matches-exactly-one AND current-k-equals-expected-old). Keep it
  SEPARATE from `src/fix_seat_counts_2025.py`, which derives counts from the
  arithmetic — a script that trusts the arithmetic cannot also be the one that
  overrides it.
- Coverage is thin: only 193 of 3,592 races (5%) print an instruction. All 193
  agree. Agreement means the best witness never contradicts us where it speaks,
  NOT that the year is right.

Related: [[civicatlas-num-winners-is-the-weak-field]],
[[civicatlas-silence-is-not-a-default]] (the `k < 1: continue` skip that hid
Phillipston turned "untestable" into "passed" — now reported as `NO_SEATS`).
