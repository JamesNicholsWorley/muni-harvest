---
name: civicatlas-derived-text-keying
description: "CivicAtlas gate never read the PDF itself - only stem-keyed derived stores - so 43 readable PDFs had no text that was a reading of them and 16 were held/dropped on wrong-source flags; fixed with data/pdftext/<sha256>.txt (path IS the provenance) and a grounding RESCUE, after the obvious veto design measured badly -- BUT the hash store was added ALONGSIDE the stem store, which still outranks it, so a REPLACED document leaves its old text behind and winning"
metadata:
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Found 2026-08-20 by `src/check_derived_freshness.py` (new): it re-extracts each
PDF and compares vocabulary instead of trusting the filename a derived file
shares with it.

**The defect.** `parse_gate._layers` consulted `publish/markdown`,
`data/markdown`, `data/raw_ocr` — three DERIVED stores, all keyed by STEM — and
**never the PDF**. 43 readable PDFs had no derived text that was a reading of
them; 16 were HELD/DROPPED on exactly the flags a wrong source produces
(CONTENT_NOT_IN_SOURCE, CONTENT_PARTLY_UNGROUNDED, SOURCE_DOC_MISMATCH,
DATE_NOT_ON_PAGE), and 12 of 14 of those parses were 84–100% grounded in text
nobody had extracted. Same family as [[civicatlas-wrong-artifact-checks]] and the
Rowe2024 catch.

**The fix that worked: address by hash.** `data/pdftext/<sha256 of pdf>.txt`
(`src/extract_pdf_text.py`). The path IS the provenance, so a replaced PDF is a
cache MISS, not a stale hit — staleness is unrepresentable, not merely detected.
No `--refresh`, no invariant needed. NOTE the contrast with
[[civicatlas-doc-fingerprints]]: a hash used as an ADDRESS is sound; a hash
*backfilled beside* a record (`source_sha256`) proves nothing about staleness.

**The design I tried first and rejected on measurement — remember this before
re-deriving it.** Letting the PDF's text VETO a markdown that shares none of its
vocabulary gained 9 town-years and cost 10. Those 10 are sound: surnames appear in
the markdown at 62–100% and the PDF at 0–8%, because the markdown is the fetched
CITED source (Bolton2021 cites a Telegram story, Egremont2025 the Berkshire Edge,
Granby2025 WWLP) and the PDF under the same stem is a different, uncited document.
Yarmouth2021 is the mirror image. **A stem holding two unrelated documents is an
ambiguity the gate must not settle by preference** — the old code guessed
markdown, the veto guessed PDF, each right about half the time.

What shipped: the PDF text is a **RESCUE inside `_check_grounding`** — it can only
move a record from ungrounded to grounded, annotated `GROUNDED_IN_PDF_NOT_SOURCE`.
Fabrication is still caught because an invented record is in no layer.
ADMIT 1451→1459, HOLD 183→180, DROP 24→19, no regressions. Recorded as
DECISIONS.md §6.10 and §6.11.

**THE HASH STORE WAS ADDED BESIDE THE STEM STORE, NOT INSTEAD OF IT (found
2026-08-20 via Warren 2025).** `_layers()` still yields `data/raw_ocr/<stem>.txt`
BEFORE the pdftext, so hashing solved staleness only for the store that was
hashed. When a town-year's PDF is REPLACED, the pdftext entry cleanly
disappears — that is the design working — while the stem-keyed OCR of the old
document stays put and keeps winning. Warren2025's citation moved from
warrenct.gov to the town's own MA return; `data/raw_ocr/Warren2025.txt` went on
saying "First Selectman ... Gregory LaCava", and an 18-race Massachusetts parse
whose every race closed was HELD `DATE_NOT_ON_PAGE` because the gate was reading
Connecticut. **Retiring a document is not finished until its stem-keyed derived
text is retired too.**

Swept the other 456 stems holding both. mtime (`pdf newer than raw_ocr`) is the
LEAD, content is the verdict — 9 candidates, each opened: 6 were the same defect
(Lancaster2024 held the NOVEMBER state election under a May annual; Otis2025 held
the April TOWN CAUCUS; Dudley2024 held the WARRANT; Brewster2022/Norfolk2023/
Norfolk2025 held 80–149k chars of cover-page OCR noise) and were retired to
`data/setaside/retired_text/` with a register (`src/retire_stale_raw_ocr.py`).
**Three were deliberately NOT retired, and that is the transferable half:**
Merrimac2021 and Acushnet2022 point the other way (the OCR is the Annual Report
and carries the election; the PDF is the audited accounts / a 2020 primary — the
DOCUMENT is wrong, not the text), and Holbrook2021 has no pdftext at all, so
retiring its wrong text removes the only text and the record goes from
"graded against the wrong page" to "unsearchable", which reads as cleaner —
[[civicatlas-silence-is-not-a-default]] exactly.

The retirement was worth it beyond the counts: reading the REAL Norfolk 2023 page
showed one PDF carrying three elections, with a Jan-28 special Select Board
parsed into the ANNUAL town-year slot. Net ADMIT 1459→1462, HOLD 180→179,
DROP 19→18. See [[civicatlas-special-elections]].

**A threshold must be measured, not fitted.** A "garbled text layer" test at 4+
letter words flagged Brockton2025, Cambridge2023, Haverhill2021, Newton2025 — all
opened, all perfectly legible big-city ward-by-precinct tallies that are
legitimately mostly DIGITS. Scored on 6+ letter words across all 1138 PDFs with a
text layer: Brewster2025 0.06, next lowest 0.87. One value, a 14× gap, then
everything else — so the threshold sits in a measured empty band.
