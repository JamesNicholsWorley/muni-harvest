---
name: civicatlas-2026-sweep
description: "CivicAtlasMA 2026 collection: URL templating fails (1.7% backtest), discovery via muni-harvest Actions is the route"
metadata: 
  node_type: memory
  type: project
  originSessionId: 007d3b8f-950c-4487-8e4d-9f7f01fe8087
---

CivicAtlasMA 2026 municipal results collection (started 2026-08-03). See
[[civicatlasma-project]], [[civicatlas-env-tarpit-ci]], [[civicatlas-google-custom-search]].

**BEST ROUTE (validated 2026-08-04): Google Custom Search + Haiku picker.** Beats the
3.27M-node muni-harvest crawl for 2026, and proved WHY: Leicester was crawled exhaustively
(8,352 nodes incl. its ATR archive `ArchiveCenter/Item/320-395`) yet is a total blackout,
because the election tally lives INSIDE 150-page ATRs behind opaque URLs the URL-classifier
tags `doctype:"other"`. Breadth didn't fail, recognition did; Google read the pages we only
indexed. Pipeline (per gap town-year): 1 Custom Search query -> hand first-page 10 results
(title/url/snippet) to Haiku (sync routing call, NOT batch — routing, not doc parsing) ->
Haiku returns best official-results URL + type -> deterministic fetch (curl_cffi; follow
clerk pages to the results PDF) -> existing parse+scope+year gate. Guardrails baked into the
picker prompt (from muni-harvest HANDOFF gotchas): exclude ACFR (finance-only; narrative
Annual Town Report is fine), reject state/primary/presidential + wrong-year, "results" is
polysemous. **Pilot: 10/15 recovered end-to-end (67%), ~$0.18** (search free <=100/day then
$5/1k; Haiku picker ~$0.01; parse $0.17). Scripts: `logs/_gap2026_pilot.py` (search+pick ->
`logs/gap2026_candidates.csv`), `_gap2026_fetch.py` -> `data/staging_2026/`, `_gap2026_submit.py`,
`_gap2026_collect.py`, `_gap2026_ingest.py` (merged model: flips the town's 2026 no_source row
in master_urls to published). Keys in `C:\Users\Owner\documents\Python Scripts\.env`.

**THE FETCH LAYER, NOT CONTENT, MADE TOWNS LOOK "EMPTY" (fixed 2026-08-04).** In the first
2026 sweep, 59/112 parsed EMPTY — but Norwood/Stoughton (two of the largest) DO publish
results; the failures were fetch/link-follow, not missing data. Root causes: (a) a clerk page
lists EVERY year's election, and a naive scorer grabbed the wrong year (Stoughton pulled a
2024 STATE doc — my "ate" hint token also matched "St-**ate**"); (b) hardcoded CivicPlus-only
doc patterns missed Revize `_assets_`, off-host CDN PDFs (cms5.revize.com, ProudCity
storage.googleapis.com), govoffice, opaque filenames (`PCT-1-05042026.pdf`). **Fix =
`logs/_gap_fetch2.py`:** fetch the picked page -> hand its links (url+anchor) to a HAIKU
link-picker that returns the one real RESULTS tally for the target year (rejects warrants,
specimen/sample ballots, calendars, applications, wrong-year, state/primary — a regex can't
disambiguate these, Haiku can) -> local content-verify the fetched PDF (office names +
blanks/write-in/precinct tally; reject ANTI: article N/warrant/specimen/calendar/handbook;
scanned no-text is ALLOWED, parses via vision) -> multi-hop (clerk -> news/detail -> PDF,
depth 2). MUST retry on `APIConnectionError` and skip already-staged files (a mid-run network
blip otherwise loses progress). **Validated: 13/13 recovered from the "empty" bucket parsed to
clean municipal results, 100% precision** (Buckland results-not-warrant, Hudson election-not-
specimen-ballot, Merrimac keyword-less filename, Mansfield from a no-pick). Lesson for
2021-2025 + ATR scaling: **use this fetcher, not the first naive one** — the naive one both
under-recalls (opaque filenames) and grabs junk (dog licenses, handbooks). Coverage after:
2026 194->207 (69.9%), overall 2021-2026 78.9% town-years / 92.6% people-years.

**ATR IDENTIFICATION without downloading/OCRing (validated on Leicester 2026-08-04):** you do
NOT need to blind-download+OCR opaque archive items. (1) The CivicPlus archive INDEX page
`Archive.aspx?AMID={id}` lists every item as `<a href="Archive.aspx?ADID={n}">TITLE</a>` +
`<img alt="TITLE">` — one GET maps ADID->year->title for ALL items (Leicester: 13 ATRs, ADID
320=2021 ... 629=2025). (2) `Content-Disposition` via a Range GET (`Range: bytes=0-0`) returns
the original filename + size + content-type with NO body (HEAD 404s but ranged GET 200s). So
the ATR track = Custom Search finds the archive index -> parse ADID->year -> download only the
MISSING years -> OCR only first ~3 pages (cover=year, TOC=election-results page #) -> crop that
page -> parse. Never OCR the 150-page whole; never fetch irrelevant docs.

**Do NOT try to predict next-year URLs by substituting the year.** Backtested properly:
hide each town's real 2025 URL, generate candidates from its 2021-2024 URLs, check for a
match. Result across 294 towns: **HIT 5 (1.7%)**, ID_ADDRESSED 159 (54%), MISS 95,
NO_CANDIDATES 35. Municipal filenames churn between years
(`athol_election_results_4-5-2025_0.pdf` -> `athol-election-results-4-7-2025`) and over
half of all documents sit behind an opaque CMS id (`DocumentCenter/View/3318/...`) where
the year appears only in a decorative slug the server discards. Rewriting that slug
returns the OLD document under a new-looking name — the exact wrong-year contamination
cleaned up in the prior session. **Discovery, not prediction.**

What IS stable is the DIRECTORY, not the filename — misses landed in the right folder.

**Scoping:** towns = municipalities with `expected=yes` in an even year (cities are
odd-year only). 297 towns; 296 have a known domain (Monroe has no website at all).
262 have a 2026 date predicted from prior years — bylaws fix a weekday-of-month ("third
Tuesday in May"), so (month, weekday, occurrence) carries across years, the day number
does not. Predicted months: Mar 17, Apr 62, May 164, Jun 18 — all past by August.

**Four angles dispatched on muni-harvest Actions** (branch `y2026-sweep`, merged to main;
a NEW workflow file must be on the default branch before `gh workflow run` can find it):
- `docsweep-shard` (sitemap whole-site doc sweep) `hosts_file=config/y2026_town_hosts.txt`
- `discover-shard` (deep link crawl) — added a `hosts_file` input, was hardcoded
- `dc-idsweep-shard` — added `--headroom N`: the gap list is `range(1, top+1)` bounded by
  the committed manifest's highest id, so documents posted SINCE the manifest was built
  are unreachable by construction. That is exactly the current-year case. Stops after 150
  consecutive misses. Ran with `per_host_cap=200 headroom=1500`.
- `news-rss-2026` (NEW, stdlib Google News RSS, no key/quota) — 102 of 297 towns have
  never yielded a document from their own domain; local papers are the only record.
  Filters on the FEED publication year, not the URL slug (reused slugs are a known trap).

**Local side (no network):** `CivicAtlasMA/logs/_y2026_harvest.py --nodes <dir>` scores the
merged `nodes_*.jsonl` artifacts into `logs/y2026_candidates.csv`. Requires positive 2026
evidence and REJECTS a node naming a different year — a "2025 Annual Town Election Results"
file still on the site in August 2026 is last year's.

Retrieve with `gh run download -n docsweep-merged` (also `discover-deep-merged`,
`dc-idsweep-merged`, `news-rss-2026-merged`). Per-SHARD artifacts upload as each job
finishes, so partial results are readable long before a run ends (job logs are not --
`gh run view --log` refuses until the whole run completes).

**Three scoring traps found by dry-running the harvest on partial artifacts (2026-08-03):**
- A predicted-date match must NOT excuse a competing year. Dates are (month, weekday,
  occurrence), so day numbers recur: Avon votes April 14 in both 2015 and 2026, and
  `April-14-2015-Town-Election-Results` ranked as the best 2026 candidate in the sweep.
  Any other year now disqualifies outright; the year range must span 1900-2099 (a
  2010-2025 range let `April-14-2009` through).
- Host->municipality via `setdefault` silently gives a SHARED VENDOR STORE to whichever
  town is seen first -- `storage.googleapis.com/juniper-media-library` serves dozens of
  towns and filed Savoy's and Cheshire's results under Goshen. Drop any host claimed by
  >1 town (6 excluded, 4 of them newspaper domains).
- **Google News town-name search is ~2/3 false positives.** MA town names are reused
  nationally and abroad: Barre VT, Canton OH (cantonrep), Chester SC + Port Chester NY +
  Chester ENGLAND, Conway NH. Requiring only the town name is not enough -- require MA
  evidence (known MA-only outlet, explicit "Massachusetts", or published within ~10 days
  of the bylaw-predicted date). 978 raw -> 736 deduped (3 query templates repeat
  headlines) -> 248 kept across 117 towns. Date-proximity is the weaker test; NH/VT hold
  March town elections too. `logs/_y2026_news_filter.py` does this; rejects are written
  to `logs/y2026_news_rejected.csv`, never silently dropped.

**NEWS SOURCES ARE PARSEABLE — do not claim otherwise.** Local papers print the full
tally and the parser handles them: of the 183 `source_kind=news` rows in master_urls.csv,
142 (86%) parsed into races+candidates (952 races, 2,487 candidates) — the same rate as
official sources (87%). Own-domain and news are still tracked separately, but only
because they need different FETCH paths (news rows are news.google.com RSS redirect
stubs needing resolution to the publisher), not because one is unusable.

**When checking parsed JSON, the top-level key is `elections`, NOT `races`.** Reading
`d['races']` returns 0 for every file and looks like proof that a source type never
parses. That bug nearly confirmed the false "news isn't parseable" claim.

**Saugus is an odd-year November city-style town** wrongly marked `expected=yes` for
2024, which pulled it into the 2026 worklist with a predicted date of 2026-11-03. It is
the ONLY town whose even-year expectation disagrees between 2022 and 2024. 2026
denominator should be 296, not 297.

**Diagnose "missing" towns by CRAWL DEPTH before calling them absent.** Of 102 towns with
no 2026 candidate, only 45 had 500+ nodes crawled; 48 were never or barely reached. 35 of
the 102 have perfect 5/5 prior-year coverage — for those, absence is a sweep failure, not
a dark floor. Only 7 have 0/5 prior coverage.

**The tier cache never reaches GitHub Actions — `data/` is gitignored (`.gitignore:2:/data/`).**
`data/tier_cache.jsonl` holds 441 host tiers locally; on the runner the file does not exist, so
`pipeline.run()` defaults EVERY host to T0 and prints "0 via browser tier". In the 2026 re-crawl
(run 30872361836) 35 of 50 requested hosts returned `pages=0` in under 30s: 21 of them are known
T1/T2 hosts that need the browser, got a stdlib crawl, and were refused by the vendor WAF. The
403s cluster on shared CMS IPs (34.196.1.111 x8, 89.106.200.153 x7, 135.84.124.41 x4).
**`crawl_site` logs a host that fetched ZERO pages as `[OK] files=0 pages=0`** — indistinguishable
in the log from a host that was crawled and genuinely had nothing. Fix the reporting before
trusting any "we swept it and found nothing" claim. Corroboration that the tier data is good: the
4 hosts an independent HTTP probe found unreachable (SSL handshake failure x3, timeout x1) are
exactly the 4 the tier cache already marks `blocked`.

Distinguish the failure modes — they all wore the same "never reached" label: (a) slow hosts that
ate the job clock, fixed by `per_host_seconds`; (b) WAF-blocked hosts that fail in seconds, which
the time budget does nothing for; (c) robots.txt blanket bans; (d) a 429 on the homepage, which
loses the whole host because the homepage is the crawl root (was `tries=1`).

FIXED in muni-harvest `4c65dc5`: tier cache ships via `config/tier_cache.jsonl` + a workflow copy
step, `pip install -e ".[live]"`, `BROWSER_TIERS` now includes `blocked` and `needs_unblocker`
(130 + 40 hosts vs only 71 T2 — the old T1/T2-only test missed most browser-required hosts),
`crawl_site(stats_out=...)` names the outcome, orchestrator prints `[EMPTY]` + reason, and
audit.log/stats.jsonl upload as artifacts. Regression test:
`CivicAtlasMA/logs/_y2026_verify_outcomes.py`.

**Four towns publish `User-agent: * / Disallow: /`** (Easton, New Braintree, Barre, Palmer) —
allowing only Googlebot/Bingbot. The last three files are byte-identical, so it is a CMS vendor
default, not four town decisions. Excluded from crawling pending an owner decision; do NOT
silently override robots on government sites.

**`has_json` in master_urls.csv is unmaintained** — 1,349 JSON files exist on disk, the
column admits 130, and 178 rows say `no` where the file exists. `parse_corpus collect`
writes the file without updating the flag. Never report coverage from that column; also
note ~203 `discarded_not_results` rows retain JSON on disk, so counting files overstates
coverage too.

**A "low-file" crawl usually means unreached, not empty — three defects, all fixed in
muni-harvest `925d271` (2026-08-04, verified end-to-end):** diagnosed by re-crawling the
retry hosts LOCALLY (residential IP + curl_cffi, see [[civicatlas-env-tarpit-ci]]).
(1) **Extensionless CMS document alias — the big one, corpus-wide.** `is_file_url()` keyed
on extension, so the Granicus/Vision GovAccess friendly URL `/<section>/files/<slug>`
(302-redirects to `/sites/g/files/vyhlif.../f/uploads/*.pdf`) was queued as a PAGE, fetched
as HTML, and never emitted as a file — the crawler visited each document and recorded
nothing. 258 of the 12 retry hosts' page-nodes (7%) were mis-filed this way; this CMS runs
a large share of the 351 towns. Fixed by adding the alias to `_DOC_ENDPOINT_RE` (the
`/pages/` HTML namespace stays crawlable). (2) **Off-site doc portals** (Laserfiche) were
dropped by `same_site`; now `is_doc_portal()` follows them for browser-tier expansion.
(3) **Truncation:** 6 of 9 retry hosts stopped at exactly 200 pages, all mid-BFS-depth-3;
raised `max_pages_browser` 200->400 and seed clerk/election pages on every host so the
results archive crawls at the front of the frontier. Proof: a real hadleyma.org crawl went
23 -> 379 files, archive 2012-2025 incl. the missing 2025 town-year.
**Implication for a full re-sweep:** defect (1) means most prior crawls under-collected
GovAccess towns; a re-run under `925d271` is warranted but is CI time — scope before running.
**Measured yield (batch msgbatch_01HLSxcoC2NhNBtiX2sgU7i2, 249 docs, $2.42 Haiku batch,
2026-08-04):** of 59 recovered 2021-25 candidates only **9 parsed to real municipal
results** (50 EMPTY); of 190 2026 docs **127 clean** (58 EMPTY, 5 MALFORMED news
roundups). Lesson: the alias fix truly SURFACES the docs, but most GovAccess towns publish
town-meeting "doings"/warrants/annual reports, not a discrete candidate-election tally —
reachable != results, so the 2021-25 gap ceiling is far below the 184 open gaps. 2026
own-domain+news is the higher-yield cohort. INGESTED 2026-08-04 (local, no push): 11
clean 2021-25 flipped to published in master_urls (coverage 77.4%->78.1%, 1274->1285);
131 clean 2026 recorded as a SEPARATE cohort in data/inventory/y2026_hosted.csv (json in
data/json_2026), master_urls untouched for 2026. Two parser gotchas seen this batch:
(a) news prose makes Haiku emit `elections` as a JSON *string* with `"votes": <UNKNOWN>`
placeholders (fixed by a news-aware re-parse: "votes MUST be a JSON integer, -1 if
unstated, return a native array"); (b) the gate's one-best-per-year pick can lose to an
untried alternative -- Monterey/Washington 2022 had a proper "Election Results" PDF the
gate skipped (recovered via logs/_unused_candidates.py bucket A). Remaining leads:
119 prior-year town-years with NO results file in the crawl (need news/other source),
~85 of 296 2026 towns with no lead, 10 paywalled 2026 news, and Westminster2025 (results
doc is login-gated). Staging pipeline scripts: CivicAtlasMA/logs/_parse_{gate,fetch_stage,
count,submit_staged,collect_staged}.py, _ingest_staged.py, _unused_candidates.py.

**Wayback DOES recover prior-year results pages a live crawl can't** — a page that existed
then and was removed before the 2026 crawl survives only in archive.org. Confirmed
2026-08-04: probed all 359 gaps via the CDX API, 224 raw hits, but only **34 "strong"
(target year in URL, municipal) + 22 landing** after filtering out wrong-year (Springfield's
was 2009, Easton's 2018), state/presidential, and town-meeting/survey noise. Fetched 56,
parsed, year-checked (reject unless a parsed election date == target year), **12 clean
ingested** (coverage 78.1->78.8%). Yield << URL count because most town "official-results"
pages are ANNOUNCEMENTS linking to a PDF or JS widget — neither tag-strip nor trafilatura
gets the tally. A link-follow pass (parse the archived HTML's <a href> for a results PDF,
fetch it from the SAME Wayback capture via web/<ts>id_/<absurl>) added 4 more
(logs/_wb_linkfollow.py); the year-check caught a link-follow PDF that was actually 2018.
Works ONLY on larger, archived towns — the 119 tiny towns have 0 Wayback captures at all.
**CDX query gotchas (each silently returned 0):** an inline `(?i)` flag in `filter=`;
`matchType=prefix` combined with a `/*` wildcard url. Use `url=host&matchType=domain&filter=
urlkey:.*(result|election).*` (validate against a known-good town first). Scripts:
logs/_wb_{fetch,submit,collect,validate,ingest}.py, wayback_worklist.csv.
Google News was ALREADY run for 2021-25 (183 news rows in corpus); do not re-sweep it.
The two `robots_disallow` holdouts are also resolved (`a4cf0ee`): westhamptonma.gov is a
polite override; cms3.revize.com needed only a wildcard-`Allow` parser, no override.
