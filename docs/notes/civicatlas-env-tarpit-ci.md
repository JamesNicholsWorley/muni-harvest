---
name: civicatlas-env-tarpit-ci
description: "CivicAtlasMA — curl_cffi impersonate=chrome beats MA municipal WAFs LOCALLY; residential IP beats CI, which is the opposite of the old assumption"
metadata: 
  node_type: memory
  type: project
  originSessionId: 007d3b8f-950c-4487-8e4d-9f7f01fe8087
---

For CivicAtlasMA election-results recovery (see [[civicatlasma-project]], [[collect-missing-results-runbook]]):

**LOCAL IS BETTER THAN CI FOR WAF HOSTS (measured 2026-08-04) — this reverses the original
headline of this memory.** `curl_cffi.requests.get(url, impersonate="chrome", verify=False)`
from this machine gets **200 + 84-298 same-site links** on every host GitHub Actions reported as
`waf_403` or a dead 1-page crawl (hamiltonma.gov, sandisfieldma.gov, brimfieldma.org,
hadleyma.org, huntingtonma.us, townofbecket.org, wilmingtonma.gov, brewster-ma.gov,
townofrowley.net, westboylston-ma.gov). muni-harvest HANDOFF.md 3.5 already said it: *"Datacenter
IPs are worse for WAF-protected sites (browser tier) but fine for archive.org. Keep the browser
tier on residential IPs."* curl_cffi is installed globally under `C:\Python314` (no venv).
- **Diagnostic trap to avoid:** probing these hosts with stdlib `urllib` returns 403 or
  "certificate is not valid for <host>" and looks exactly like an IP block. It is not — it is the
  WAF serving a default cert/challenge to an un-impersonated TLS fingerprint. Always probe with
  curl_cffi before concluding a host is unreachable from here.
- Two hosts are genuinely moved, not blocked: `townofberkleyma.com` -> `townofberkleyma.gov`,
  `townofpaxton.net` -> `paxtonma.gov` (both now in muni-harvest `config/host_overrides.csv`).
  `westboylston-ma.gov` apex fails TLS but `www.` works — a www-retry, not a domain change.
- muni-harvest crawler now PREFERS impersonation over selenium for WAF tiers (commit `8aa60ef`),
  escalates to it on 403 or a homepage network error, and CI asserts curl_cffi is importable so
  the tier cannot degrade silently.

**Environment constraint discovered 2026-07-31:** From this local machine, direct byte-download
(`resource_urls.fetch_bytes` — requests/curl_cffi/stealth-browser) is **tar-pitted (~45s hangs → fail)
on ~half of MA municipal WAF hosts** (CivicPlus/GraniteDoc `sites/g/files/vyhlif...`, some CivicEngage).
The read-only agent tools (WebFetch/WebSearch) reach those hosts fine (fast 404s / content), so the
tar-pit is **IP-reputation-based against this environment**, not the sandbox (persists with sandbox
disabled) and not TLS-fingerprint (curl_cffi also hangs). Belmont/DocumentCenter and news hosts
(patch, wwlp, capenews, 959watd) are NOT tar-pitted and fetch locally fine.

**Consequences / working approach:**
- Deterministic same-URL refetch (`refetch_missing.py`) has LOW yield here: most failed `native_url`s
  are genuine 404s (docs moved), and byte-download tar-pits anyway. Recovery is a SEARCH problem.
- **Agent finder is the primary mechanism** and runs fine here: `workflows/find_results.workflow.js`
  (rewritten LEAN — one search-only agent per town, NO whole-PDF fetching). Measured ~26K tokens/agent,
  ~94/150 candidates found on the top-150-by-population batch. `build_targets.py` emits the ranked
  target JSON; `triage_finder.py` classifies each found URL reachable-doc / reachable-html / unreachable.
- **Byte-download for tar-pit hosts → GitHub Actions on the muni-harvest repo** (clean runner IP; its
  stdlib-urllib scraper already gets through these WAFs). Prepared (uncommitted, on main working tree,
  needs branch+commit+push+dispatch — CONFIRM with owner, it's outward-facing):
  `muni-harvest/scripts/fetch_url_batch.py` (self-contained stdlib+curl_cffi sharded fetcher),
  `.github/workflows/url-batch-shard.yml` (workflow_dispatch, artifact output), input
  `config/election_urls.csv` (municipality,year,url,alt_url). Retrieve via `gh run download -n
  url-batch-merged` → ingest into CivicAtlasMA.

**ROOT CAUSE FOUND (2026-08-01): mass CMS migration, and the Wayback Machine is the recovery
path.** Many MA towns migrated CMS in 2025-26 (Granicus/Drupal -> CivicPlus); every old
`/sites/g/files/vyhlif...` and `/home/news/...` URL died wholesale (Google snippets still show the
old content — stale cache). Three consequences:
1. **Wayback sweep is the highest-yield recovery for dead URLs**: `src/wayback_recover.py` (CDX
   per-host enumeration of archived election PDFs, existed already) + `src/wayback_sweep.py` (new
   driver: match archived PDFs to missing years by URL-slug year, download `id_` raw snapshot with
   plain requests — archive.org NOT blocked locally). Test: 8/10 missing years matched on 5
   dead-URL towns. **archive.org rate-limits hard** — pace ~6s/download, backoff on 429, retry CDX
   once after 25s; sweep is slow-but-free, run in background.
2. **The new-CMS paths fetch FINE locally** (Holden/Millbury DocumentCenter PDFs: 1s). The
   "tar-pit" was mostly dead old-CMS paths hanging, not a blanket IP block. So: resolve the town's
   CURRENT election index (WebFetch reads everything) -> extract the real href -> plain local
   download usually works. GitHub Actions fetch rarely needed.
3. **Finder must return VERIFIED LINK PAIRS** (doc_url + source_page + link_text, copied from a
   page the agent actually opened — never constructed). Rebuilt in find_results.workflow.js. The
   pair is re-checkable and kills hallucinated/guessed URLs.

**Reprocessing pipeline for found-but-unprocessed pages** (the big earlier leak — 139/150 found but
only 16 recovered): news articles -> `render_html_local.py` (Playwright+Docling, local, no push;
53/62 rendered) -> parse; official index/landing pages -> `resolve_candidates.py` (extract+rank
links, download-verify) or manual WebFetch href-extraction for blocked pages; dead URLs -> wayback
sweep. `manual_finds.csv` is ALSO load-all/save-all — never run wayback_sweep --queue concurrently
with ingest_finds or another finds-writer.

**CI url-batch result (2026-07-31): 0/19.** The first `election_urls.csv` run fetched nothing —
NOT because the runner is blocked, but because the search-only finder's *guessed* gov-PDF paths for
tar-pit towns are dead 404s (confirmed via WebFetch). Lesson: **CI url-batch only helps for VERIFIED
URLs.** For tar-pit gov docs whose real path is unknown, the right tool is site DISCOVERY —
muni-harvest's existing `docsweep`/`dc-idsweep` sharded crawlers (crawl the host, find the real
current DocumentCenter/vyhlif URL), then fetch. Don't feed guessed URLs to url-batch.

**Finder batch sizing: ~150 agents/run hits the account session limit** ("You've hit your session
limit · resets <time> ET"). Batch 1 (150) squeaked through (~3.85M tok); batch 2 (150) throttled
after ~14 agents. Run finder batches of **~60-80**, or space them across resets. Resume is possible
via `resumeFromRunId` but session-limit-failed agents don't cache, so most re-run — prefer rebuilding
targets with `build_targets.py --exclude <prior batches>` and running a fresh smaller batch.

**Finder efficiency (measured 2026-08-02):** the cost driver is TURN COUNT — un-capped agents made
~32 tool calls per completed find (~50K tok each; context re-sent each turn). Fix: a hard "AT MOST
8 tool calls, stop at first verified pair, no proxy workarounds" line in the prompt → **9.4
calls/agent, ~26K tok/agent, same find quality** (verified pairs incl. annual-report page cites).
**Haiku does NOT work** for these schema-forced finder agents: 7/10 never called StructuredOutput
despite nudges, ignored the tool budget, 0 finds — keep the default model. Session window budget is
~1.4-1.6M subagent tokens → ~55-60 budgeted agents per window.

**Finder economics:** ~26K tok/agent; batch 1 = 94 candidates/150 (63% find rate) among larger towns;
smaller towns (batch 2) trend lower + more paper-only dark-floor. Triage split (batch 1): 16 reachable
PDF, 59 reachable HTML (news/pages), 19 unreachable. Reachable PDFs host+parse cleanly; ~23 valid/25
parsed. Pipeline: `build_targets` -> Workflow finder -> `triage_finder` -> `append_finder_finds --kind
doc/html` -> `ingest_finds --apply --only` -> `parse_corpus submit --new`.

**Wayback sweep outcome (2026-08-01): 199 PDFs recovered / 203 matched across 166 towns** — even
tiny towns (Savoy, Rowe, Mount Washington) matched; the paper-only dark floor is far smaller than
assumed. ~10 downloads arrive truncated/corrupt under rate-limiting — validate with
`len(PdfReader(...).pages)>=1` (construction alone misses subtle corruption) before ingest; retry
later. Of 192 ingested, 71 parsed valid (679 races), 122 EMPTY (CDX slug filter is high-recall; the
scope gate zeroes minutes/state docs — expected, costs ~$0.005/doc).

**Year-gate referee pattern:** `year_check.py --apply` reverts EVERY flagged mismatch, including
out-of-range false positives (term-expiry dates) — NEVER run it blind. Instead referee each in-range
mismatch against the PARSED election dates in `data/json/{stem}.json` (Haiku reads the real election
date): parsed-dates-match-assigned = KEEP (regex fooled), parsed EMPTY/absent/disagreeing = targeted
revert (see logs/_revert29.py pattern). Caught 5 keepers out of 34 flags. News reused-slug traps are
real: a "2021"-slugged article can serve the 2023/2025 election.

**Wayback works for NEWS/HTML too, not just PDFs (2026-08-02):** `src/wayback_html.py` — for a
paywalled/nav-shell/failed render, CDX-enumerate captures of that EXACT url, prefer captures from
the election year, fetch raw `id_` snapshot, Docling->markdown, and keep ONLY if it beats the
incumbent render (score = tally-words*12 + "Name 412" line-shapes + digits). Yield: 19 improved /
107 tried; near-100% on *failed* renders (Walpole2022, Orange2024, Warwick x2, Aquinnah2021,
NewSalem2025, Greenfield2023), low on live paywalls (the archive captured the paywall too). Two
traps: (a) score MUST strip markdown links/URLs first — asset GUIDs and utm params in share links
made a Berkshire Eagle paywall shell outscore a real article; (b) guard Docling against PDF/zip
magic bytes — an html-named PDF falls through to OCR and grinds for many minutes. Log every
adjudication so the job resumes without re-fetching (archive.org pacing makes it slow).

**Agents cite PRINTED page numbers, not PDF indexes** (Cummington FY2024: printed 64 = PDF 66;
Boylston2025 shift +5). `crop_hosted_reports.py` now VERIFIES the cited pages hold HEAD+TALLY, falls
back to auto-detect, and if neither confirms keeps the cite anyway (scanned pages have no text
layer). Never add `--restore` to a bulk crop run without checking: it reverted two good crops to
full 174pp reports.

**Google Drive-hosted results** (Windsor): rewrite `drive.google.com/file/d/{id}/view` ->
`drive.usercontent.google.com/download?id={id}&export=download` or the probe sees an HTML shell.
Drive FOLDER links have no single doc behind them — reject, don't queue the listing.

**Tiny-town find rate (batch 8, the 75 never-searched smallest towns, pop 70-989): 17/75 = 23%**
vs 63% for large towns. 2.10M tokens, 10.9 calls/agent. Adding "results may live inside the Annual
Town Report; put tally page numbers in notes" to the finder prompt is what got Cummington/Middlefield.
Regional weeklies (Berkshire Eagle, Greenfield Recorder, MV Times, Vineyard Gazette, iBerkshires)
are often the ONLY record. Monroe has no town website at all.

**Dead-end ledger (2026-08-02):** `src/deadend_ledger.py --write` joins every attempt log
(wayback_sweep, wayback_html, queued_pairs, render_html_local) onto the residual worklist and emits
`logs/deadend_ledger.csv` + `logs/paywalled_sources.csv`. At 85.7% coverage the 173 residual split:
165 searched_no_source, 6 needs_manual_link (Boxford2021, EastBrookfield2022, Petersham2021,
Tolland2021, Warren2022, Windsor2021), 2 paywalled. CAVEAT: "searched_no_source" is WEAK evidence —
the finder workflow discarded found=false notes, so we know a town-year was searched but not what
was ruled out. FIXED: find_results.workflow.js now returns a `misses[]` array (municipality, year,
checked, source_page) alongside pairs. Re-running the tail with miss capture is what would let us
claim exhaustion.

**Paywalled publishers blocking MA municipal results (for a possible subscription):** 37 town-years
across 17 publishers, but only **3 would ADD a town-year** — 34 would merely UPGRADE an existing
stub render. Biggest: berkshireeagle.com 7, recorder.com 4, patch.com 4, patriotledger.com 3,
thesunchronicle.com 3, archives.thereminder.com 3, nantucketcurrent.com 3. Note Berkshire Eagle +
Greenfield Recorder + Athol Daily News + Gazette are all Newspapers of New England (one subscription
may cover several); Patriot Ledger/Telegram/Herald News/SouthCoast Today are Gannett. Subscription
value is mostly data QUALITY, not coverage.

**`parse_corpus --new` is FILE-based** (json presence in data/json/), NOT the `has_json` column (which
is stale at ~952). So `--new` correctly targets only newly-hosted docs (~67 last run, $1.28). Don't
trust `has_json`.
