---
name: civicatlas-deskew-before-reading
description: "A scanned grid 1.3 degrees off square produces a dozen unrelated-looking OCR symptoms; deskew the page before any row/column reasoning, and score the LONG rules to find the angle"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Billerica 2026's pages 1-4 went through the scanner about **1.3 degrees off square**
(page 0 was 0.4). At 400dpi across a 2833px-wide table that means a printed row
starts at y=397 under the label column and has fallen to **y=343** by GRAND TOTAL —
most of a full row pitch (58px).

**Every symptom looked like a different bug and invited its own local fix.** All
three of these were written and thrown away before the cause was found:

- a numeric column that read 5 cells out of 40 → looked like a psm/threshold problem
- a label whose figures sat 16px away on the left of the sheet and 72px away on the
  right → looked like a per-column offset needing calibration
- a TOTAL line that gave 8 of its 13 columns to `Total Blanks` → looked like the
  ±ROW_TOL windowing being too tight against the pitch

The tell that should have been read earlier: **per-column horizontal-rule detection
showed the same 49 rules in every column, drifting monotonically −54px left to
right.** A consistent monotone drift across x is skew and nothing else.

**Finding the angle: score the LONG rules, not the short ones.** The first search
maximised full-height *vertical* rule pixels and answered 0.0 for every page — the
column rules are short and stay dark under a small rotation while the long
horizontal ones smear. Rotate a quarter-size copy over ±2.5° in 0.1° steps and count
scanlines that are >75% ink across the table's x-range. Apply the winner at full
size. Search small, apply big: 51 rotations of a 4678×3308 page is a minute; the
small copy answers identically in a second.

**Two things break when you straighten the page**, both worth expecting:
- `im.rotate(..., fillcolor=255)` on an **RGB** page fills the corners with
  **(255,0,0) — red**, which every darkness test reads as ink. Convert to `L` first.
- Deskewing makes the *margin* legible too, so heading blocks in the left margin
  start qualifying as vertical rules (page 1 offered 11 of them before the first
  real one). Don't threshold on x — find the **longest run of near-equal-width
  cells** (the 12 precinct columns are the only regular thing on the sheet) and
  treat everything left of it as one label cell.

Related: [[civicatlas-ocr-is-not-the-page]] (don't judge a scan by its OCR),
[[civicatlas-wrong-artifact-checks]].
