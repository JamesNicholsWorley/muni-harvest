---
name: civicatlas-multi-document-town-years
description: Some MA clerks publish one election as a PAIR of documents; register the second by sha256 as a source part rather than inventing a second stem
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Needham 2025 and Milford 2025 were both filed SHORT, and both for the same
reason: the clerk published the election as **two documents posted the same
day** — a town-wide tally and a separate Town Meeting Member tally — and the
inventory cited only one. Needham 13 races -> 25; Milford 12 -> 31 (exactly its
median). Assume the pair whenever a town's deficit is entirely Town Meeting
Members and its other years carry them.

**A second inventory stem is the wrong fix.** `parse_gate._split_stem` matches
`^([A-Za-z .'-]+?)(\d{4})(\d{4})?$`, so `Needham2025b` parses to municipality
"Needham2025b" / year None, and the same break repeats in the Gate row index,
`_load_baselines`, `build_publish.admitted` and `coverage_report.prior_stats` —
where a second row silently **adds a town-year to the coverage denominator**.
Five files, two of them blocking invariants. Concatenating the PDFs is worse:
the stored sha256 then matches nothing any URL serves.

**What works: `src/source_parts.py`.** Register the second document BY HASH —
`data/pdfs/parts/<sha256>.pdf`, `data/pdftext/<sha256>.txt`,
`data/inventory/source_parts.csv`. `parse_gate._pdf_native` then reads the
primary text plus every registered part's, so the gate grades the parse against
every document the town actually published. One function's change; the
inventory keeps one row, each artifact stays exactly what its URL serves, the
denominator does not move. Same principle as [[civicatlas-doc-fingerprints]] —
the path IS the provenance.

Land with `src/land_tmm_part.py`, which refuses if no source part is registered
(else the races land ungrounded) and refuses to run twice.

See also [[civicatlas-arithmetic-cannot-see-a-lost-name]] for the parser traps
these two-column precinct tallies set.
