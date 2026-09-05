---
name: civicatlas-ocr-is-not-the-page
description: an illegible OCR is not an illegible document; Holland2025 was written off as needing a replacement without anyone opening the image
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CLOSED 2026-08-19. Holland2025 was the last open CivicAtlasMA two-parse town-year
and had been adjudicated `NEEDS_ANOTHER_DOCUMENT` on the reasoning "the disputed
count is not legible." That reasoning read the OCR (`Robert Patron lja
tosl-enonoad`) and concluded the *page* was illegible. Nobody had opened the
image. Cropped at 900 dpi (`src/crop_holland2025.py`) every hand-written figure is
plain.

- The disputed cell (water commissioner) is **190** — publish was right, data's
  130 was invented; the text layer carries no digit on that line at all.
- Reading the page found **four more errors both parses share** — town clerk 145
  should be 195, `Jonathan Bias 129` should be `Jonnathan Blas 139`, `Kelsey
  DeVos` should be `DeVoe`. Comparing two parses can never surface an error they
  agree on.
- The clerk signed it `OFFICIAL ELECTION RESULTS 6/10/25` with `TOTAL VOTES 212`.
  An annotated, signed ballot **is** the return; `is_sample_ballot` was a misread
  field, not a standard to relax. Every race clears 212 (largest 208).

**Why:** the same defect as [[civicatlas-wrong-artifact-checks]] one level up — a
record was graded against its own failed extraction, and then the *grading* was
believed over the document. "Not legible" is a claim about an artifact; say which
one.

**How to apply:** the gate's grounding guard already refused to run on OCR, but
decided "is OCR" by **directory**, so a scanner's OCR sitting in `data/markdown/`
was treated as a clean extraction. `parse_gate._is_scanned_pdf` now decides
structurally — every page covered by one raster — *and* requires the text to
contain no markdown link syntax, because Holbrook2022 is a scan whose markdown is
CivicPlus navigation and silencing grounding there would have retired a correct
DROP. Net across 1737 documents: 5 records moved, ADMIT 1394→1398, HOLD 331→327,
DROP unchanged at 12. Related: [[civicatlas-two-parse-closure]],
[[civicatlas-parse-identity-checks]], [[civicatlas-uncontested-and-gaps]].
