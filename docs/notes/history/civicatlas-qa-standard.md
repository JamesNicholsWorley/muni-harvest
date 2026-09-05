---
name: civicatlas-qa-standard
description: "CivicAtlasMA QA was rebuilt (2026-08-12) around a single data-contract in qa/, superseding the sprawling qa_archive"
metadata: 
  node_type: memory
  type: project
  originSessionId: 97f28b1a-e07a-4a10-b3a1-7ef11454a391
---

The CivicAtlasMA data-QA was **rebuilt from scratch on 2026-08-12** into `CivicAtlasMA/qa/`,
replacing the sprawling read-only linter in `qa_archive/` (which ran but produced no data changes).

**Why:** the old suite conflated provable schema/arithmetic conformance with probabilistic anomaly
detection under one WARN tier (1,315 WARN, ~55% noise), and had no remediation stage — the owner
wanted a single well-defined standard and a triage tool, not an autofixer.

**The design (owner decisions — see qa/STANDARD.md):**
- `_original` fields are **canonical/verbatim to the source**; QA **edits `_original` in place** where
  it disagrees with the source (that edit IS the data change). **No schema change, no new fields, no
  name/district standardization** until QA is fully done (deferred to a later parser pass).
- Disposition model replaces ERROR/WARN/INFO: **VIOLATION** (provably wrong) / **LEAD** (adjudicate
  vs source) / **EXCEPTION** (legitimate, reason recorded — kills "good enough"). Plus a fix-type:
  FIELD-EDIT / WRONG-DOC / RE-PARSE / TRIM-REGIONAL / RECOVER-TURNOUT / ACCEPTED.
- **Wrong-doc cases are noted and handed to the gap-fill pipeline**, not fixed here.
- Linter is JSON+reference only; source-doc adjudication done on demand by human/subagents.

**Key facts learned:** RTMM huge Blanks = correct multi-seat undervote (total = ballots x num_winners,
Chelmsford 25/25 offices close exactly). num_winners is derivable from vote/ballot arithmetic (C2, high
precision — Acton School Committee declared 3/4 but closes on 2). Wrong-doc smoking guns: spring towns
dated 2024-11-05 (presidential) or 2024-03-05 (MA primary). Regional school aggregates (e.g.
Northborough-Southborough reserved cross-town seats) show as implied-ballots >> town consensus — TRIM,
not wrong-town.

**Progress (as of 2026-08-12):** first run 994 VIOLATION; after applying provable fixes -> ~203
VIOLATION. APPLIED (each with a pre_*.zip backup in qa/outputs + a changelog CSV): C2 num_winners
348 (apply_c2.py, exact + sub-1%), B1 address strips 68, B2 Blanks-row renames 10, A4 date fills 363
via MMA fallback (apply_a4.py, provenance in a4_date_fill.csv). Added a new check **G1 office-count
consistency** (cross-year): found ~97 under-covered docs — 49 official-source = incomplete parses
(re-parse targets, ~$10 credits available but batch deferred), 33 news = thin source need better doc.
A4 wrong-doc check: NONE are wrong docs (famous names only in source books, not parses).
**Explore subagents CANNOT be trusted for numeric source adjudication (proved 2026-08-12).** A 9-agent
fan-out over C4/C1/E1 produced circular reasoning ("Blanks should be X to match consensus") and two
outright FABRICATED quotes (a Hinsdale2025 turnout figure from a doc that says "Turnout not reported";
a Littleton2026 "TOTAL BALLOTS CAST 1210" from a doc that is a blank SAMPLE BALLOT). Only the narrow
"find a printed sentence" task was ~70% reliable, and every hit still needed my own grep to confirm.
Verify EVERY agent claim against the source before applying. Prefer deterministic scripts + my own
vision-Read of the PDF.

**Big root cause found: precinct-column capture.** Holbrook2021 was parsed entirely from the
Precinct-1 column (283 ballots) instead of TOTAL Per Candidate (1005) - all 9 offices, plus 8 name
OCR errors. Corrected by hand; every office now closes exactly at 1005. Suspect the same failure in
other multi-precinct C4 flags (Pepperell, Cheshire, Chelmsford, Clarksburg).
Also: apply_c2.py's consensus rule (>=3 offices agreeing AND >=60%) is too strict - Raynham2024 had
ALL 11 offices at exactly 347/694 but only 45% agreement, so 7 wrong num_winners survived. Fixed
by hand; consider relaxing the threshold.

REMAINING (source-reading passes): C4 ~85 ballot-agreement leads (needs a deterministic verifier,
NOT agents), E1 19 turnout, A4-manual 14 dates (2021-22, no date in source - need web lookup),
C1 8 material closure, A3 67 empty offices (11/15 docs isolated-ok, 4 whole-doc-suspect).
Littleton2026's source is a sample ballot -> new WRONG-DOC.
WRONG-DOC 55 held per owner. Queue: `qa/outputs/triage_queue.csv`; run `cd qa && python -m civicqa.cli`.

**Owner decisions added 2026-08-12 (later session):**
- **Ballot questions are OUT of scope everywhere** — schema is candidates-only.
- **`votes = -3` sentinel (new)**: a write-in winner of a race with NO ballot candidates, whose count
  is not separable from the printed `All Others` aggregate. Gets its own candidate row `"<Name>
  (Write-in)"`; the aggregate row keeps its clerk-printed label AND its count (no double-count, since
  -3 is excluded from C1 closure). Rule **B2b**. Corpus-wide this is exactly 2 rows (Holbrook2021
  Assessors + Board of Health). Write-ins the clerk already gave their own row with a real count
  (Northfield2021 x12, Lakeville2026 x2) are already conformant — leave them.
- **TRIM-REGIONAL rule: a town holds ONLY its own column**, never the district total. Partner columns
  + district totals go to the separate **regional register** (`qa/build_regional_register.py` ->
  `outputs/regional_races.csv`, 511 races / 359 town-years; 8 have a partner town with no town-year
  record of its own, so the register is the only witness).
- **A rule may only assert a fix-type its evidence supports** (added to STANDARD.md). D3 was asserting
  WRONG-DOC on mere date disagreement — 39 of 48 had no evidence; new `ADJUDICATE` fix-type for
  unresolved LEADs, and D3 now defers to D2 on year typos.

**The deterministic verifier (qa/verify_tallies.py) is 0-for-3 on COLUMN-CAPTURE claims** — Plympton2023
(matched a prose sentence in a news article), Mattapoisett2023 (read the NEXT candidate's total off a
concatenated line), Royalston2023 (the "precinct" columns were `Royalston | Athol | total` REGIONAL
district columns). Do not treat COLUMN-CAPTURE as actionable without turnout corroboration. Royalston2023
is in fact correct: 8 of 9 races close at exactly 273 ballots.

**STALE WARNING (2026-08-13):** everything above under "Progress" and "REMAINING" describes the
2026-08-12 state and has been overtaken — the queue is now down to 11 open findings. Read
[[civicatlas-qa-tail-close]] for the current position, the vision Batch-API pipeline, and the three
linter rule bugs still outstanding. The subagent verdict in this file is also revised there: the
distrust was earned by Explore fan-outs, but general-purpose agents with self-contained prompts and
an UNRESOLVED escape hatch performed well.

Ground-truth available but not yet wired: DLS officials + OCPF filers at `~/Downloads/Names Data`,
Boston/statewide district shapefile at `C:/Users/Owner/QGIS/BostonCityCouncil/`. Related: [[civicatlas-consolidation]].
