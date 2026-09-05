---
name: civicatlas-derived-store-is-not-the-corpus
description: "ingest_finds hosted every artifact into publish/ (derived, pruned) while data/ is what the parser and gate read — 19 parses read stale files and Abington 2021 came back as a PFAS water report; the same stem-vs-content split also let a page's markdown grade an image's parse"
metadata:
  type: project
---

Found 2026-08-22. `src/ingest_finds.py` wrote every hosted PDF/markdown to `publish/`, which `src/build_publish.py` REGENERATES from `data/` and prunes to ADMIT. `data/` is what the parser, the gate and every checker read. So an ingested document landed in `publish/pdfs`, `data/pdfs` kept whatever was there before, and the parse that followed read the OLD file.

**Abington 2021 is the tell:** the crop of its town report went to `publish/`; `data/` still held a one-page scan with no text layer, and the parser returned a heading of "PFAS6 Results for Hingham Street WTP, Finish Water" — the water department. The gate then correctly said NOT_A_RETURN, so it read as a bad document rather than a misdirected write. **All 19 documents in that batch returned zero races for the same reason.** Fixed with `mirror_to_data()` at the write.

**The same split in a second form:** derived text is keyed by STEM, documents by CONTENT. Worthington 2023's markdown (08-17) was a reading of the town's NEWS PAGE; on 08-22 the document became the results IMAGE that page links. The gate prefers a wordy markdown layer over an OCR one, so it graded the image's parse against the page's prose — 0 of 15 surnames, CONTENT_NOT_IN_SOURCE on a parse that had read the sheet correctly. Moved to `data/setaside/stale_derived/`.

**How to apply:**
- After any ingest, verify `data/pdfs/<stem>` and `publish/pdfs/<stem>` hash the same before parsing.
- When a document is REPLACED, retire its stem-keyed derived text in the same act — markdown especially, because it outranks OCR.
- A whole batch returning zero races is never 19 bad documents; it is one plumbing fault.

**AND A STALE STEM-KEYED LAYER CUTS BOTH WAYS (2026-08-23).** `data/raw_ocr` is keyed by stem and `_layers()` yields it BEFORE the PDF's own text, so when a document is replaced the old reading keeps winning:

- **It can BLOCK a good record.** Tyringham 2022's clerk-emailed return was held on SOURCE_DOC_MISMATCH — "the cited source calls itself a STATE ELECTION" — because raw_ocr still held the town's *2018 state election*. Retiring the layer published it immediately.
- **It can also ADMIT a bad one, which is worse and invisible.** Sutton 2026 was PUBLISHED "clean" with six races and counts (Select Board 584/651/615) while its only held-and-cited document is a nomination-papers notice listing positions and a phone number. Grounding found every surname — in `data/raw_ocr/Sutton2026.txt`, a reading of a different document ("May 12, 2026 Official Election Results"). Retired by `src/retire_sutton2026.py`.

**How to find them:** for every raw_ocr file whose stem also has a PDF *with* a usable text layer, compare vocabulary overlap. 21 of ~740 scored under 30%; reading all 21 gave 12 stale, 7 merely different extractions of the same page, and 2 where the OCR is the GOOD reading and the PDF is the problem (Brewster 2025's text layer is mojibake; Sutton 2026's PDF is the wrong document). Overlap is a LEAD — open every one before retiring it. `src/retire_stale_raw_ocr.py` holds the audited list and moves files to `data/setaside/retired_text/` rather than deleting, since a stale OCR is evidence that a real document exists to be re-found.

