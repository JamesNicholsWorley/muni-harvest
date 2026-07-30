# muni-harvest — Recovery & Next-Agent Handoff

*Whole-project orientation for the next agent. Covers the corpus as it stands now, the
recovery tooling added on top of the original build, the election work as a reusable
**template**, and concrete starting points for the other document classes (minutes,
agendas, budgets, bylaws, warrants). Last updated 2026-07-30.*

*Read alongside: `HANDOFF.md` (original build & infra record), `SCOPE_INVESTIGATION.md`
(coverage audit, Rounds 1–3), `ELECTION_GAP_NOTE.md` (election recovery accounting).*

---

## 0. TL;DR

- **Corpus: 3,271,525 distinct nodes** (`data/discover/nodes.jsonl`, gitignored, ~1GB),
  consolidated + deduped by urlkey + municipality-backfilled. Index-only (URLs, no bytes).
- **Four recovery sources** now sit on top of Wayback, each with a CLI command + a sharded
  GitHub-Actions workflow: **docsweep**, **dc-idsweep**, **minutes-recover**, + a cert-fixed
  **browser tier**. All committed; direct-push-to-main.
- **Elections were the worked example.** Recall 40%→58% (documentID-aware); of ~409
  still-missing town-years, a content-dive **located 240 inside documents we already hold**
  (annual reports/minutes/HTML pages) — gap 409→144. The *methodology* is a template for any
  doctype.
- **The other classes are wide open**: 691K agendas, 360K minutes, 32K budgets, 44K bylaws,
  16K warrants are indexed but never systematically audited/recovered. Reusable analysis
  scripts and the content-dive harness are in `scratch/`.

---

## 1. Corpus: what's in it, where, how it's organized

- **`data/discover/nodes.jsonl`** — the single consolidated manifest. One JSON object/line:
  ```
  seed_host, municipality, url, urlkey, kind ("page"|"file"), mimetype, doctype,
  anchor, depth, parent_url, breadcrumb, discovered_via, storage_host
  ```
  Backups from this session: `nodes.pre_consolidate.jsonl`, `nodes.pre_backfill.jsonl`.
- **`discovered_via`** tells you the source: `wayback` (historical PDFs), `crawl` (BFS live
  crawl, incl. browser tier), `docsweep` (sitemap sweep), `dc_idsweep` (de-linked
  DocumentCenter), `minutes_recover`, `agendacenter_live`, `documentcenter`, `sitemap`.
- **`urlkey`** = canonical dedup key: host www-stripped, **path lowercased**, query kept
  (case-sensitive). Match docs across sources on this. For CivicPlus, also match by
  **(host, documentID)** — the slug-less `/View/{id}` and the slugged verified URL are the
  same doc (see gotcha §5).
- **Doctype distribution (current):** agenda 691,093 · minutes 360,521 · notice 57,436 ·
  bylaw 44,658 · report 40,235 · budget 31,892 · packet 21,094 · decision 20,131 ·
  warrant 16,479 · election_results 13,497. Doctype is a **wide-net URL classifier**
  (`discover/docclass.py`) — recall-biased, verify by content before trusting.
- **Board coverage (of 351 towns)** — see `data/discover/coverage.md`. Highlights:
  Select Board 244 ag / 226 min / 210 both; Planning 275/252/243; ZBA 232/192/173;
  Finance 255/207/199; School Committee 188/**67**/63. Agenda↔minutes linked meetings:
  94,067 (AgendaCenter meeting-id) + 11,522 (freeform board+date).

## 2. Recovery tooling added this session (CLI + Actions)

| Command | What it does | Workflow |
|---|---|---|
| `docsweep` | Sitemap → fetch every content page → extract every linked document (CMS-agnostic; DocumentCenter, off-host CDN, HTML). The main whole-site recovery. | `docsweep-shard.yml` |
| `dc-idsweep` | Probe the CivicPlus `/DocumentCenter/View/{id}` id-space for **de-linked** archives no page links + Wayback never snapshotted. Density-gated + per-host cap. | `dc-idsweep-shard.yml` |
| `minutes-recover` | For each agenda-only AgendaCenter meeting, GET the deterministic Minutes URL (same date+id). ~21–35% resolve. | `minutes-recover-shard.yml` |
| `export-manifests` | Extract compact `config/dc_known_ids.jsonl.gz` + `config/agenda_only.jsonl.gz` so the two sweeps run on Actions **without** the 1GB corpus. Regenerate after every merge. | — |

Run a sharded job: `gh workflow run docsweep-shard.yml -f shards=20` (gh at
`C:\Program Files\GitHub CLI\gh.exe`), then `gh run download <id> -n <artifact>`, merge into
`nodes.jsonl` deduped by urlkey (see `scratch/consolidate.py`), re-run `coverage`/`groundtruth`.
Browser-tier hosts must run **locally** (`discover --hosts-file …`); runners have no browser.

## 3. Key code fixes this session (`src/muni_harvest/discover/model.py` unless noted)

- **`urlkey`** lowercases the path (CivicPlus emits both `/DocumentCenter/View/` and
  `/documentcenter/view/`).
- **`is_file_url`/`is_doc_endpoint`** recognize extension-less CMS doc routes
  (`/DocumentCenter/View/{id}`, `/ImageRepository/Document?documentID=`, `GetFile.ashx`).
- **Storage allowlist** += finalsite.net, storage.googleapis.com, **sanity.io**,
  **aptuitivcdn.com**, **documents-on-demand.com** (muni docs were dropped as off-host).
- **`serving_host`** — probes bare-vs-`www` and picks the one that answers (many towns refuse
  one variant; `norm_host` stripped www so the crawler hit the dead one). Wired into docsweep
  + crawl. Fixed Norwood 0→1,798 files.
- **Browser tier** (`fetchers/waf_session.py`): `acceptInsecureCerts` (muni sites with bad
  TLS were landing on Chrome's "Privacy error" → 0 pages).
- **docsweep hardening**: skip storage-host seeds; per-host wall-clock budget; 340-min job cap.

## 4. The election recovery = a reusable TEMPLATE for any doctype

The exact pipeline used for elections generalizes to minutes / agendas / budgets:

1. **Define the expected set.** Elections used CivicAtlas `master_urls.csv` (expected town-
   years). For other classes: derive expectations from `municipalstructure` (which board each
   town has), the meeting cadence, or the fiscal calendar (every town files a budget + ACFR).
2. **Measure corpus coverage.** URL-match on `urlkey`, then (host, documentID) for CivicPlus.
   Scripts: `still_missing_full.py`, `remeasure.py`, `verify_recovery.py` — parameterize the
   doctype filter.
3. **Recover misses at the source.** docsweep (currently-linked) → dc-idsweep (de-linked) →
   minutes-recover (AgendaCenter) → browser tier (WAF towns). Host-list audit vs the
   authoritative `CivicAtlasMA/data/inventory/sources/towns_websites.csv`
   (`scratch/host_audit2.py`) + allowlist adds catch structural gaps.
4. **Find content inside containers.** Where a labelled doc doesn't exist, the content lives
   in a broader document (annual report, minutes, packet). **The content-dive harness**
   (`scratch/dive_candidates.py` → `dive_fetch.py`/`dive_fetch2.py`/`dive_deep.py`) fetches
   candidates, extracts text with `fitz`/HTML-strip, and confirms by **content signals**.
   For elections: election heading + `Blanks`-per-race + office names + vote tallies. Swap
   the signal regex for the target class (see §6).
5. **Hand off, don't over-classify.** URL/anchor classification is noisy both ways (HANDOFF
   gotcha #7). Emit candidate + evidence; let content-verification (CivicAtlas `process_pdf.py`)
   make the final call. Election deliverable pattern: `scratch/dive_confirmed.csv`
   (town-year → document_url + evidence).

## 5. Gotchas discovered this session (add to the canon)

1. **CivicPlus IIS returns 404 to HEAD but 200 to GET** for the same valid document —
   dc-idsweep must GET (Range: bytes=0-0).
2. **Bare vs www**: many MA town domains refuse one variant; use `serving_host`.
3. **documentID-aware matching**: `/DocumentCenter/View/51303` (slug-less, from dc-idsweep) and
   `/View/51303/OFFICIAL-RESULTS` (verified) are the SAME doc — match by id, not string, or
   recall looks ~18pts lower than it is.
4. **ACFR ≠ Annual Town Report.** The ACFR/Comprehensive Financial Report is finance-only and
   has **no** election/meeting content. The narrative *Annual Town Report* is the goldmine
   (contains the elections section + often board summaries). Exclude ACFRs when hunting.
5. **Sitemap-less small towns** need the browser/deep-crawl path — docsweep depends on
   `/sitemap.xml`. Sanity.io / Aptuitiv / Google-Sites / ProudCity small-town CMSs vary.
6. **"results"/"minutes"/"budget" are polysemous** in URLs (water-quality results, bid results,
   meeting minutes vs. minute-of-angle, budget vs. budget-workshop). Content-verify.
7. **AgendaCenter unknown-board gap**: 261,971 agenda/minutes docs have no board attribution
   (board lives in the empty anchor). `recover-boards` only grabbed the *current* live view;
   **historical board recovery** (archived-listing snapshots) is the big open lever for minutes.

## 6. Concrete starting points for the OTHER document classes

**Minutes (360K indexed).** Biggest structured opportunity.
- Meeting-level completion is ~36–47% (agenda-heavy is real behavior + Wayback per-URL gaps).
- **Historical board attribution** is the lever: 261,971 AgendaCenter docs are unknown-board.
  `recover-boards` fetched only the current `/AgendaCenter` view; fetch **year-param archived
  listings** (or Wayback snapshots of the listing) to attribute the rest → unlocks per-board
  minutes coverage. Start from `discover/agendacenter_recover.py` + `scratch/live_ac_truth.py`.
- Content-dive template: minutes signal = "MINUTES", "called to order", "moved/seconded",
  "adjourned", a date + board name. Reuse `dive_*` with that signal set.

**Agendas (691K).** Most complete class; use as the denominator. Per-board agenda coverage
via `scratch/board_stats.py` / `body_coverage.py`. Gap analysis = which (board, date) meetings
have an agenda but the town clearly met (cross-ref minutes / broadcast).

**Budgets & ACFRs (32K).** Never audited. Every town files an **annual budget** + an **ACFR**
each fiscal year → a clean expected grid (351 towns × years), same shape as elections. Signal:
"GENERAL FUND", "APPROPRIATION", "ACFR", "Statement of Net Position", fund tables. Many are
inside the Annual Town Report too (content-dive).

**Bylaws / zoning (44K) & Warrants (16K).** Bylaws are near-static (one current set/town) —
coverage = does each town's current zoning bylaw + general bylaws exist. Warrants pair with
town-meeting minutes (warrant → results). Warrant signal: "ARTICLE 1", "MOVED", "TOWN MEETING
WARRANT".

## 7. Reusable scripts (`scratch/`) — the toolbox

- **Coverage/accounting:** `body_coverage.py`, `board_stats.py`, `board_gap_breakdown.py`,
  `meeting_level.py`, `still_missing_full.py`, `remeasure.py`, `genuine_results.py`,
  `verify_recovery.py`, `measure_recovery.py`.
- **Content-dive harness (the reusable finder):** `dive_candidates.py` → `dive_fetch.py` →
  `dive_fetch2.py` (URL-encode + WAF cookie-lift) → `dive_deep.py` (broader candidates).
  Swap the signal regex to target minutes/budgets/etc.
- **Host/CDN hygiene:** `host_audit2.py` (vs authoritative towns_websites.csv),
  `resolve_domains.py`, `consolidate.py`, `backfill_muni.py`.
- **CivicPlus reverse-engineering (reference):** `dc_explore.py`, `dc_bundle.py`,
  `dc_folder_docs.py`, `dc_index_probe.py` (documented the auth-walled folder API).
- **Artifacts (CSV outputs):** `dive_confirmed.csv` (240 election town-years → doc + evidence),
  `still_missing_final.csv`, `recovered_missing_docs.csv`, `recovered_candidates_tagged.csv`.

## 8. Operations recap

- `gh` / `hcloud` NOT on PATH — full path `C:\Program Files\GitHub CLI\gh.exe`.
- Direct-push-to-main (public repo, no PR rule). Commit trailer:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Corpus + backups are gitignored (`data/`); manifests + host lists + notes ARE committed.
- Python: project `.venv` (`.venv/Scripts/python.exe`), `fitz`/pymupdf available for PDF text.
- Windows/bash gotchas: quote paths; `git-bash` mangles `/leading` args (`MSYS_NO_PATHCONV=1`);
  don't pipe long background jobs through `tail` (buffers until exit — read the raw output file).

## 9. Confidence & what's solid

**Solid:** the 4-source recovery stack (reproducible, Actions-sharded); documentID-aware
election recall 58%; the content-dive located 240/409 missing election town-years inside held
docs with page-level evidence; host-audit + serving_host + CDN allowlist fixes. **Open levers
(highest value first):** historical AgendaCenter board attribution (unlocks per-board minutes),
budget/ACFR coverage grid, warrant↔town-meeting pairing, the ~144 residual election town-years
(smallest towns / un-published / 2025 recency). The scraper is a **finder** — classification &
extraction are CivicAtlas's `process_pdf.py`.
