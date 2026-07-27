# muni-harvest — Build & Findings Handoff

*Complete technical record of the MA municipal / civic-document harvester: what was built,
how each piece works, what we measured, and the gotchas. For the next agent to extend.*
*Last updated: 2026-07-27. Repo: https://github.com/JamesNicholsWorley/muni-harvest (public).*
*Supersedes the design-only `../HARVEST_SCALING_HANDOFF.md`.*

---

## 0. TL;DR

- **Corpus: ~2.21M unique document/page nodes** across 351 MA municipalities / 405 municipal hosts,
  harvested **free** (Wayback + GitHub Actions + local). **$0 of the $40 budget spent.**
- **Pipeline** (all resumable, index-only — no bytes downloaded yet):
  `probe → wayback (sharded) → discover (crawl+CMS enumerators) → coverage / groundtruth / verify`.
- **Two hard-won reverse-engineered backdoors** for JS CMS libraries a crawler can't see:
  CivicPlus **AgendaCenter** and **DocumentCenter** (React API).
- **The archive.org per-IP throttle** was the single biggest obstacle; **solved by sharding across
  GitHub Actions runner IPs** + block-aware retry.
- **Election ground-truth recall: 95.9% town-level / 70.9% document-level.** The residual is
  structural (2025 recency, minutes on school-district domains, genuinely-unpublished minutes),
  not findable-but-unfound.

---

## 1. Architecture & pipeline

Core reframe: **the browser is a scarce resource to ration; avoid the host entirely when a free
archive already has the content; size concurrency on two independent axes** (cheap tier =
politeness-bound; browser tier = machine-bound).

CLI (`muni-harvest <cmd>`, entrypoint `src/muni_harvest/cli.py`):

| Command | Does |
|---|---|
| `probe` | Tier-classify every host (T0/T1/T2/dns_fail/storage/blocked/needs_unblocker) → `tier_cache.jsonl` |
| `escalate [--redo]` | Run T0-blocked hosts through the T1/T2 browser tier to split browser-solvable vs needs-unblocker |
| `wayback [--shard I/N] [--hosts-file]` | Parallel Wayback CDX enumeration (deep historical docs) |
| `discover [--shard] [--max-pages]` | Union crawl+sitemaps+CMS+Wayback → nav-tree nodes |
| `recover-boards` | **AgendaCenter** full harvest (meeting→board + all agenda/minutes URLs) |
| `documentcenter [--shard]` | **DocumentCenter** React-API enumerator (`/ImageRepository` docs) |
| `coverage` | Board×doctype coverage + agenda↔minutes linkage (wide-net classifier) |
| `groundtruth` | Election recall vs the 942 known-collected PDFs (town+year) |
| `verify [--candidates --shard]` | Content-verify docs (open PDFs, check results signals) |
| `budget <seed\|summary\|spend\|alloc>` | $40 dynamic ledger |
| `store <ping\|ensure>` | S3-compatible object storage (R2/B2) |

Distributed on GitHub Actions (public repo = free/unlimited): `wayback-shard.yml`,
`verify-shard.yml`, `discover-shard.yml` (N-shard matrix + merge job → downloadable artifact).

---

## 2. Repo structure

```
src/muni_harvest/
  core/           stdlib-only politeness + JSONL I/O (vendored from AbundanceHistory common.py)
                  - RateLimiter (thread-safe), fetch() (gzip+backoff), cached_fetch, AuditLog, JSONL
  config.py       settings.toml loader + .env loader + host_overrides()/excluded_hosts()
  archive/
    wayback.py    CDX enumeration; _cdx_get() block-aware retry; shard_hosts(); load/valid_host/policy
    commoncrawl.py discovery-only CC index lookup (homepage/CMS fingerprint)
  resolve/        tier_cache.py (domain→tier JSONL) + resolver.py (cheapest-source-wins)
  probe/          tier_probe.py (T0 WAF/challenge detection → browser-required fraction)
  fetchers/
    waf_session.py  VENDORED WAF ladder (build_driver/mint_session/fetch_in_browser/fetch_bytes)
    browser_pool.py self-healing pool of warm stealth drivers (recycle on error/over-use)
    tiered.py       T0→T1→T2 escalate_blocked() (dns_fail/storage/invalid classification)
  discover/
    pipeline.py     orchestrator: union sources, tier-aware crawl, per-source deltas → nodes.jsonl
    crawl.py        polite BFS: AIMD delay, 429 circuit-breaker, browser-tier fetch, nav-tree
    htmllinks.py    stdlib HTML link+anchor+breadcrumb extraction
    model.py        urlkey, cross-domain doc policy (storage allowlist), same_site
    docclass.py     WIDE-NET (board, doctype, date, meeting_id) classifier
    sitemaps.py     sitemap index/gz/text parsing (seed, not truth)
    cms.py          CMS fingerprint → listing-endpoint seeds
    agendacenter_recover.py  AgendaCenter enumerator (board map + full agenda/minutes harvest)
    documentcenter.py        DocumentCenter React-API enumerator
    storage.py      resolve Drive/Dropbox/S3 download URLs (index-only)
    coverage.py     board coverage report + linkage
    groundtruth.py  election recall (town+year)
    verify.py       content verifier + candidate emission for distributed verify
  budget/ledger.py  append-only $40 ledger → one-way budget.md
  store.py          S3-compatible client (R2/B2)
config/
  settings.toml     worker counts, caps, rate limits
  muni_hosts.txt    committed canonical 405-host list (corrected + news-excluded)
  host_overrides.csv 8 verified dead-domain corrections
  exclude_hosts.txt  22 news/media hosts to drop
  verify_candidates.jsonl  1301 election-doc candidates for distributed verify
deploy/             cloud-init.yaml, setup_vm.sh, README (Hetzner + R2)
.github/workflows/  wayback-shard.yml, verify-shard.yml, discover-shard.yml, harvest.yml
data/               (gitignored) all harvest outputs
```

Data (multi-GB corpus) **never** goes in git — object storage (R2/B2).

---

## 3. Technical deep-dives

### 3.1 Wayback CDX + the archive.org throttle (THE key infra lesson)

- CDX endpoint: `https://web.archive.org/cdx/search/cdx?url={host}&matchType=host&filter=statuscode:200
  &filter=mimetype:application/pdf&collapse=urlkey&output=json&limit=2000&showResumeKey=true&fl=original,timestamp,mimetype`.
  Paginate via `resumeKey` (trailing blank/one-col row carries the token).
- **The throttle is per-IP CUMULATIVE volume, not instantaneous rate.** Running all 408 hosts from one
  IP at even ~1 req/sec triggered archive.org's abuse protection → **`WinError 10061 connection actively
  refused`** in bursts (346× in one run), cascading every in-flight host to error. A single local run got
  **287/408 hosts (30% loss)**.
- **Two fixes, both needed:**
  1. `_cdx_get()` in `wayback.py`: on block signatures (`refused/10061/429/timeout/reset`) back off **up
     to 180s with jitter** (not the 8s blip), so a runner survives a ban window.
  2. **Shard across GitHub Actions runner IPs** (`wayback-shard.yml`): 4–20 shards, each ~100 hosts, each
     IP does ~1/N of the volume. Result: **402/405 hosts, 3 errors, 1.87M docs, ~1h, free.**
- **GitHub runners are Azure IPs and archive.org served them fine** (we feared they'd be throttled harder —
  they weren't). This is the reusable pattern for all archive.org-heavy work.

### 3.2 Tier probe + browser tier (spend gate)

- `probe`: T0 = plain stdlib GET; blocked if 403/429/503, DNS/TLS error, or challenge-page regex
  (`just a moment|cf-chl|incapsula|captcha|...`).
- `escalate`: T0-blocked hosts → T1 (`mint_session` cookie-lift) → T2 (browser). **Critical gotchas found:**
  - Re-fetching the original URL in-browser is **cross-origin** after a bare→www redirect → status 0
    false-negative. Fix: inspect the **loaded `page_source`** (post-redirect/JS), not a re-fetch.
  - Challenge detection on a full rendered DOM false-matches `captcha`/`enable javascript` in form
    widgets. Fix: **size-first** — a >12KB DOM is the real site; interstitials are tiny.
  - `BrowserPool` must **recycle a driver that errored** (or a `WinError`-style crash cascades into a run
    of `WebDriverException`). Also DNS pre-check (`socket.gethostbyname`) short-circuits dead domains.
- **Result (436 hosts): T0 333 (76%), T1 2, T2 71, dns_fail 15, storage 4, invalid 3, blocked 6,
  needs_unblocker 2.** Of ~412 real municipal hosts: **80.8% free, 17.7% self-host browser, ZERO need a
  paid unblocker** (the 2 needs_unblocker are TV news sites). → **$8 unblocker reserve rebalanced away.**

### 3.3 Discover crawler

- Polite same-site BFS from homepage + sitemap/CMS seeds. Per-host **AIMD** delay; robots Disallow +
  Crawl-delay honored; **per-host 429 circuit-breaker** (bail after 5 consecutive 429s — one rate-limiting
  town, Barnstable, once stalled a run for **15.5h** before this fix).
- **Cross-domain policy:** PAGES stay same-registrable-domain; FILES captured off-host if on a storage
  allowlist (`s3/drive/dropbox/civicplus/revize/granicus/cloudfront/azure`). Drive/Dropbox URLs resolved to
  direct-download form.
- **Browser-tier crawl:** T1/T2 hosts (from tier_cache) crawl their live pages via the shared `BrowserPool`
  (`use_browser`), so browser-required towns (e.g. Arlington: 0→files) get live docs.
- **Nav-tree:** each node stores `parent_url, depth, anchor, breadcrumb` → reconstructs site hierarchy.
- **Anchors are empty for ~99% of nodes** (Wayback/sitemap have no link text) → classification must be
  URL/path/filename-based, not anchor-based.
- Caps (`settings.toml [discover]`): `max_pages` 150 (T0) / 60 (browser), `max_depth` 4, `max_consec_429` 5.
  The deep pass overrides these (`--max-pages 800 --max-depth 6`).

### 3.4 CMS enumerators (the JS-library backdoors)

**CMS distribution** (from `discover` fingerprint): CivicPlus **227**, WordPress 33, Revize 19,
unknown/blank 121, OpenGov 5, Granicus 3. Only the two CivicPlus JS apps need backdoors; the rest are
plain HTML links → deep-crawlable.

**AgendaCenter** (`agendacenter_recover.py`) — server-rendered, tractable:
- URL encodes doctype+date+meeting-id: `/AgendaCenter/ViewFile/(Agenda|Minutes)/_MMDDYYYY-{id}`.
  Agenda & minutes of the same meeting **share the id** → linkable without a board name.
- **Board** is only in the (empty-for-us) link text. Recover from the live page: category legend
  `<input name="chkCategoryID" value="{CID}"> {Board Name}` + `id="cat{CID}"` listing sections; walk
  ViewFile links assigning each to the current CID → board.
- One `/AgendaCenter` fetch returns **all retained years** (no pagination). Harvest emits every
  agenda/minutes URL as a node. **Result: 209 towns, 76K doc nodes, 31K meeting→board mappings.**

**DocumentCenter** (`documentcenter.py`) — React SPA, the hard one (fully reverse-engineered):
- Files are served as **`/ImageRepository/Document?documentID={id}`**, NOT `/DocumentCenter/View/` — so
  link-graph crawl AND Wayback both **completely miss them** (corpus had zero). This was a major blind spot.
- Backdoor (plain `requests`/urllib, **no browser needed**):
  1. `GET /DocumentCenter` → session cookies (`ASP.NET_SessionId`, `__RequestVerificationToken`).
  2. `GET /antiforgery` → `{"token": "..."}` (CSRF).
  3. `POST /admin/DocumentCenter/Home/_AjaxLoadingReact?type=1` with header
     `RequestVerificationToken: {token}` and JSON body `{"value":fid,"expandTree":false,"loadSource":7,
     "selectedFolder":fid}` → JSON `{"Data":[{"Text","Value","LoadOnDemand","ParentID"}...]}`.
  - `LoadOnDemand=true` → folder (recurse with its `Value` as fid). `LoadOnDemand=false` → **document**
    (`Value` = documentID; download URL = `/ImageRepository/Document?documentID={Value}`).
  - Folder path (e.g. `Agendas / Board of Appeals / 2015`) carried as the node `anchor` so the classifier
    derives board/doctype/date. (`GetDocumentsForAFolder` is auth-walled; not needed — leaf tree nodes ARE
    the documents.)
- **Result: 67,704 documents across 183 towns.** Reusable for any modern CivicPlus site.

**Revize / WordPress / freeform:** docs are plain `href`s in HTML (Revize path encodes department:
`Documents/{Dept}/*.pdf`) → the **deep crawl** handles them, no backdoor.

### 3.5 Deep live crawl (distributed)

- `discover-shard.yml`: on a runner there's no local Wayback/tier data, so discover runs **pure deep T0
  stdlib crawl** at `--max-pages 800 --max-depth 6`, 20 shards. Merge → `nodes_deep.jsonl`.
- **Result: 300K nodes, +110,653 NEW unique** (the rest dups of Wayback/CMS content). Catches the freeform
  docs the 150-page cap missed.

### 3.6 Classifiers

- **`docclass.py` (wide-net, recall-biased):** ordered board patterns (specific→generic; COA before
  city-council; `board[ _-]of[ _-]appeals` separator-tolerant), doctype patterns (agenda/minutes/warrant/
  election_results/budget/bylaw/…), multi-format date extraction, AgendaCenter authoritative parse.
  Bias to **recall** (over-tag; verify later) per the goal "avoid false negatives."
- **Content verifier (`verify.py`):** opens candidate PDFs (Wayback snapshots + live) with `fitz`, checks
  text for RESULTS signals vs ballots/warrants. **Distributed run (verify-shard, 20 IPs): 38.6% precision**
  — i.e. the URL "election" label over-counts (specimens/notices/applications). The content-`_RESULTS`
  regex is likely too STRICT (false negatives) and ~half of Wayback snapshot URLs 404 — both need work
  (see Open Issues).

### 3.7 Budget, storage, VM (built, mostly unused)

- **Ledger** (`budget/ledger.py`): append-only `budget.jsonl` → one-way `budget.md`. Rebalanced after the
  probe (unblocker $8→$2, +$4 llm, +$2 storage). **$40 allocated, $0 spent.**
- **Storage** (`store.py`): S3-compatible (Cloudflare R2 / Backblaze B2). `store ping/ensure`. Wired,
  awaiting the download stage.
- **VM** (`deploy/`): Hetzner CX22 Ashburn + `hcloud` + cloud-init + SSH key ready. **Deferred** — probe
  proved the full sweep runs free (local + Actions); provision only when the download/scheduling stage needs it.

---

## 4. Measured findings

- **Coverage** (of 351 towns, towns with BOTH agendas & minutes): Planning 235, Conservation 212, Select
  Board 206, Finance 194, ZBA 157, Board of Health 154, City/Town Council 114, Elections 98, School
  Committee 58. **80,631 agenda↔minutes meetings linked.**
- **Election recall vs 942 known PDFs: 95.9% town-level (281/293), 70.9% document-level (668/942).**
- **Agenda↔minutes completion ~38% at (board,date) granularity** — this is **real town behavior** (live
  authoritative listings run ~3–4× agenda-heavy; towns post agendas reliably, minutes sparsely). Joint +
  revised agendas are real but only ~5% (496 joint + 2,336 revised), NOT the cause of the gap.
- **PDFs ~90% born-digital** (free `fitz`/`pypdf` text); OCR need is a bounded minority (tesseract binary
  still not installed — install or use rapidocr before any OCR run).
- **Inventory data-quality:** `native_url` = "source of a past PDF," often a CMS/news/cloud host, not the
  town's site. 8 dead domains corrected (`host_overrides.csv`); 22 news hosts excluded; 7 more dns_fail
  towns need manual research; `.xlsx`-path rows are junk.

---

## 5. Gotchas & lessons (read before extending)

1. **archive.org throttles per-IP cumulative volume** → shard across IPs (Actions) + long block-aware
   backoff. Don't hammer from one IP.
2. **Datacenter IPs are worse for WAF-protected sites** (browser tier) but **fine for archive.org**. Keep
   the browser tier on residential IPs; Wayback/verify on Actions.
3. **Modern CivicPlus DocumentCenter uses `/ImageRepository/Document?documentID=`** — not `/View/`. Any
   pipeline keying on `/DocumentCenter/View/` misses everything.
4. **Anchors are empty for ~99% of nodes** — classify from URL/path, carry CMS folder paths as anchor.
5. **In-browser re-fetch of a redirected URL is cross-origin** (status 0) — read `page_source` instead.
6. **One rate-limiting host can stall a whole crawl** without a per-host circuit-breaker.
7. **A URL cannot tell you what a document IS** — the "election" label is ~39% precise by content;
   completeness metrics from URLs overstate presence and can't prove absence.
8. **`gh` and `hcloud` are NOT on PATH** in the Bash/`!` shells — invoke by full path
   (`C:\Program Files\GitHub CLI\gh.exe`, `%LOCALAPPDATA%\muni-harvest-tools\hcloud.exe`).
9. **argparse help strings**: a literal `%` throws — reword. **PowerShell**: no heredocs (use the Bash
   tool); `gh --json ... --jq` arg-parsing is finicky — grep the `--log` instead.

---

## 6. Operations

- **Auth:** `gh` authenticated (JamesNicholsWorley, scopes repo+workflow; `gh auth setup-git` done → plain
  `git push` works). Repo is public; direct-push to `main` (no PR-review rule).
- **Run a distributed job:** `gh workflow run wayback-shard.yml -f shards=4`; watch with
  `gh run watch <id>`; pull results with `gh run download <id> -n <artifact>`. Merge locally, dedup by
  urlkey, re-run `coverage`/`groundtruth`.
- **Full local re-measure:** `wayback` (or download sharded) → `discover` → `recover-boards` →
  `documentcenter` → `coverage`/`groundtruth`/`verify`.

---

## 7. Open issues / next steps (ordered)

1. **Content-verify at scale done right** — the `_RESULTS` classifier is too strict (false negatives) and
   ~half of Wayback snapshot candidates 404. Prefer live URLs, broaden results signals (precinct/ward vote
   tables, "blanks", candidate-vs-count), re-run `verify-shard`. Then trust the precision.
2. **Re-fingerprint the 121 unknown/blank-CMS towns** (homepage fetch failed or no match) to catch any
   remaining structured library.
3. **Gated fetch/download stage** — actually download the 2.21M docs to **R2** (adds `sha256` to the
   manifest for true content-dedup; `fitz` text extraction two-layer model). This is where the built
   **R2 + VM** infra finally gets used.
4. **School-committee minutes** live on separate school-district domains (intentionally out of scope now) —
   a "related domains" pass would recover them.
5. **Historical AgendaCenter board recovery** (~245K unknown-board) — the live listing only exposes retained
   years; archived-listing snapshots would attribute the rest.
6. **Granicus/Legistar + OpenGov** (8 towns) — Legistar has a public API; low priority.

## 8. Confidence

**Robust:** archive.org sharding win; the two CivicPlus backdoors (reproducible); 0 municipal sites need a
paid unblocker; ~38% minutes-completion is real behavior; corpus comprehensiveness (2.21M, reaches every
document class a MA muni site exposes). **Not certain:** exact content-verified election precision (needs
the tuned classifier + live-URL fetch); the ~29% doc-level recall residual is dominated by 2025 recency +
year-matching, not capture.
