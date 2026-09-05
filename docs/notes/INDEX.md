# Notes the corpus wrote about itself

Thirty-nine notes, one idea each, kept verbatim. Every one exists because
something went wrong in a way that was not obvious beforehand, and the specifics
are what make them stick: a summary saying "closure has limits" would not have
stopped anyone, and Provincetown's exact figures did.

They are grouped by the QA layer they serve, so an agent working one layer can
read that layer's notes and skip the rest.

Records of fixes already landed are in `history/` — read those only when you need
to know why something is the way it is.

## Layer 0 — is this the right document?

- [`empty-parse-is-wrong-doc`](civicatlas-empty-parse-is-wrong-doc.md) — enumerate what a return IS, never what it isn't
- [`municipality-is-a-witness`](civicatlas-municipality-is-a-witness.md) — the municipality field exists only to DISAGREE with the stem
- [`wrong-state`](civicatlas-wrong-state.md) — New England reuses town names; the office vocabulary is the state fingerprint
- [`scope-municipal-only`](civicatlas-scope-municipal-only.md) — fire and water districts are in scope; state races never are
- [`partial-vs-not-a-document`](civicatlas-partial-vs-not-a-document.md) — ask the citation's HOST before calling a document partial
- [`parse-identity-checks`](civicatlas-parse-identity-checks.md) — ask whose election it is before comparing parses
- [`multi-document-town-years`](civicatlas-multi-document-town-years.md) — a pair of documents is one election, registered by sha256
- [`landing-page-is-a-lead`](civicatlas-landing-page-is-a-lead.md) — a clerk's index page is a lead, not a return
- [`date-corroboration`](civicatlas-date-corroboration.md) — read the ARCHIVED capture; a live page names the next election
- [`proximity-not-aboutness`](civicatlas-proximity-not-aboutness.md) — a signed return outranks a forecast calendar
- [`undated-returns-publishable`](civicatlas-undated-returns-publishable.md) — the owner's rule for an undated return

## Layer 1 — is the reading grounded?

- [`ungrounded-is-unread`](civicatlas-ungrounded-is-unread.md) — 9 of 40 ungrounded records were materially FALSE
- [`names-are-unchecked`](civicatlas-names-are-unchecked.md) — every check tested numbers; nothing tested names
- [`ocr-is-not-the-page`](civicatlas-ocr-is-not-the-page.md) — an illegible OCR is not an illegible document
- [`ocr-invention-vs-silence`](civicatlas-ocr-invention-vs-silence.md) — prefer a reader that fails silent
- [`unsearchable-blind-spot`](civicatlas-unsearchable-blind-spot.md) — a placeholder is not an extraction
- [`deskew-before-reading`](civicatlas-deskew-before-reading.md) — 1.3 degrees off square produces a dozen symptoms

## Layer 2 — does the arithmetic hold?

- [`arithmetic-is-merge-blind`](civicatlas-arithmetic-is-merge-blind.md) — a fused race passes every ballots-times-seats check
- [`arithmetic-cannot-see-a-lost-name`](civicatlas-arithmetic-cannot-see-a-lost-name.md) — a perfect sum with a candidate missing
- [`seats-up-not-winners`](civicatlas-seats-up-not-winners.md) — num_winners is SEATS UP; the printed count outranks the arithmetic
- [`num-winners-is-the-weak-field`](civicatlas-num-winners-is-the-weak-field.md) — one digit, decides who won, invisible to size-based diffs

## Layer 3 — scope, completeness, reporting

- [`special-elections`](civicatlas-special-elections.md) — S&lt;Muni&gt;&lt;YYYYMMDD&gt;, never in an annual slot
- [`coverage-metric`](civicatlas-coverage-metric.md) — report town-year AND population-weighted

## Verdicts, citations, and the system lying to itself

- [`silence-is-not-a-default`](civicatlas-silence-is-not-a-default.md) — proving a document wrong made the corpus more confident about it
- [`two-authorities-drift`](civicatlas-two-authorities-drift.md) — two files holding one fact in two vocabularies
- [`derived-store-is-not-the-corpus`](civicatlas-derived-store-is-not-the-corpus.md) — the parser read the pruned copy
- [`uncontested-and-gaps`](civicatlas-uncontested-and-gaps.md) — a complete record deleted as a collection gap
- [`citation-not-source`](civicatlas-citation-not-source.md) — a rotted URL read as a missing election
- [`flag-describes-the-citation`](civicatlas-flag-describes-the-citation.md) — NEEDS_UPGRADE is about the citation, not the document
- [`known-bad-url-is-a-verdict`](civicatlas-known-bad-url-is-a-verdict.md) — **retired**: never call a document bad, say what it is
- [`doc-fingerprints`](civicatlas-doc-fingerprints.md) — hash not URL; replacing a document retires its notes
- [`a-hold-cannot-be-relabelled`](civicatlas-a-hold-cannot-be-relabelled.md) — change what the gate looks at, not what the inventory says

## Finding documents

- [`blocked-is-a-tool-verdict`](civicatlas-blocked-is-a-tool-verdict.md) — 403 describes our client, not the town
- [`env-tarpit-ci`](civicatlas-env-tarpit-ci.md) — residential IP beats CI for municipal WAFs; the reverse for archive.org
- [`atr-is-a-town-habit`](civicatlas-atr-is-a-town-habit.md) — one ATR-sourced year is a lead for every other year in that town
- [`harvest-is-a-title-index`](civicatlas-harvest-is-a-title-index.md) — CivicPlus URLs embed the title; held nodes are a searchable index
- [`mine-before-scrape`](civicatlas-mine-before-scrape.md) — 95 of 225 held town-years were already answered offline
- [`clerks-publish-to-google-drive`](civicatlas-clerks-publish-to-google-drive.md) — "no document" may be a sharing setting
- [`archive-recovery-levers`](civicatlas-archive-recovery-levers.md) — what actually recovers a vanished return
