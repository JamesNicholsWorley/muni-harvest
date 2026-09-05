---
name: civicatlas-ocr-invention-vs-silence
description: "Prefer an OCR reader that fails SILENT over one that fails LOUD: a value invented in a blank cell is the one error downstream arithmetic can never catch"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Billerica 2026's grid was read two independent ways: a **tall strip per COLUMN**
(`assign_values`, one OCR pass down a precinct, words snapped to nearest row) and
a **wide band per ROW** (`band_values`, one crop across all 12 precincts). The
obvious move was to fuse them and keep whichever agreed. Measured, that was
**worse than the band alone**, and the reason generalises:

**The two readers do not fail the same way.** The band reader fails SILENT — a
merged or straddling word is discarded, and the cell stays empty. The strip
reader fails by **INVENTION**: on a sparse page it snapped stray ink into rows
that printed nothing, putting `3355` against a candidate in precinct 11 and
`1874` into `Total Blanks` — columns the band correctly left blank.

**Why that asymmetry decides it.** Everything downstream is checked by the
document's own arithmetic (`sum(candidates + write-ins + blanks) == TOTAL ==
ballots x seats`). A blank cell is *visible* to that check and falls through to
the tight second-opinion re-read (`build_billerica2025.reread()` / `cell()`),
which settles it against the printed total. A **wrong number in a cell that was
truly empty has no printed total to contradict it** — it is arithmetically
invisible and lands as data.

So: when combining readers, don't ask which is more accurate on the cells it
fills. Ask **what each one does when it has nothing** — and keep the one that
says nothing. The strip reader survives in the code only as a **ruler**: its ys
are still the honest way to locate where a row's figures sit, so it supplies
`figure_ys` and nothing else.

Corollary, same page: **a merged OCR word must be discarded, not split.** When a
token straddles two column boundaries, cutting it at the boundary guesses which
digits belong to which precinct. `band_values` drops it (`if len(home) != 1:
continue`). Two merged TOTAL cells left blank cost nothing; one mis-split cell is
permanent.

Related: [[civicatlas-deskew-before-reading]] (this only became measurable once
the page was square), [[civicatlas-ocr-is-not-the-page]],
[[civicatlas-silence-is-not-a-default]] — note the tension: silence must not be a
*default* for a whole bucket, but it is the right *cell-level* failure mode.
