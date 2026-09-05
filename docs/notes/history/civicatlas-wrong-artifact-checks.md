---
name: civicatlas-wrong-artifact-checks
description: "CivicAtlas gate kept grading records against the wrong artifact — source_text took the first file that existed, and the date regex could not match an ordinal; grounding proves the parse read the doc, not that the doc is the right town-year"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Three defects of one shape, all found 2026-08-19, all in CivicAtlasMA.

**1. `parse_gate.source_text()` returned the first file that EXISTED.** Order was
publish/markdown → data/markdown → data/raw_ocr. For an image-only scan the
markdown always exists (it IS the failed extraction), so the OCR beside it was
never reached. Worse, that markdown is often not blank but *about a different
artifact*: the town's news page or CMS navigation, scraped instead of the PDF.
The gate grounded candidate surnames against a page with no surnames, got 0%, and
DROPped correct parses (Hanson2025, Winthrop2025). Fixed by choosing the layer
with substance (strip `<!-- -->` before measuring) and skipping a markdown layer
when OCR of the same stem is >2x richer. `parse_corpus._hint_text` uses the same
rule on purpose — the text the parser reads and the text the gate grades it
against must be the same text.

**2. `_ANY_DATE_RE` could not match an ordinal date.** It ended `\d{1,2}\b`, and
in "MAY 6TH, 2025" there is no word boundary between `6` and `TH`. Any document
writing an ordinal read as printing no date at all (Harvard2025, held on
DATE_NOT_ON_PAGE while headed "MAY 6TH, 2025 ANNUAL TOWN ELECTION").

**3. Grounding proves the parse read the document; it does NOT prove the document
is the right town-year.** I reported Lincoln2021 and Mattapoisett2022 as verified
recoveries because their parses grounded 100%. Lincoln's PDF is dated June 15
2020; Mattapoisett's is 2023 and already published. Always check the document's
own date against the stem's year before calling something a recovery — and the
`verification` notes in the inventory are NOT uniformly stale, they must be read
case by case.

**4. OCR that succeeds at the WRONG LAYER of the page.** Worthington2025 is a
photo of a ballot with the counts written in by hand. Tesseract read 1174 chars —
the *printed* office headings and candidate names, comfortably over
`ocr_backfill`'s ok/thin threshold — and read zero hand-written figures and no
hand-written date. That text became the stem's source layer and the date guard
raised DATE_NOT_ON_PAGE against a record proved digit-by-digit on 500-dpi crops.
Set the OCR aside and it re-ADMITs. **`ok` means "produced text", never "read the
document"** — a character count cannot distinguish a good read from a fluent read
of the page's furniture. No blanket rule yet: 32 vision-settled stems also carry
OCR layers where the OCR is a genuine supplement.

**Why:** this is the project's signature failure — a name or pointer trusted as
the thing — and it now has four prior instances (the .xlsx extension bug,
_office_key, the native_url handoff-by-filename, the setaside register stem).

**How to apply:** when a check fails, ask what artifact it actually read before
believing the verdict. `parse_corpus` also used to read from publish/, which
build_publish fills with ADMITs only — so a rejected document was structurally
unreachable for re-parsing. It now reads data/. See
[[civicatlas-citation-not-source]] and [[civicatlas-doc-fingerprints]].
