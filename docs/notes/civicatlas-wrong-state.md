---
name: civicatlas-wrong-state
description: "New England reuses town names across state lines, so no name test can catch a wrong-STATE return; the office vocabulary is the state fingerprint, and my first marker set was wrong 4-to-1"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Found 2026-08-20 while looking for better documents for the short returns: **Warren2025 was Warren, CONNECTICUT** (First Selectman, Board of Finance, Board of Assessment Appeals; hosted at warrenct.gov) and **Bedford2022 was Bedford, NEW HAMPSHIRE** (heading prints "BEDFORD, NEW HAMPSHIRE"; Supervisor of the Checklist; bedfordnh.org). Both were ADMIT/published/"clean". Retracted to `data/setaside/` by `src/retract_wrong_state.py`; detector is `src/check_wrong_state.py`.

**Why:** every name-based check agreed with itself — stem said Warren, parse said Warren, document said Warren — because the town really is called Warren, in both states. Bedford MA and Bedford NH even hold their annual elections in the same month, so the date test agreed too. `check_wrong_town`/D1 compares the parse's municipality to the stem and structurally *cannot* see this (see [[civicatlas-municipality-is-a-witness]]). The only witness that separates them is the **office vocabulary**: a ballot is written by its state's general laws, so the clerk cannot help printing a state fingerprint. MA has no First Selectman, no Board of Finance, no Board of Assessment Appeals, no Supervisor of the Checklist.

**But the office test only ever raises a suspicion.** My first marker list called "Trustee of Trust Funds" NH-only and duly convicted Berlin, Princeton and Walpole across nine town-years — four false positives per real one. Berlin 2021's first line is "Town of Berlin, **MA**" and Princeton elects an Electric Light Commissioner. MA towns do elect trustees of trust funds. The marker was a guess about another state's law wearing the costume of a test.

**How to apply:**
- A marker seen across MANY YEARS of one town is a fact *about that town*; a mixup does not repeat itself identically for five years from five different URLs. Only a marker unique to one year of a series is a suspicion.
- What convicts is the document naming its own state, or the host domain (`warrenct.gov`, `bedfordnh.org`) — never the vocabulary alone. Open the document.
- A marker earns its place only if MA law creates no such elected office *at all*. "Rare in MA" is not enough.
- The retraction must make the corpus **less** confident — qa_2025 NO_RECORD blockers went 1→2, which is the point ([[civicatlas-silence-is-not-a-default]]).
- `build_publish.py`'s safety rule ("nothing leaves publish/ that data/ does not have") had to be widened to mean *anywhere* under data/, including `data/setaside/`; read literally it forbids every retraction the project will ever make.

**RECURRED 2026-08-22, and the new fact is WHERE it hides: in a SCAN.** Warren2024 held "STATE OF CONNECTICUT, OFFICE OF THE SECRETARY OF THE STATE, Head Moderator's Return, Presidential Election 2024" and Ware2024 held "BENZIE COUNTY Statement of Votes, Presidential Primary February 27" — Benzie County is in **MICHIGAN**. Both sat on `EMPTY_PARSE`, which reads as "the extractor failed" and actually meant nobody had ever looked: a scan has no text layer, so *every* text guard the project owns silently cannot run (the gate says so on each pass — 162 documents NOT SEARCHABLE, 147 of them ADMITted on the parse alone). Render-to-bitmap + OCR takes ~4 minutes per document and settled both instantly. Retired by `src/retire_ocr_revealed_wrongdocs.py`; the OCR stays in `data/raw_ocr/` as the evidence for the verdict.

**How to apply:** before believing any verdict about a scan, OCR it — an untested document is unknown, not clean, and `EMPTY_PARSE` on a scan is a statement about our reading, not about the document. Also: **Warren is a repeat offender** and worth checking by hand every pass — this session alone it held Wilbraham's 2022 return, Brookline's 2023 return, and Connecticut's 2024 return.
