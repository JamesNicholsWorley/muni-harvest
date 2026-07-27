# Scope investigation — board coverage, missing minutes, election capture

*2026-07-27. Evidence-based audit of the harvested corpus (nodes.jsonl, 2.23M nodes)
against ground truth: the `municipalstructure` SQL table (351 MA municipalities) and the
verified election collection in CivicAtlasMA. Scripts in `scratch/`.*

---

## 1. Select Board / City Council scope (vs municipalstructure)

`municipalstructure`: **292 Select Board towns, 59 City Council** (351 total).

Coverage of each town's **own governing body** (Select-Board docs for SB towns, City-Council
docs for CC towns), after filling AgendaCenter boards from the recovered meeting→board map:

| Governing body | towns | in corpus | own-body agendas | own-body minutes | own-body BOTH |
|---|--:|--:|--:|--:|--:|
| Select Board | 292 | 282 (97%) | 238 (81%) | 220 (75%) | 205 (70%) |
| City Council | 59 | 56 (95%) | 43 (73%) | 42 (71%) | 38 (64%) |

**The own-body numbers understate reality.** Counting agendas/minutes of *any* board:
270/292 SB towns have agendas and **273 have minutes** in the corpus. The drop from 273→220
"Select-Board minutes" is not missing documents — it is **board attribution**: AgendaCenter
(the dominant CivicPlus CMS) puts the board name only in the link text, which Wayback did not
capture, and our live board-recovery only covers the *current* AgendaCenter view. So the docs
are captured; we just can't always label them Select-Board vs some other board.

**True town-level gaps (small, actionable):**
- **10 SB towns absent from corpus entirely:** Goshen, Gosnold, Harwich, Monroe, North Andover,
  Norwood, Pelham, Petersham, Southampton, West Brookfield.
- **3 CC towns absent:** Pittsfield, West Springfield, Weymouth.
- **12 SB towns in corpus but zero agendas** (Arlington, Barre, Bellingham, Dalton, Hancock,
  Hardwick, Huntington, Mount Washington, Orange, Savoy, West Bridgewater, Windsor) — mostly
  tiny hilltowns + browser-tier towns (Arlington is the known 0→browser case).

→ These ~25 towns are the concrete "go get it" list, not a systemic scope failure.

## 2. Why so many agendas are missing minutes

Two distinct levels — the headline "38% completion" is a **meeting-level** number, and the
town-level story is very different.

**Town level: minutes are almost never truly absent.** Of 33 SB towns with a Select-Board
agenda but no Select-Board *minutes*, only **2 towns** (Florida, Wendell) have zero minutes of
*any* board in the corpus. The rest have minutes — just unattributed (see §1).

**Meeting level (AgendaCenter meeting-id join, 194,016 meetings across 190 towns):**
- both agenda+minutes: 69,795 (36.0%)
- **agenda only: 121,709 (62.7%)**
- minutes only: 2,512 (1.3%)

**Decisive live test.** For agenda-only meetings, the Minutes file has a *deterministic* URL
(same date+id). I probed the **live** sites for old (2019–2023) agenda-only meetings, spread
across years (recent meetings excluded — their minutes legitimately aren't posted yet):

| Town | agenda-only minutes found LIVE | Town | found LIVE |
|---|--:|---|--:|
| Concord | 17/30 (57%) | Weston | 10/30 (33%) |
| Northampton | 10/30 (33%) | Carlisle | 11/30 (37%) |
| Wellesley | 10/30 (33%) | Lowell | 8/30 (27%) |
| Chelmsford | 5/30 (17%) | Brookline | 0/30 (0%) |

**Aggregate: ~71/240 = 30% of "agenda-only" meetings have minutes live on the same site that
we missed.** The other ~70% genuinely 404 — minutes were never posted.

**Conclusion.** The gap is *both* real behavior *and* a fixable harvest miss:
1. **Majority is real.** MA open-meeting law forces a 48h agenda posting for every meeting;
   minutes are approved/posted slowly and selectively. Agenda-heavy listings are normal.
2. **~30% is a Wayback per-URL capture gap.** Wayback snapshotted the Agenda ViewFile but not
   the Minutes ViewFile of the same meeting; our AgendaCenter recover only read the current view.
   Because the Minutes URL is deterministic (same date+id), these are **cheaply recoverable by a
   live GET per agenda-only meeting-id** — no Wayback, no browser. Recovering them would lift
   meeting-level completion from ~36% to roughly ~55%.

## 3. Election results — verified CivicAtlas URLs vs the deep scrape

Cross-referenced **1,436 verified election docs** (CivicAtlasMA `master_urls.csv`, LEO/ATR
provenance, expected=yes, real URL) against the corpus by canonical urlkey (+ host + CivicPlus
documentID form):

| Capture status | count | % |
|---|--:|--:|
| captured (exact URL) | 545 | 38.0% |
| captured (DocumentCenter ID form) | 32 | 2.2% |
| **MISS — host crawled, doc not captured** | **825** | **57.5%** |
| MISS — host absent entirely | 34 | 2.4% |

**Only ~40% of verified LEO election docs are in the corpus, despite crawling ~98% of their
hosts.** The URL method the project relied on is confirmed inadequate. Why the 859 misses:

- **38% are `/DocumentCenter/View/{id}` URLs.** We harvest DocumentCenter as
  `/ImageRepository/Document?documentID=` — but only 11% of these election docs actually matched
  by ID (our enumerator didn't reach those cities'/folders' docs). Not just a URL-form artifact.
- **~40% are HTML result pages / dynamic endpoints** (`.php`, `.aspx`, `.ashx?key=`, `/elections/`
  landing pages). Our Wayback pass filtered `mimetype:application/pdf`, so it **structurally
  cannot** capture an HTML results page; the file-only classifier drops them too.
- **~22% are direct PDFs** on deep `/elections/`, `/city_clerk/` paths (beyond the 150-page /
  depth-4 crawl cap) or on non-allowlisted CDNs (finalsite.net, storage.googleapis.com).

**But the collection already largely exists.** CivicAtlasMA already **downloaded the PDF for
933/1,436 (65%)** of all verified docs. Of the 859 muni-harvest misses: **513 (60%) CivicAtlas
already holds as PDF**, and **298 were deliberately `discarded_not_results`** (specimen ballots,
notices — correctly excluded). Only ~19 are genuinely pending (oversized/exhausted).

A liveness probe of 30 random misses: **20/30 (67%) still fetch directly** now (16 PDF + 4 HTML);
7 are 404 (rotted news/landing URLs), 2 are 403 (WAF).

**Conclusion.** Don't try to rediscover election results by crawling — it plateaus at ~40%.
Treat **CivicAtlasMA `master_urls.csv` as the authoritative election seed**: it is town-verified,
65% already downloaded, and the rest are mostly live and directly fetchable by URL.

---

## Recommended next steps (ordered)

1. **Ingest CivicAtlas's verified election set** into muni-harvest as ground truth rather than
   rediscovering it. Artifact ready: `scratch/election_seed_verified.csv` (1,436 rows tagged
   captured/missed + native + hosted URL). ~40% already in corpus; ~500 need only a direct fetch.
2. **Recover missed AgendaCenter minutes cheaply:** for every agenda-only meeting-id, GET the
   deterministic Minutes URL live (sharded across Actions IPs). Expect ~30% hit → ~+36K linked
   meetings, completion ~36%→~55%.
3. **Fix the election capture path** for future harvests: (a) capture HTML/dynamic result pages
   under `/election(s)/` (drop the PDF-only filter for those paths); (b) add finalsite.net +
   storage.googleapis.com to the storage allowlist; (c) raise crawl depth/page-cap on clerk/
   election subtrees.
4. **Chase the ~25 truly-absent towns** (§1 lists) — small manual/browser-tier pass.

*Scripts: `scratch/body_coverage.py`, `meeting_level.py`, `probe_missing_minutes.py`,
`election_xref.py`, `build_election_seed.py`, `probe_election_misses.py`,
`verify_dc_undercount.py`. Outputs: `body_coverage_detail.csv`, `election_seed_verified.csv`,
`election_leo_misses.csv`.*

---

# ROUND 2 — content-level verification (supersedes the softer Round-1 claims)

*Prompted by justified skepticism: don't trust a constructed-URL 404; look at what towns
actually publish. Scripts: `live_ac_truth.py`, `live_vs_corpus.py`, `paired_probe.py`,
`election_host_depth.py`, `dc_gap.py`, `requantify.py`.*

## R2.1 Minutes — the gap is BIGGER than Round 1 said, and partly a real miss

- **Live AgendaCenter ground truth (Concord):** the live site lists 906 meetings, **62% with
  BOTH agenda and minutes**; the agenda-only remainder is dominated by *future* 2026 meetings.
  Our corpus links only ~36%. The town publishes far more minutes than we linked.
- **Recent capture is perfect:** 100% of Concord's currently-live minutes URLs are in our corpus.
  The deficit is entirely *historical* meetings (Wayback-era).
- **Paired live probe (agenda AND minutes at the same meeting-id, old 2019–21 meetings,
  4 towns, 72 meetings):**
  - **~35% — BOTH agenda and minutes are live, we captured only the agenda** → real, recoverable
    miss (Wayback snapshotted the agenda ViewFile but not the minutes ViewFile of the same meeting).
  - **~64% — agenda is live (200) but minutes 404 at the same id** → minutes genuinely never
    uploaded to the town's system for that meeting. Confirmed at the file level, not assumed.
  - ~1% both gone (meeting aged out — inconclusive).
- **Verdict:** ~35% of "agenda-only" meetings have minutes we can still fetch — a real bug worth
  fixing, not archaeology. The other ~64% are agenda-posted-minutes-never-posted (common MA board
  behavior; a YouTube/South-Shore-News recording would prove the *meeting* happened but not that
  written minutes were ever posted online). Recovery is deterministic: GET the Minutes ViewFile at
  each agenda-only id — same URL shape, no browser, no Wayback.

## R2.2 Elections — the misses are concrete, fixable CAPTURE BUGS, not absence

The skeptical read was right: "we should have collected these URLs." Decomposing the 859 misses:

- **DocumentCenter folder-traversal bug (272 misses; 91% diagnosed):** for these, the enumerator
  ran on the host and captured document IDs BELOW and ABOVE the wanted one (Lawrence wants id
  51303, we have up to 51648; Framingham wants 44049, we have up to 55027). **The document exists
  inside the ID range we harvested — our tree walk skipped its folder** (the Elections folder's
  leaves are only exposed via the auth-walled `GetDocumentsForAFolder`, which the enumerator
  skips). Fixable: traverse those folders (or ID-sweep the known contiguous range).
- **Shallow / zero crawl (33% of ALL misses on hosts with <100 pages crawled):**
  `springfield-ma.gov` = **1 page**, `wilmingtonma.gov` = 1, `newburyport` = 1, `newtonma.gov`/
  `quincyma.gov` = 60. We leaned on Wayback's PDF-only index and **never walked their
  `/elections/` sections**, so we never discovered the linked result PDFs. Springfield=1-page is a
  block/redirect — exactly a browser-tier + Actions-IP case.
- **Off-host CDN files (googleapis, finalsite, revize, drive.google):** linked from pages we
  didn't crawl, or on hosts not in the storage allowlist (finalsite). Fixable via allowlist + crawl.
- **HTML result pages:** the Wayback pass filtered `mimetype:application/pdf`, so it *structurally
  cannot* capture an HTML results page. Fixable by keeping crawled pages under `/election(s)/`.
- **Recency:** a small handful (≈8) are docs published after our July-2025 harvest.

**Case bug found:** `urlkey()` lowercases the host but not the path, so `/DocumentCenter/View/`
≠ `/documentcenter/view/`. Minor here, but fix it (lowercase the path for CivicPlus) to avoid
false dedup misses.

## R2.3 Corrected bottom line

Nothing here supports "the documents don't exist." Every major gap is a harvest defect with a
free fix (Wayback per-URL gaps, an incomplete DocumentCenter folder walk, hosts crawled 1 page,
a PDF-only filter, a missing CDN allowlist entry, a path-case bug) — all runnable on the existing
GitHub-Actions shards + browser tier. The one genuinely-real component is ~64% of agenda-only
*meetings* whose minutes were never posted online at all.

---

# ROUND 3 — fixes implemented + manual minutes investigation

*Acting on the goal. Code in `src/`, verification in `scratch/`.*

## R3.1 Root causes confirmed by live reverse-engineering
- **DocumentCenter CANNOT be fully enumerated via the API** — `GetDocumentsForAFolder`
  (per-folder document list) is **auth-walled** (Sign-In page). The public `_AjaxLoadingReact`
  tree returns only a small old subtree (Lawrence: 55 folders, ids 27..3086) while the site has
  ids to 52,000+. The "traversal bug" is unfixable at the API layer.
- **But every document is public and LINKED from content pages.** Lawrence's election PDF
  `/DocumentCenter/View/51303` returns 200 pdf and is linked from `/772/Election-Results`,
  listed in `/sitemap.xml`. Same for Framingham 44049 (`/3095/Election-Results`). We missed them
  because (a) the crawl never reached those pages and (b) `is_file_url()` treated extension-less
  `/DocumentCenter/View/{id}` as a *page*, not a document.

## R3.2 Fixes implemented
1. **`urlkey()` path-case** (`model.py`) — path lowercased (query preserved). Unit-tested.
2. **`is_file_url()` recognizes extension-less doc endpoints** (`is_doc_endpoint`):
   DocumentCenter/View, ImageRepository documentID, GetFile.ashx, civicax/filebank, `?bidId=`.
3. **Storage allowlist +finalsite.net +storage.googleapis.com** — off-host election PDFs captured.
4. **`docsweep` — sitemap-seeded whole-site document sweep** (`discover/docsweep.py`, CLI
   `docsweep`, `docsweep-shard.yml`): per host fetch `/sitemap.xml` -> fetch every content page ->
   extract every linked document. CMS-agnostic, no auth, bounded by the sitemap (no page-cap
   truncation), browser-tier for blocked hosts, resumable + shardable. The real recovery path.
5. **`minutes-recover` — deterministic AgendaCenter minutes** (`discover/minutes_recover.py`, CLI
   `minutes-recover`, `minutes-recover-shard.yml`): GET the Minutes ViewFile at each agenda-only
   date+id; ~35% resolve.

## R3.3 Manual minutes investigation — the gap is NOT the Select Board
Per-board breakdown from Concord's LIVE AgendaCenter (2020–24 settled meetings):
- **Select Board: 35 agendas / 28 minutes / 0 agenda-only.** Statutory boards post minutes
  reliably (Capital Planning 10/10, White Pond Advisory 12/12, Personnel Study 16/18…).
- The 43% town-wide agenda-only gap is concentrated in **ad-hoc / advisory / regional bodies**:
  CASE Collaborative (21), Director of Planning (11), Regional Emergency Communications (8), task forces.
- **Reading the agendas:** CASE agenda-only meetings are **executive sessions for collective
  bargaining** (M.G.L. c.30A §21(a)(2)); executive-session minutes are **sealed by law** (§22)
  until confidentiality lapses — legitimately unpublished. CASE is also a **separate regional
  collaborative** (10-superintendent board, own site casecollaborative.org) hosted courtesy on
  member towns; its records live with the collaborative (some CASE minutes do exist on Concord).
- **Takeaway:** for the boards that matter, minutes are largely complete. The agenda-only tail is
  real institutional behavior (sealed executive sessions; regional/advisory bodies) plus the ~35%
  deterministic Wayback-miss that `minutes-recover` reclaims.

## R3.4 Measured verification (docsweep on 4 real towns; verified URLs as yardstick only)
Ran `docsweep` on dighton-ma.gov, rockportma.gov, townofblackstone.org, littletonma.org
(243–400 pages each, 5,562 docs, +4,563 new distinct urlkeys), then measured election-doc
recall against the CivicAtlas verified URLs **without ingesting them**:

- **Recall 12% → 82%** (2/17 → 14/17). 12 newly recovered.
- Newly recovered include the exact DocumentCenter/View PDFs the auth-walled API missed
  (Blackstone 584/610/1352/2451, Dighton 1864/2390/3611, Littleton 1790/9564, Rockport 2626)
  AND HTML election pages (Dighton `/385/Election-Information-Center-Results`).
- The 3 still-missed are **old de-linked archives** (Blackstone id 242, Rockport 454/4419) —
  superseded and removed from the live pages, so no public crawl reaches them. That is exactly
  what Wayback covers (it snapshotted them while linked). One town (Rockport) also hit the test
  400-page cap; production uses 6000.

**Recovery sources are complementary:** `docsweep` = everything currently linked on the site
(the fix for the election/DocumentCenter gap), `wayback` = de-linked historical docs,
`minutes-recover` = deterministic AgendaCenter minutes. Verified URLs stay a yardstick, not a seed.

## R3.5 How to run at scale (free, on the existing infra)
- `gh workflow run docsweep-shard.yml -f shards=20` → merge `nodes_docsweep.jsonl`, dedup into
  `nodes.jsonl` by urlkey, re-run `coverage`/`groundtruth`.
- `gh workflow run minutes-recover-shard.yml -f shards=20` (needs `nodes.jsonl` present) → merge
  `nodes_minutes.jsonl`.
- Blocked hosts (springfield=1 page) resolve via the browser tier automatically (docsweep reads
  the tier cache and leases a warm driver for T1/T2).

## R3.6 Handling ALL cases — de-linked archives via id-sweep
The 3 residual misses (Rockport 454/4419, Blackstone 242) were **de-linked archives**:
`/DocumentCenter/View/{id}` returns 200/application-pdf, but no live page links them and
Wayback never snapshotted them, so docsweep and Wayback both miss them. Added a third,
deterministic recovery source:

- **`dc-idsweep`** (`discover/dc_idsweep.py`, CLI `dc-idsweep`, `dc-idsweep-shard.yml`):
  gap-aware sweep of the per-site View id space. For each DocumentCenter host it takes the
  ids already in the corpus, walks the remaining gaps (and past the known max, to catch
  docs newer than our harvest), and probes each with a **range-limited GET** — because
  **CivicPlus IIS returns 404 to HEAD but 200 to GET** for the same valid document (found
  the hard way). Hits are emitted as file nodes with the title parsed from the redirect
  slug. Resumable, shardable, rate-limited; a hit id-ceiling is logged, never silently capped.
- **Proof:** a 30-id gap window on Blackstone recovered **18 de-linked documents** including
  the target `View/242` ("2023-Annual-Town-Election-Official-Results"), old campaign-finance
  reports, and town-meeting recommendation sheets — none linked anywhere on the live site.

**Complete recovery stack (run in this order, merge+dedup by urlkey into `nodes.jsonl`):**
1. `wayback` — historically-linked docs (incl. some de-linked, if snapshotted).
2. `docsweep` — everything currently linked on the site (CMS-agnostic; DocumentCenter,
   off-host CDN, HTML pages). The main election/DocumentCenter fix.
3. `dc-idsweep` — de-linked DocumentCenter archives neither of the above caught.
4. `minutes-recover` — deterministic AgendaCenter minutes for agenda-only meetings.

Together these cover every document a MA muni site exposes: currently-linked, historically-
linked, and de-linked-but-still-served. Verified URLs remain a yardstick, never a seed.
