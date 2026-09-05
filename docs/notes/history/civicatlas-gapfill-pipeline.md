---
name: civicatlas-gapfill-pipeline
description: CivicAtlasMA gap-fill toolkit — the validated scripts for Custom-Search/fetch/ATR recovery and their roles
metadata: 
  node_type: memory
  type: reference
  originSessionId: 007d3b8f-950c-4487-8e4d-9f7f01fe8087
---

CivicAtlasMA gap-fill pipeline (built/validated 2026-08-04), all in `CivicAtlasMA/logs/`. Local
only, no push. See [[civicatlas-2026-sweep]] (fetch-layer fixes), [[civicatlas-google-custom-search]]
(keys in `Python Scripts/.env`), [[civicatlas-coverage-metric]].

**Three complementary recovery tracks — dedup at the parse gate, so overlap is free:**

1. **Single-year Custom Search** (`_gap2026_pilot.py` search+pick -> `gap2026_candidates.csv`;
   `_gap2026_fetch.py` -> staging; `_gap2026_submit/collect/ingest`). Query `"{town} MA {year}
   annual town election results"` -> Haiku picks best result URL -> fetch -> gate. Best for 2026
   and single-gap years. Validated: pilot 10/15, full 2026 sweep +47.

2. **Multi-year landing fetcher** (`_gap_multiyear.py`, reuses `_gap_fetch2.resolve`). ONE
   year-agnostic search -> the town's Election-Results INDEX page -> call resolve() per missing
   year against that page (its Haiku link-picker selects each year's tally). **KEY FINDING: clerk
   'Election Results' pages list only the LAST FEW years, so this recovers recent gaps (2024-2026)
   but NOT 2021-2022** (rolled off -> ATR/Wayback territory). Only worth running on towns that
   PUBLISH (>=2 covered years); sort by most-published, NOT most-missing (most-missing surfaces
   dark-floor tiny towns with no results page). Worklist: 169 publisher-towns / 330 gap-years.

3. **`_gap_fetch2.py` — the robust resolver.** Haiku link-picker + local content-verify + multi-hop
   + retry. Fixed fetch layer (see [[civicatlas-2026-sweep]]); the naive first fetcher under-recalled
   AND grabbed junk. 13/13 recovery precision.

3b. **`_resolve_auto.py` — the AUTO-ESCALATING resolver (2026-08-05, owner-requested; USE THIS for
   hard residual gaps).** Fixes the four residual failure modes the plain resolver couldn't: (a)
   ANCHOR FIRST on the town's KNOWN results page — its other published years' listing-page native_url,
   then `site:{official_domain} election results` — "start on known results pages"; (b) QUOTED search
   `"{town}" Massachusetts "{year}" annual town election results` so the town's OWN page surfaces (Hull
   was returning other towns); (c) AUTOMATIC browser-tier escalation (lazy shared Playwright ctx) when
   a page is JS/portal (Laserfiche `/WebLink/`, govoffice3 `/vertical`, revize viewer, `Browse.aspx`)
   or a curl download returns <120 bytes (0-byte hotlink) — an automatic escalator, not a separate
   path; (d) YEAR-STRICT pick + a deterministic `_year_ok` guard so a 2024 request never grabs the 2025
   doc (the plain resolver's big failure — Alford/Millville pulled 2025 for 2024). Recovered Ipswich
   2024 (deeper hop) where the plain pipeline failed. STILL hard: Laserfiche WebLink doc-trees (Mashpee
   — browser renders but the JS doc-tree yields no direct link) and tiny towns with no online 2024 doc
   (often ATR-only or town-meeting). `resolve_auto(town,year,landings)`; driver builds landings per
   target; `python logs/_resolve_auto.py [Stem ...]` (no args = full 2023/2024/2025 cohorts).

4. **ATR harvester** (`_atr_harvest.py`, BACKGROUND backup). For towns missing >=2 of 2021-25:
   Custom Search -> Haiku picks the ATR archive index -> parse ADID->year (or DocumentCenter
   links) -> download only missing years -> TEXT-scan (free, no OCR for born-digital) for the
   election page -> crop. First run: only 5 staged of ~150 (49 no-archive, 97 no-atr-for-year) --
   the archive-finder + `atr_index()` link-parser are WEAK and need hardening. HARDENED
   2026-08-04 -> 5 to 18 recoveries: two key fixes (a) `Archive.aspx?ADID=` is ROOT-relative,
   build it from scheme+host NOT urljoin against the /334/ index path (was 404ing every CivicPlus
   town — Leicester alone then yielded 2021-2025 from born-digital 200pg ATRs); (b) crop localizer
   must center on the CONTIGUOUS densest results block (score each page = TALLY-count + heading +
   office - state; take peak +/- pages with score>=2), NOT min..max of every scattered OFFICE/TALLY
   hit (was cropping 60-160 pages). Plus a per-year DIRECT search fallback + Content-Disposition
   year resolution. Direct-fallback ATRs are LOWER precision (Dalton x4 all parsed EMPTY -> gate
   caught them). Net: Leicester 0->4 years (2021/22/23/25; 2024 weak crop). Truly scanned ATRs
   logged (`atr_harvest_log.csv`), not processed (need OCR).

**News->official upgrade (HELD by owner 2026-08-05 — prioritize FILLING GAPS over upgrading).**
How it works, for later: 153 published town-years are `source_kind=news`; official docs are often
on one clerk page and FULLER (Westwood 2025 news had 1 race, official had 8).
`logs/_upgrade_ingest.py Stem=native_url ... --apply` replaces news with official ONLY if official
races >= news (never downgrade), sets source_kind=official. **Do NOT touch the 220 `source_kind=
'other'`** — provenance is unconfirmed (could be news or official), owner wants no blind upgrades
there. A future news-only upgrade should be a simple DETERMINISTIC pass, no 'other'.

**2024 has MORE gaps than 2023 or 2025 because 2024 is a PRESIDENTIAL year** (owner noticed the
dip): of 29 towns that have 2023 & 2025 but not 2024, **24 are `discarded_not_results`** — the
pipeline grabbed the high-profile presidential/state-election doc (correctly rejected as
non-municipal) and missed the municipal Annual Town Election underneath. Fix = re-search
municipal-SPECIFIC for 2024 (`logs/_gap_fill_targeted.py` ANOM cohort). Same trap will hit any
future presidential/state year.

**Town-meeting vs ballot — RESOLVED 2026-08-05: it's exactly ONE town, LEVERETT.**
franklincountynow.com/news/216612 states Leverett is "the only town left in the state to elect
their public officials on the floor of the Town Meeting." So EVERY other MA town holds a ballot
election (Gosnold/Florida/etc. DO ballot — they just may not publish tallies, like Conway). Only
Leverett's gap years are true no-ballot; do NOT reclassify any other town on town-meeting grounds.
Leverett handling is a per-owner decision (mark no_election, or capture town-meeting-elected
officers as winner-only from the town newsletter/report). Earlier inference-from-budget was wrong.

**(superseded) Town-meeting vs ballot — earlier UNRESOLVED note:** Owner: don't assume Gosnold elects at
Town Meeting without reading its BYLAWS; but Gosnold's budget has NO line item for a local
election and its report names no election date -> reasonable to infer no ballot election occurs.
Would want an authoritative list of which MA towns hold ballot elections vs elect at Town Meeting
(check MA Sec. of State / MMA / a municipal dataset). Conway DOES ballot but only posts a WINNER
LIST with no tallies (conwayma.gov/n/2182/2025-Local-Election-Results) — parse winner-only
(votes=-1), same as uncontested. Do not reclassify to no_election without evidence. (2) **Landing-fallback gap** — the multi-year sweep's 231 "none" cases
include towns where the picker chose an adjacent info sub-page (Westwood picked
`/voting-elections/election-results` which lists nothing; `/voting-elections` lists every year).
Retrying sibling/parent pages should recover many. **Town-meeting elections are real**
(MGL): smallest towns (Gosnold pop 70 — its whole annual report has ZERO vote tallies; Conway
holds a ballot but prints no tallies in its report, only clerk records) elect officers at Town
Meeting or don't publish tallies -> those years should be `no_election`, not gaps (denominator
fix, pending decision). Parser year-traps still caught by the gate: rotated PDFs misread the year
(Monterey 2025 -> "2027"), news posts emit stray years (Blandford -> "1980"). Coverage 2026-08-05:
81.5% town-years / 93.6% people-years.

**WRONG-TOWN GATE HOLE (found + fixed 2026-08-05).** The auto-resolver sometimes grabbed a
DIFFERENT town's doc (search/landing returned another town; shared CDN; Laserfiche), and the gate
accepted it because it only checked year + municipal-scope, NOT town identity. Caught 9 bad
ingests via a corpus audit comparing each `{stem}.json`'s parsed `municipality` field to the stem
town (Richmond2026=Brookline, Russell2026=Plymouth, Canton2026=Milton, Monroe2026=Monterey,
Shrewsbury2026=Weston, Whately2026=Leyden, Winchendon2026=Templeton, Windsor2023=Peru,
Hancock2026=non-MA townships). FIX: `logs/_gap_multi_ingest.py` now has a `_wrong_town` guard —
reject if a parsed municipality EXACT-matches (after stripping town/ma/township suffixes + townof
prefix) a real MA town that isn't the stem town. Matching MUST be suffix-normalized exact, NOT
substring: 'stow' is a substring of 'massachusettstown' (the parser's generic placeholder) ->
false positive; 'miltonma' -> strip 'ma' -> 'milton' -> real hit. Benign 'unknown'/'Massachusetts
Town' placeholders are ignored (doc IS the right town, parser just didn't fill the field). Audit +
revert tool: `logs/_revert_wrongtown.py`. **Always run the wrong-town audit after any
landing/search-based bulk ingest.**

**TWO INGEST GUARDS now in `_gap_multi_ingest.py` (2026-08-05, after a data-pollution scare):**
(1) `_wrong_town` — reject a parse whose municipality field exact-matches (suffix-normalized) a
DIFFERENT real MA town. (2) **already-published skip** — gap-fill ingest must NOT overwrite a row
already `coverage_state=published` (only `no_source` gaps); deliberate replacements go through
`_upgrade_ingest.py` (or `--allow-overwrite`). ROOT CAUSE of the scare: the auto-resolver
overwrote already-published rows, and gap-fill had no town-identity check. **Full forensic result
(local, from the master_urls.pre_*.csv backup chain):** the 9 reverted wrong-town town-years
(Shrewsbury/Hancock/Monroe/Whately 2026 etc.) were wrong from the ORIGINAL 2026 sweep — NOT
good-data-that-got-clobbered (their json_2026 originals were also Weston/Monterey/garbage;
quarantined to `data/_quarantine_wrongtown/`). The ONLY published->published source changes across
ALL backups were the 4 intended Westwood upgrades. **Data-quality tiers of 1,600 published
town-years: 96.1% town-confirmed (parsed muni == town), 2.7% unknown-field-but-own-domain, 0.2%
generic-source (all verified fine), 1.0% no-source-url, 0 wrong-town.** So ~99% high-confidence.
Audit tools: `_revert_wrongtown.py` + the tier/overwrite audits. **Run the wrong-town audit + the
already-published guard after every landing/search bulk ingest.** Shrewsbury2026 + the 8 others are
now HONEST gaps needing correct sources (Shrewsbury official URL:
shrewsburyma.gov/DocumentCenter/View/20886, host was flaky).

**Merged-model ingest**: 2026 is a normal year in master_urls now, so ingest flips a town's
`no_source` row -> published (json -> data/json, doc -> publish/pdfs; back up master first).
Year/scope gate rejects wrong-year + NON_MUNICIPAL (catches the Rockland-2024 presidential-primary
trap). Report Haiku batch cost before every `submit` (~$0.006/doc); parse is BATCH never sync.
