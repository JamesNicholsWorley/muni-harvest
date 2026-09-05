---
name: civicatlas-history-leads-scope
description: "CivicAtlasMA — Chrome-history-surfaced docs are LEADS only; verify municipal scope + year, never auto-ingest"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 007d3b8f-950c-4487-8e4d-9f7f01fe8087
---

For CivicAtlasMA gap-filling, the user's Chrome history (Profile 1, not Default) is a rich
lead source — reverse-engineered method: Google `"{Town} MA {year} annual town election
results"` -> town-clerk/DocumentCenter PDF -> fallbacks Wayback -> archive.is -> Annual Town
Report -> Facebook -> local news; plus manual DocumentCenter-ID walking. See
[[civicatlas-2026-sweep]].

**Why:** When I listed 6 history-surfaced "official" docs and offered to auto-ingest, the user
corrected me: not all were valid. Rockland `DocumentCenter/View/3398` "Copy-of-official-
Results-Clerk-tally-end-of-night-3-5-24" was the **March 5 2024 presidential primary**
(Super Tuesday), NOT a municipal town election. A Webster 2023 direct doc was also no-good
("evident from URL"). Instruction: **don't ingest.**

**How to apply:** Treat history/DocumentCenter hits as *leads*, never as vetted sources.
Before presenting (let alone ingesting): (1) confirm it's a MUNICIPAL annual town election,
not a state/presidential primary or general — MA runs presidential primaries in March of
presidential years and labels them "official results" too; (2) confirm the doc's own printed
date-year matches the target town-year. Present only vetted leads; the user approves before
any ingest. The parse gate (NON_MUNICIPAL flag + year_check) is a backstop that would also
reject a presidential primary, but catch it upstream to save the parse. Local only, no push.
