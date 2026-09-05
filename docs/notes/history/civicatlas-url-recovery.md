---
name: civicatlas-url-recovery
description: "CivicAtlas native_url recovery — the URLs were never lost, they were never carried across the handoff into master_urls.csv; sha256 against the held PDF is the only acceptance test, and the recovered slugs doubled as a scope audit"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

132 CivicAtlasMA town-years held a PDF with a blank `native_url`. The inventory
was almost no help (5 had a landing-page markdown, 11 a filename), but **115 of
the 132 appeared in some fetcher's log** — `gap2026_candidates.csv`,
`resourced_links.csv`, `crawl_hosted.csv`, `wayback_sweep.csv`, all keyed
`(municipality, year, url)`. The URL was never lost; it was never carried across
the handoff into `master_urls.csv`. **Check the logs before assuming provenance is
gone** — an earlier pass searched them by *stem* and concluded "3 of 98", because
the logs key on municipality+year, not stem.

**A log line is a name.** Webster 2022's row points at mansfieldma.com; Berlin
2026's at shrewsburyma.gov. `src/recover_native_urls.py` therefore accepts a
candidate only on **sha256 of the fetched body == sha256 of our PDF**. Verdicts:
ACCEPTED 51 (written) / MOVED 5 (same text, different bytes — not written) /
WRONG_DOC 12 / BLOCKED 20 (403; recorded as a door not forced, never as a rotted
citation) / DEAD 27. Two things made it work: retrying a 403 once with a browser
UA, and following a landing page's document links **one hop** — matching not just
`*.pdf` but `/DocumentCenter/View/`, `/showpublisheddocument/`, `/files/`, since
those CMSes serve PDFs from extensionless paths.

**The recovered citations doubled as a scope audit.** Once sha256 ties the town's
own slug to our bytes, the slug is evidence about what the file *is*: 15 of the 51
name something other than the record they sit under — Canton/Northfield/Upton 2022
and Aquinnah 2024 are state elections, Holland 2024 presidential, Chatham 2026 is
headed May 15 2025, and Dalton 2022/2023, Norwell 2022/2024, Townsend 2022/2023
are each one byte-identical file under two stems. None published.

**Why:** provenance loss here was a handoff bug, not a collection failure, and the
cheapest fix was already on disk. **How to apply:** when a field is blank across a
cohort, ask which process *should* have written it and go read that process's own
output before going back to the network. See [[civicatlas-citation-not-source]],
[[civicatlas-wrong-artifact-checks]], [[civicatlas-doc-fingerprints]].
