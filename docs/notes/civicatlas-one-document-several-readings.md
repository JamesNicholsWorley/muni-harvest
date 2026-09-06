---
name: civicatlas-one-document-several-readings
description: "we hold up to three readings of one document and each is lossy somewhere else; taking the first one in a fixed order reported 569 findings against documents that were right"
metadata:
  node_type: memory
  type: project
---

Found 2026-09-06, working the `wrong-document-1` bucket. Boston 2021 was flagged
`document_supports_record: 0/25 names and 0/36 figures located in
data/raw_ocr/Boston2021.txt`. The document is right. The reading was not:

    raw_ocr   pvescsr | oa ez] oira]ar] roe] eal sos] tera] su] se] se]
    pdftext   MICHELLE WU   3878  3002  5935 ... 91794

Both are readings of the same eleven-page PDF. `document_text()` walked
`raw_ocr, markdown, pdftext` and returned the **first that existed**, so a
born-digital PDF that had also been run through OCR was checked against the OCR.

**There is no reading that is right in general.** raw_ocr is the only reading of
a scan, which is why [[civicatlas-unsearchable-blind-spot]] put it first. pdftext
is the only faithful reading of a born-digital PDF. Preferring either blinds the
checks on the other half of the corpus. Three failure shapes, one cause:

- **Boston 2021** — OCR collapsed the table into noise; grounding scored zero.
- **Auburn 2022** — markdown extracts the heading as `MAY 1 7 , 202 2`; pdftotext
  reads `MAY 17, 2022`. A correctly-dated return reported as undated.
- **Hopedale 2025** — raw_ocr is `<!-- image -->` and nothing else, and it still
  won the priority order over a real extraction.

**How to apply:** the document is the thing being asked about; a reading is a
lossy view of it. Ground against the **union of every reading held**, and name
the readings searched in the evidence so a failure still says where you looked.
The union can only ever un-flag — every string that matched one reading still
matches the join — which is what `--compare-to` is for: 569 findings un-flagged,
**0 newly flagged**, across `carries_the_year`, `document_supports_record`,
`names_grounded` and `figures_grounded`.

This does not retire the upstream fix in [[civicatlas-unsearchable-blind-spot]].
A placeholder file should still never be written. But while it exists it now
contributes nothing instead of suppressing a real reading.
