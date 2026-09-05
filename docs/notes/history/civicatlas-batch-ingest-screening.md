---
name: civicatlas-batch-ingest-screening
description: "how the Ingest 5 batch of 105 researched candidates was screened and landed (+60 records, 87.3%->90.4%); the landing-page/attachment trap, the ATR page-index trap, and three ways my own screen over-reported before it was right"
metadata:
  node_type: memory
  type: project
---

2026-08-24. `research/ingest5/` (another agent) produced 108 fetched candidates for 103 open
town-years. Staged -> screened -> adjudicated -> hosted -> parsed -> gated: **ADMIT 60**,
HOLD 13, DROP 4, at **$0.59** on Haiku Batch. Corpus 1695 -> 1755 published, 87.3% -> **90.4%**
town-years, 96.4% people-years. See `INGEST5_STATUS.md`.

**THE PIPELINE THAT WORKED**, and is reusable: `src/stage_ingest5` (copy, never touch the
research folder) -> `resolve_ingest5_attachments` -> `extract_ingest5_text` (column-aware PDF,
render-then-OCR for scans, xlsx via sheet XML) -> `triage_ingest5` -> `adjudicate_ingest5`
(my read, evidence quoted) -> `host_ingest5` (derived_store + inventory only) -> parse -> gate.

**A LANDING PAGE IS ~140 CHARS SAYING "Attachment / Size / x.pdf / 345 KB".** Six candidates
were wrappers. Their attachment links point at the LIVE site and 404 -- which is why the page
was archived and the file was not found directly. Rewrite the attachment through the Archive
at the SAME capture timestamp as the page, with `id_`. Recovered 3 of 6; CDX proved the other
3 were never captured.

**AN ATR's PRINTED PAGE NUMBER IS NOT ITS PDF INDEX.** Seven slices looked like kennel
licences, vital records, budget schedules and town-meeting minutes -- and the election was
further down the SAME slice. Judging an ATR page by its first 100 characters is worthless: the
page opens with whatever the previous section was finishing. Search the whole slice.
Three genuinely needed re-cutting (Lee 2023 pp.101-102, West Bridgewater 2023 pp.19-20).

**MY OWN SCREEN OVER-REPORTED THREE WAYS** -- the recurring pattern this whole session:
1. substring rivals ("Erving" in *serving*, "Reading" in *processing reading was 202*,
   "Franklin" from *Franklin County* Regional Retirement). Word-boundary, and exclude
   `<Town> County`.
2. "doesn't name the town" != "is another town's". Sheffield's return never says Sheffield --
   the clerk posted it on sheffieldma.gov. Use the citation HOST; and for a Wayback URL the
   host that matters is the one INSIDE the capture, not web.archive.org (that alone condemned
   four good documents).
3. REVIEW/MIXED_SCOPE from triage_empty_parse is the classifier DECLINING, not condemning.
   Folding it into NOT_A_RETURN discarded 20 candidates.

**TWO NAME-COLLISION TRAPS.** Essex 2023's "ATR" is the *South Essex Sewerage District* Annual
Report. And the handoff's own warning proved exact: an ATR death register is *name + age*,
structurally identical to *name + votes*, and passes any pair-counting test -- only vocabulary
separates them.

**TWO INVARIANTS WERE INCOMPLETE, not violated.** `pending_parse has a document` looked only
for a PDF or parse, but 229 published town-years have NO pdf and 222 are held as
data/markdown; a document here is legitimately a news story or spreadsheet. And
`audit_writers`' bare `verdicts\.csv` pattern also matches `logs/qa_vision_verdicts.csv`, so a
module that merely NAMED that report was flagged as writing the gate's verdicts. Anchor on
`gate/verdicts.csv`.

**STILL OPEN:** 14 stems already held a document while their town-year read `no_source` -- the
new candidate cannot be hosted without displacing a file someone judged, so those need a
comparison. Wales 2024 and Westport 2022 are marked ballots needing vision, not an LLM parse
(see [[civicatlas-ungrounded-is-unread]] -- Wales 2023 published its winner with 0 votes that
way). Brimfield 2022 is a 126-page pure scan whose Town Clerk section is near p104 but whose
crop landed on audit correspondence; Dalton 2022's held document simply has no 2022 return.
