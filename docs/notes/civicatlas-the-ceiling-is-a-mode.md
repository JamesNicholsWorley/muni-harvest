---
name: civicatlas-the-ceiling-is-a-mode
description: "ballots is a mode over contests that disagree; 144 of 197 impossible-arithmetic findings sit inside that disagreement, and only the document's printed count separates a short reading from a real excess"
metadata:
  node_type: memory
  type: project
---

Found 2026-09-08 working the adjudication ledger, after reading sixty-three
resolutions in the `impossible-arithmetic-1` bucket that all said the same
thing: *"THE READING IS FAITHFUL AND THE EXCESS CANNOT BE A SEAT COUNT."* Sixty-three
sessions had each opened a document, confirmed the figures, and had nowhere to
put the answer. That is a pile, and a pile is a signal.

**`marks > ballots x seats` is impossible only if you know `ballots`.** We do
not. `derive_ballots` takes every at-large single-seat contest that prints its
blanks — each of which sums to the ballots cast exactly — and returns the
**mode**. The quorum rule is satisfied by two contests agreeing. It is not
violated by four others disagreeing, and nothing said so.

**Middleborough 2023** is the clean case. The sheet prints, verbatim:

    OFFICIAL RESULTS   #of Eligible Voters: 19,131   Total Votes Cast: 1,398

Every single-seat TOTAL row on that sheet reads 1398 and every two-seat row
2796. Three of our six qualifying contests read **1396**, because the OCR lost
write-in marks — the sheet's own `WRITE-IN/TERESA FARLEY` total column OCRs as
`a`, and `WRITE-IN/ANDREA SMYTHE` drops a column entirely. So the mode is 1396,
and the two contests that read the printed figure are reported as **exceeding
the ballots**. A contest condemned by a ceiling its siblings' misreadings set,
against a number the document prints in its own header.

**The scale.** Of 1,284 records with a derivable count, **156** have qualifying
contests that disagree; 1,128 agree unanimously. Of 197 at-large
`marks_exceed_ballots` findings, **144** sit inside that disagreement — the
contest is within `max(estimates) x seats`. Only **53** exceed every reading the
document supports, and those are a different animal: they are mostly multi-seat
(Wayland 2023 `SELECT BOARD` 5050 against a unanimous 2475 x 2; Dedham 2021
`SCHOOL COMMITTEE` 12619 against 4173 x 3), which is the shape of a wrong seat
count or a fused race, not a lost mark.

**Do not "fix" it by taking the maximum.** That was the first idea and the
corpus falsifies it. **Shirley 2023** prints `TOTAL Number Votes Cast 688`,
which is the *mode*; three of its contests read as high as 727, so there the
high readings are the wrong ones. Middleborough says the maximum is right and
Shirley says the mode is right. Nothing in the record separates them — both are
"our contest sums disagree" — so any rule picking one silently corrupts the
other. Taking the maximum also lets an outlier excuse itself: Dracut 2026's
estimates are `[1992, 1992, 3984]`, and a maximum ceiling would clear the
doubled figure that is the actual defect.

**What actually separates them is the document's printed ballot count, and the
corpus does not hold it.** `ballots_cast` is `derived_from_contests` in 1,273 of
1,891 records and `stated_in_record` in 64 — so the "free comparison" the
pipeline was designed around has no second number to compare against. Deriving
the count was right; discarding the printed one was the cost nobody priced.

**How to apply:**

- The verdicts have not moved and should not move on arithmetic alone. What
  changed is the evidence: `ballots_derivable` now names the dissenting figures
  and the spread, and a `marks_exceed_ballots` inside that spread carries
  `"but the single-seat contests disagree (up to N)"`. A session no longer has
  to re-derive the spread before it can start.
- Working one of these: read the document's **header**, not the contest. The
  count is usually printed there — `Total Votes Cast`, `Total Ballots Cast`,
  `TOTAL Number Votes Cast`. If it equals the maximum, the short contests are
  ours to fix and the flagged one is right. If it equals the mode, the flagged
  contest is ours to fix.
- An excess against **unanimous** contests is not this class. Check the seat
  count first (see [[civicatlas-seats-up-not-winners]]) and then layout
  (see [[civicatlas-arithmetic-is-merge-blind]]).
- The standing recommendation to the owner: transcribe the printed ballot count
  as its own field, alongside the derived one. It is a copied number, not a
  produced one, so it does not open a hallucination site — and it settles 144
  findings that currently cost a document read each.
