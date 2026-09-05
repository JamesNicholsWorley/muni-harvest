---
name: civicatlas-harvest-is-a-title-index
description: "CivicPlus DocumentCenter URLs embed the document TITLE after the id, so muni-harvest's already-held nodes are an offline, searchable title index of a town's whole document library — this closed Chatham 2025 with zero requests"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

On CivicPlus sites the URL is `/DocumentCenter/View/<id>/<Document-Title-Slug>`.
So the nodes muni-harvest has already harvested are not just a URL list — they are
a **title index of the town's entire document library**, searchable offline for free.

Chatham 2025 had been open for weeks and was slated for a GitHub Actions id-sweep.
Streaming `muni-harvest/data/discover/nodes.jsonl` (1.5 GB, line by line) surfaced
6,098 Chatham DocumentCenter ids with slugs. Filtering for a standalone `ATE` token
exposed an unbroken series — 7933=2010 … 7946=2022, 7947=2023, 7368=2024 — and
**9524 = `2025--ATE-May-15-2025-Minutes-PDF`**. One fetch, ADMIT, 3 races, arithmetic
closed. The document was never missing; it was never looked for in the right index.
See [[civicatlas-mine-before-scrape]].

**Why:** every other Chatham year in the corpus came from that same ATE-Minutes series.
A per-town naming series is the strongest possible lead, and it is only visible if you
look at the town's ids *as a set* rather than chasing one year at a time.

**How to apply:**
- Before scraping any CivicPlus town, mine the harvested nodes for its DC ids and read
  the slugs. ~145 towns are covered.
- Look for the town's own **naming series** across years, not just the target year.
- Prefer the certified artifact over the election-night one: id 8736
  `Annual-Town-Election-Preliminary-Results` is what newspapers report from; the
  `ATE-Minutes` are the clerk's certified record.
- **Word-anchor the regex.** A loose `elect|result` matched `Electrical-Permit` and
  `Real-Estate-Commitment`; a bare `ATE-` matched `Upd`ate-`` and `D`ate-``. Both
  returned hundreds of confident hits that were nothing.
- A slug is a **lead**, never a source — fetch and read before it counts
  ([[civicatlas-citation-not-source]]).
