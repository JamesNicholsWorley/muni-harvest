---
name: civicatlas-arithmetic-is-merge-blind
description: "ballots x seats is preserved when two races are fused, so it can never detect a merged block; and a median over two other years is not a baseline"
metadata:
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Found 2026-08-20 while looking for better documents for the 13 short returns. Two of the three "partial documents" I set out to replace were nothing of the kind.

**The arithmetic identity is preserved under merging.** Provincetown 2025 published a `Select Board` with `num_winners=3` containing Abramson 400, Golden 405 and **Conklin 17** — Conklin stood for *Charter Compliance*. The document prints its races in two columns and the reader ran the left column together. `Others 94` was 51+43, two races' write-ins summed; `Blanks 707` was 226+481. And it **passed the check**: 400+405+17+94+707 = 1623 = 541 x 3.

**Why:** if block A closes at `ballots x k1` and block B at `ballots x k2`, then A+B closes at `ballots x (k1+k2)`. Every check this project has built on ballots-times-seats is *structurally* incapable of seeing a fused race — it tests a NUMBER, and a merge corrupts a BOUNDARY. Checking harder would never have found it. I then tried to build a detector on vote magnitude ("a candidate seated with 4% of the leader's vote"): it fired **391 times across 249 town-years** and filtering failure-to-elect placeholders removed exactly one. The hits are real — sleepy offices genuinely seat write-in winners on 1-5 votes (Dennis 2025 a Constable with 2, Falmouth 2025 a Light Board member with 5). Kept as a documented negative result in `src/check_fused_races.py`; do not rebuild it.

**A median over two other years is not a baseline.** Taunton 2025 was filed SHORT at "6 races vs median 13.5" and read as a partial document. The median is over 2021 (21 races) and 2023 (6), and 2021's extra fifteen are all Town Meeting Member district races Taunton stopped enumerating. Six *is* Taunton's whole citywide ballot. `truncation_2025.csv` already refuses towns with <2 other years (NO_BASIS) — the right instinct one notch too loose. `src/check_truncation_baseline.py` ranks by SPREAD as well as count: **9 of 14 SHORT verdicts** rest on a questionable baseline.

**How to apply:**
- Fusion is a claim about a document's LAYOUT, so only the document can answer it. What found Provincetown was comparing races-in-parse against office-headings-in-document (`src/audit_short_documents.py`). Multi-column scans are where this happens.
- Before believing a SHORT verdict, look at the spread of the town's other years and whether 2025 is already at or above the town's own floor.
- Arithmetic still earns its keep the other way round: Taunton's Planning Board summed 2,366 short and the printed percentages summed to 93.62%, which *predicted a missing candidate of ~2,363 votes before anyone looked*. Cropping at 900dpi found JOHN J. COUTINHO, 2,366, under the clerk's seal. See [[civicatlas-ocr-is-not-the-page]].
- Related: [[civicatlas-empty-parse-is-wrong-doc]], [[civicatlas-proximity-not-aboutness]], [[civicatlas-seats-up-not-winners]].
