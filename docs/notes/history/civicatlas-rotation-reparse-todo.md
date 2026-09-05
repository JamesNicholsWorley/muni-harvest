---
name: civicatlas-rotation-reparse-todo
description: Pending work — normalize rotated PDFs and re-parse them; Sonnet 5 beats Haiku on hard docs
metadata: 
  node_type: memory
  type: project
  originSessionId: aada0ce6-9430-4ae7-b56d-3a0d25e402d7
---

CivicAtlasMA open follow-up as of 2026-07-06 (approved to "implement later"):

**Rotated-PDF normalization (NOT yet wired into the pipeline).**
- **63 of 861 PDFs in `publish/pdfs/` are rotated** (`/Rotate` 90/180/270) — full list in
  `logs/orientation_scan.csv`. This caused the worst manual-verify failure: Scituate2021 (image-based
  landscape tally at `/Rotate=270`) was parsed off the wrong axis, so every count was ~1/6 of the true
  TOTAL. Other offenders include Salem2025, Worcester2023, Taunton2025 (180), Revere2023, Northampton2023,
  the whole Scituate series, Woburn2021/2023 (90).
- `src/detect_orientation.py` detects (`scan`) and fixes (`fix`) these — it bakes the rotation into the
  page content (`transfer_rotation_to_content`) so the page is physically upright and re-OCR is consistent.
- **TODO to implement:** `python src/detect_orientation.py fix --all` → re-OCR the fixed PDFs
  (`src/ocr_pdf.py`) → re-parse (`src/parse_corpus.py submit --stems <the 63>`). Consider adding an
  orientation-normalize step to `ocr_pdf.py` so it's automatic for future docs. Fixed PDFs currently
  land in `data/pdfs_upright/` (demo copy of Scituate2021 already there).

**Model upgrade signal.** `src/test_parse_model.py` re-parsed the 5 manual-verify failures with
**Claude Sonnet 5** (`claude-sonnet-5`, intro price $2/$10 MTok through 2026-08-31) — it corrected ALL
known errors (wrong votes/names, dropped candidates, and even Scituate's wrong-column read on the STILL-
rotated PDF), and recovered dropped Milford TMM sub-races (24 vs 22). Those 5 files were promoted into
`data/json` + `publish/json` and pushed (commit e6e65d2). Consider a **full-corpus re-parse on Sonnet 5**
(the pipeline default is Haiku 4.5 in `parse_corpus.py`/`measure_parse_cost.py:HAIKU`).

**Two known pipeline fixes to make first:**
1. The `emit_elections` tool in `parse_corpus.py` is NOT `strict` — on 2 of 5 hard docs Sonnet 5 returned
   `elections` as a stringified JSON blob (had to `json.loads` on promotion). Add `"strict": true` to the
   tool schema to force a real array.
2. `num_winners` seat counts are still unreliable (e.g. Newburyport at-large came back 6; true is 5) — not
   fixed by a stronger model. Consider deriving seats from the ballot "Vote for N" text.

Related: [[civicatlas-credentials-and-git]] (how to push these changes).
