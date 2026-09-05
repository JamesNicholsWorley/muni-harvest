---
name: civicatlas-pdftext-index-survives-replacement
description: host_document retires stem-keyed markdown and raw_ocr but NOT the stem-keyed data/pdftext/index.csv row, so replacing a document leaves the gate reading the OLD document's text under the new document's name; fixed 2026-08-25
metadata:
  type: project
---

`data/pdftext` is keyed by sha256 — the path IS the provenance — which is
exactly why it was left out of `derived_store.STORES` and therefore out of
`retire_readings`. But **`data/pdftext/index.csv` is keyed by STEM**, and
`parse_gate._best_layer` reaches the store *through that index*. So the one
stem→sha association in the whole design outlived the document it described.

Found 2026-08-25 landing a 35-town-year ingest over 8 occupied stems. **Nine
stems were graded against the displaced document's text.** West Tisbury 2026 was
judged against 271 characters reading *"Important You are about to leave West
Tisbury, MA and visit an external site"* — the old artifact's landing page. Two
of the nine (NewMarlborough2026, Tisbury2024) had **no PDF under the stem at
all**, only an index row, so no poisoned-stem audit would ever have found them.

The tell: a first gate pass returned **35/35 ADMIT**, which is too clean. Checking
`_searchable(source_text(stem))` per stem is what exposed it. After re-running
`src/extract_pdf_text.py` (which self-heals a stale index row) the same 35 came
back 33 ADMIT / 2 HOLD, and both holds were real.

**FIXED** — `retire_readings` now drops the stem's `index.csv` row too. It drops
only the row, never the sha-keyed text file: another stem may legitimately be a
reading of those same bytes, and `extract_pdf_text` rebuilds the row from the new
bytes on its next run.

**The general rule: after any document replacement, verify the gate can actually
READ the new document before believing its verdict.** An ADMIT with no readable
text is not a pass — see [[civicatlas-padding-defeats-searchable]] for the other
way the same blind spot opens, and [[civicatlas-derived-text-keying]] /
[[civicatlas-derived-store-is-not-the-corpus]] for the family.
