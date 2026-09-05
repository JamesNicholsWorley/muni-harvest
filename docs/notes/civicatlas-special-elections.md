---
name: civicatlas-special-elections
description: CivicAtlas special-election naming schema S<Muni><YYYY><MMDD>; a special must never occupy an annual town-year slot; 10 set aside 2026-08-17.
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Special elections are in scope *eventually* but are not what CivicAtlasMA is
currently collecting. The user's schema:

    S<Municipality><YYYY><MMDD>      e.g. SWales20250723

**The rule: a special election NEVER takes the place of a year.** The leading S
and the MMDD mean it cannot collide with an annual stem (`<Municipality><YYYY>`)
and two specials in one town-year stay distinct.

**Why it matters:** while a special sat in an annual slot it did two kinds of
damage — it displaced the annual, and it made the town-year read as *covered*
when the annual had never been found. Marshfield 2026 read as published; what was
published was a one-race special.

**How to apply:** when setting one aside, artifacts move to `data/specials/` under
the S-name, the town-year returns to `coverage_state=no_source` (the truth: the
annual has not been found), and `native_url` moves to
`data/specials/specials_register.csv` — a citation pointing at a *different*
election is worse than no citation. Adjudications written against it move to
`specials_adjudications.csv` and are re-keyed to the S-stem, or the QA verifier
loses their sources and the baseline silently drops.

Identify a special by the **race, not the calendar**: Wales2024 was held on the
Massachusetts state primary day (2024-09-03) and is still a municipal special.
See [[civicatlas-scope-municipal-only]].

10 registered 2026-08-17: SAdams20240924, SHarvard20251008, SMarshfield20260502,
SMashpee20221004, SOakham20230914, SRowe20260207, SSheffield20231204,
SWales20240903, SWales20250723, SWare20241203.
