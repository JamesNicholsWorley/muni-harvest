---
name: civicatlas-rotate-before-ocr
description: "85 of 1,575 held PDFs carry a non-zero /Rotate, and the reading step ignores it: a rotated document fails figures_grounded 67% of the time against 15% for the rest, and Northbridge 2023 OCR'd to '69 --- oO N69 N = A + 9 tO' on a page that plainly prints its own heading"
metadata:
  node_type: memory
  type: project
---

2026-09-06, working the undated and ungrounded buckets. `pdfinfo` over every held
document reports **`Page rot:` non-zero on 85 of 1,575 PDFs** — mostly 270, some
90, two 180. The reading step does not honour it, and the damage is measurable:

    figures_grounded FAIL    rotated 67.1%    not rotated 15.3%
    names_grounded   FAIL    rotated 54.1%    not rotated 11.2%
    carries_the_year FAIL    rotated  7.1%    not rotated  3.6%

Sixty-eight of the 85 carry a layer-0 or layer-1 finding. That is roughly a
fifth of the whole ungrounded backlog, and none of it is about the record.

**Two documents opened, to be sure it is the rotation and not the corpus.**

*Northbridge 2023* (`rot 270`). Rendered and turned, page 1 prints
`COMMONWEALTH OF MASSACHUSETTS / TOWN OF NORTHBRIDGE ANNUAL TOWN ELECTION /
Tuesday, May 16, 2023`, `TOTAL VOTE: 451` over precincts `116 44 108 120 63`
that sum to 451, then `BOARD OF SELECTMEN 3 year term (vote for two) / Thomas J.
Melia 100 35 90 108 47 380`. Its published OCR, in full at the top, is
`69 —- oO N69 N = A + 9 tO`. The record grounded **0 of 85 names** and was
reported as not carrying its own year.

*Worcester 2023* (`rot 270`, 111,459 registered voters — the second-largest
town-year in the corpus). Page 1 prints `The City of WORCESTER / City Clerk
Department` and `OFFICIAL MUNICIPAL AND STATE ELECTION RESULTS / November 7,
2023`. The markdown extraction lost page 1 altogether and read the rotated
tables one character per row: the candidate columns arrive as `P E T E R J` and
`0 s E P H M`. **0 of 38 names.**

**Why it hides.** Every symptom it produces is a symptom something else also
produces. A wordless OCR looks like a scan of a bad photocopy; a name that will
not ground looks like a mis-transcription; a heading that vanishes looks like an
undated return. Each was investigated on its own and none of them named the
cause, because the cause is not in the document and not in the record — it is
one integer in the page dictionary that the renderer read and the OCR did not.
This is [[civicatlas-ocr-is-not-the-page]] with a machine-readable tell: the
document was never illegible, and unlike a skew ([[civicatlas-deskew-before-reading]]
— 1.3 degrees needing detection) this one **announces itself**, in
`pdfinfo`, before a pixel is rendered.

**How to apply.**

- Read `/Rotate` before OCR and rotate the raster to match. `pdftoppm` honours
  it; whatever produced `data/raw_ocr/` did not.
- The fix is upstream and it is cheap. Nothing in `qa/` should compensate: a
  check that tried to ground text against a sideways reading would be scoring
  the extractor, not the record.
- When a whole class of records fails grounding, ask what the documents have in
  common as FILES before asking what the records have in common as data. The
  answer here took one `pdfinfo` loop and explained sixty-eight findings.
- Forty-five of the 85 ground under 75% or hold no reading at all; those are
  queued in `qa/ocr_queue.csv` with the rotation named. Until they are re-read,
  their grounding failures say nothing about the corpus.
