# Election-document recovery — missing / recovered accounting

*2026-07-30. Document-FINDING project (no processing/extraction): what election-result
documents CivicAtlas was missing, what our sweep recovered, and what's genuinely absent.
Basis: consolidated corpus (3.26M nodes) vs CivicAtlas `master_urls.csv`. Artifacts in
`scratch/`: `still_missing_final.csv`, `recovered_missing_docs.csv`.*

## Headline
- **Expected town-years** (election happened; `expected≠no` already encodes cities'
  odd-year schedule): **1,649**.
- CivicAtlas had downloaded: 942. **Our sweep added a results doc for 982.** Union covers
  **1,237**. **Still missing: 412 (25%).**
- Of 143 town-years CivicAtlas explicitly marked *missing*, **our sweep recovered 57**
  (15 clearly-municipal, 32 generic election results, 10 state/federal).
- Of 41 town-years CivicAtlas *located but link-rotted* before download, **35 (85%) are
  now represented** — 25 exact (our sweep re-captured the same `/View/{id}`/URL), 7 as a
  town-year results doc, 3 archived in Wayback (Newton 2021, Lee 2025, Lanesborough 2021).
  Link rot is largely self-healing: the doc that dies at one URL survives at the
  deterministic DocumentCenter id or in the archive.

## The 412 still-missing — what they are
Concentrated in **tiny rural towns** (each missing all 5 years): Gosnold (pop. 70),
Florida, Monroe, Heath, Petersham, Phillipston, Ashby, Brookfield, Conway, Granby,
Hatfield, Lenox, New Braintree, Oakham, Pelham. Plus 96 that are 2025 (post-harvest).

**74% (306/412) already have a CONTAINER document in our corpus** — the results are
embedded but not labelled "results":
- **169 annual town reports** (small towns record election results as a report section),
- 257 town-clerk / board minutes, 167 town-meeting minutes, 40 HTML election pages.

Grep-verified (fetchable sample): annual **town** reports reliably contain results —
Williamsburg 2021 (35 election signals), Charlemont 2024, Aquinnah 2022/23, Brimfield
2021, Clarksburg 2023, Dalton 2025. **Caveat:** an *ACFR* (Annual Comprehensive Financial
Report, e.g. Sudbury) is finance-only and does NOT contain elections — don't count ACFRs.

Because this is a finding project, these count as FOUND: the town-year's results live
inside a document whose URL we already hold. Extraction is a separate (CivicAtlas) concern.

## The ~56 "truly dark" (no file AND no election page in corpus) — diagnosed
Not truly dark — mostly small, fixable coverage gaps:
- **Gosnold** — `gosnold-ma.gov` is a CivicPlus site but was **never in `muni_hosts.txt`**
  (host-list gap). Its clerk page holds permits/forms, **no results docs** though (pop. 70
  likely records results only in minutes/annual report or on paper). Add the host; low yield.
- **Florida** — `townofflorida.org` uses **Sanity.io CMS**; its PDFs sit on
  `cdn.sanity.io` (NOT in the storage allowlist) and it has **no sitemap**. Docs were
  dropped/unreached. Fix: allowlist `cdn.sanity.io` + sitemap-less deep crawl.
- Regional news covers some island/Berkshire towns (Vineyard Gazette for Gosnold/Aquinnah,
  Berkshire Eagle for Florida/Monroe/Heath) — out of scope (NEWS, not LEO).
- A residual genuinely doesn't publish results online (very small towns; posted at town hall).

## Cheap host/allowlist fixes surfaced (document-finding, not processing)
1. Add missing town hosts to `config/muni_hosts.txt` — starting with `gosnold-ma.gov`
   (audit all 351 towns for host-list presence).
2. Add `cdn.sanity.io` (and re-check other headless-CMS CDNs) to the storage allowlist in
   `model.py`, then re-sweep the affected towns.
3. Sitemap-less small-town sites need the browser/deep-crawl path, not docsweep (which
   depends on `/sitemap.xml`).

## Bottom line
The recovery filled real gaps (57 CivicAtlas-missing town-years + 85% of the rotted set).
Of the 412 still open, ~86% (356) are actually held inside annual reports / minutes / HTML
pages we already scraped — a finding, not a miss. Only a small residual of very small
towns is genuinely un-found, addressable by a few host-list / CDN-allowlist additions.
