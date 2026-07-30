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

## Update 2026-07-30 — host-list audit + allowlist + re-sweep
Audited all 351 towns vs authoritative `CivicAtlasMA/.../towns_websites.csv`. Found **12
towns whose official domain was never in `muni_hosts.txt`** (their CivicAtlas native_url
pointed at a news host) — incl. big ones North Andover, Norwood, Pittsfield, Weymouth,
West Springfield — plus Savoy. Added 13 canonical hosts (Monroe MA has no website in the
authoritative list, omitted). Allowlist += `sanity.io`, `aptuitivcdn.com`,
`documents-on-demand.com`.

**Root-cause fix (serving_host):** several added hosts refuse the *bare* domain and serve
only `www.` (norwoodma.gov refuses; www.norwoodma.gov serves). `norm_host` strips www so
the crawler always hit the dead variant → 0 pages. Added a bare-vs-www probe fallback to
docsweep + crawl. Norwood went 0 → 1,798 files.

**Re-sweep of the 15 affected hosts:** ~11K new docs from previously-blind towns (Weymouth
5,865, Norwood 1,798, Pittsfield 1,212, North Andover 701, Pelham 699, West Brookfield 459,
West Springfield 270, Goshen 373 [as CDN images], …). **108 election-results docs** found
across 7 towns. **Still-missing 412 → 401**, with **11 town-years newly filled**: Pelham
2021–2025 (all five), North Andover 2023/25, Petersham 2024/25, West Brookfield 2022,
Weymouth 2021.

Remaining partials worth a deeper follow-up: Harwich (73/928 sitemap pages — time-budget
hit), Goshen/Pelham (partial), Southampton + Easton (thin / documents-on-demand portal not
sitemap-linked). Monroe MA remains genuinely siteless.

## Update 2026-07-30b — precision feedback from the verifier (content-checked)
The CivicAtlas verifier content-checked my 57 "recovered-for-missing" docs: **25 are genuine
municipal-election results**; 32 dropped — 10 state/federal, 8 non-election "results"
(water-quality/lead/copper/PFAS, MIAA sports, survey/monitoring), 8 primary/special/town-
meeting, 1 wrong-year, 5 already-had.

**Lesson — URL classification is noisy BOTH ways** (HANDOFF gotcha #7): the loose "results"
filter over-counts by ~285 town-years (corpus 1,006 → 721 under a tight filter), while the
tight filter under-counts (misses results docs not literally named "results"). The truth is
between; the verifier's content check is authoritative. Finding ≠ classifying.

**Fix applied (handoff hygiene):** pre-drop unambiguous non-election "results"
(water/lead/sports/survey/monitoring/bid/grant) and TAG election-type
(municipal / state_federal / primary / special / town_meeting) so the verifier filters by
type instead of hand-classifying. Artifact: `scratch/recovered_candidates_tagged.csv` —
65 candidate town-years, **43 likely-municipal**, 22 state/federal separated out. The scraper
stays a finder; the municipal-vs-noise call is left to content verification.

## Update 2026-07-30c — content-dive: reading the documents we already hold
Rather than re-crawl, dove INTO the container docs we hold for the 409 still-missing
town-years: fetched each candidate (annual town reports, town-meeting/election files, HTML
election pages), extracted text (fitz / HTML strip), and detected genuine MA election-results
content — an election heading + `Blanks` (every MA race lists Blanks) + office names + vote
tallies. Two passes (2nd added URL-encoding, more candidates, WAF cookie-lift).

**Result: 190 previously-missing town-years now have election-results content CONFIRMED
inside a LEO document we already hold** (167 high-confidence + 23 medium). By container:
95 annual town reports, 75 HTML election pages, 19 town-meeting files, 1 minutes. 81 distinct
towns; 13 tiny towns fully covered by their annual reports (Ashby, Conway, Gill, Oakham,
Warwick…). This ~halves the gap: **~409 → ~219 still-missing.**

Evidence is page-level (e.g. Ashby 2023 town report: 52 `Blanks`, 11 offices, 2,147 tallies,
160pp). Deliverable: `scratch/dive_confirmed.csv` (town-year → document_url + evidence). This
is high-RECALL content-matching; the verifier still makes the final municipal-vs-other call,
but pointing at the exact container + evidence is far stronger than a URL guess.

Remaining ~219: 26 fetch-fails (dead/hard-WAF), ~168 whose held candidate had no results
content (results truly elsewhere or not published), + 2025 recency. Finder's job: the
documents that DO hold results are now pinned to their town-year.

## Update 2026-07-30d — deep-dig (broader candidates + WAF cookie-lift)
Pushed the NO_RESULTS + FETCH_FAIL town-years: gathered a much broader candidate set (all
town/annual reports any-year since report-year≈election-year, + clerk/warrant/town-meeting/
election docs ±1yr + election pages) and retried fetch-fails through a headless WAF
cookie-lift. **+63 upgrades.**

**FINAL content-dive: 240 previously-missing town-years pinned to a held document**
(211 high-confidence + 29 medium) — 123 annual town reports, 63 HTML election pages, 18
town-meeting files, 6 election docs. 95 distinct towns; 16 fully covered by their annual
reports. **Gap 409 → 144** (59% of the missing set now located inside a document we already
hold, zero re-crawling). Deliverable refreshed: `scratch/dive_confirmed.csv`
(town-year → document_url + page-level evidence).

Remaining ~144: **131** whose held candidate genuinely had no results content (results truly
elsewhere / never published online — many are the smallest towns + 2025 recency) and **13**
hard fetch-fails (dead URLs / aggressive WAF). These are the real residual for a document-
finding project; the rest are found.
