---
name: civicatlas-publish-derived
description: "CivicAtlas publish/ is now GENERATED from data/ by src/build_publish.py, never edited; set-aside files consolidated into data/setaside/ with one register."
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

`publish/` stopped being a store on 2026-08-18. It is now an output:

    publish/ := every artifact in data/ whose stem the gate ADMITs

Regenerate with `src/build_publish.py` (dry run, then `--apply`) after any change
to `data/` or to the gate. A clean run prints `+0 -0 ~0`. **Never edit `publish/`
directly** — that is exactly what produced the 216-town-year divergence in
[[civicatlas-store-divergence]].

**Why:** a store you write to can disagree with its source; a store you
regenerate cannot. The script refuses to run if any file it would delete from
`publish/` is absent from `data/`, because `publish/` was once the only home of
most of the corpus — and that refusal immediately caught three town-years
(Everett2021, Lanesborough2023, Yarmouth2024) whose source document is an
**.xlsx, not a PDF**, held only in `publish/pdfs`. Do not assume one extension
per artifact directory.

**How to apply:** set-aside files now live in `data/setaside/<reason>/` indexed by
`data/setaside/register.csv` (324 files, nine reasons, `src/collapse_setaside.py`)
instead of nine scattered directories. But `data/pdfs/_oversized` and
`data/superseded_pdfs` are **source locations, not quarantine** — four QA tools
search the first for document text and `qa/fingerprint_sources.py` reads the
second to judge old adjudications. Moving either blinds the QA verifier. Verify
after any reorganisation with `qa/build_source_index.py` then
`qa/verify_adjudications.py`; the baseline is 345 PROVEN, 0 failures.

Related: [[civicatlas-qa-tail-close]], [[civicatlas-consolidation]].
