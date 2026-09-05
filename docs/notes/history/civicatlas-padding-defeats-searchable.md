---
name: civicatlas-padding-defeats-searchable
description: "parse_gate._searchable counted column padding in its denominator, so layout-preserved grids read as unreadable scans and 130 published stems were never text-graded; FIXED 2026-08-24, and the two wrong dates it had been hiding are corrected"
metadata: 
  node_type: memory
  type: project
  originSessionId: 57be485a-0d9f-4d72-84e8-24620dfea578
  modified: 2026-08-25T02:51:00.078Z
---

`parse_gate._searchable()` ended with `letters >= len(body) * 0.25` and `body`
kept its whitespace. A precinct grid rendered with column alignment is mostly
spaces and digits, so it scored under the threshold, was filed with the
`<!-- image -->` scans, and the gate's text-reading guards never ran — the ADMIT
rested on the parse alone. **130 stems were in that state, all PUBLISHED**, the
biggest being the city returns (Revere2025 993,659 chars ratio 0.091,
Chelsea2023, Gloucester2023, FallRiver2025). `pdftotext -layout` and the
column-aware ATR reader both emit exactly this shape, so the rule penalised the
extraction mode the project depends on most.

**FIXED 2026-08-24** — ratio taken against `re.sub(r"[ \t]+"," ",body)`. The
mojibake guard above it (Dunstable2025's U+FFFD) is sound and untouched.

**Measure before shipping a corpus-wide guard change.**
`src/measure_searchable_padding.py` monkeypatches the rule and diffs verdicts;
scope is provably complete because `_searchable` gates only absence-asserting
checks, so a stem that does not flip is graded identically. Result: **10 of 130
moved, all ADMIT→HOLD on one flag (`DATE_NOT_ON_PAGE`). No DROPs, and no
grounding or fabrication flag anywhere** — the other 120 passed their first-ever
text grading clean. Published stayed at 1793; nothing was lost.

**Two of the ten were a second bug, not a hold.** Both print their date and the
guard couldn't see it because the extractor dropped the spaces:
`ANNUAL TOWN ELECTION05/03/2021` (Webster 2021 — numeric date fused to a word, so
the patterns' leading `\b` had no anchor) and `ANNUALELECTIONMONDAYJUNE262023`
(Leyden 2023 — day and year fused, so `_MONTH_GLUED_RE`'s `(\d{1,2}\b)` lookahead
couldn't fire). Fixed in `_unmerge` with two new seams (letter→digit, and
month→DDYYYY requiring a 19xx/20xx year). No record edit — the document always
said it.

**The eight real ones resolved 6 confirm / 2 CORRECT, and the corrections are the
whole return on the exercise** — both were published wrong and nothing could see
it because padding had switched the check off:
- **Ashburnham 2025: 2025-05-06 → 2025-04-29.** Town warrant (DocumentCenter/View/2311, a scan read at 250 dpi): "Tuesday the 29th day of April, 2025". The town votes the last Tuesday in April every other year; the outlier was the tell.
- **Newburyport 2023: 2023-11-01 → 2023-11-07.** Doc says "MUNICIPALELECTIONNOVEMBER2023" — month only — and the day had been filled in as 01, a **Wednesday**. City Clerk's 2023 election calendar names Tuesday 7 November.

Levers that settled the rest: the town's **warrant** (Clarksburg), **reading the
rendered page** — Palmer 2021 prints "8-Jun-21" outside the table and docling
dropped it, the [[civicatlas-ocr-is-not-the-page]] lesson — the **citation
filename** (Becket, Westminster, Halifax; the Merrimac precedent), and a
**statutory bracket** for North Adams 2025 (Tuesday after the first Monday, with
published 2021 and 2023 on either side — the Southbridge 2022 standard, not
Groveland's).

**A weekday check across a town's other published years is a cheap, strong date
audit** — it flagged both errors before any document was fetched.

Also found: `src/crop_held_reports.py` had `\bblanks?\b`, `\bprecinct\b`,
`\ball others\b` and `\b\d{1,5}\b` collapsed to literal 0x08 bytes by an earlier
heredoc, so its vocabulary scorer and number count silently matched nothing.
Repaired. See [[civicatlas-unsearchable-blind-spot]] (headline wrong there, the
predicate wrong here), [[civicatlas-derived-text-keying]].
