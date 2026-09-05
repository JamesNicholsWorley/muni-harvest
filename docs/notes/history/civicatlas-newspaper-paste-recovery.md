---
name: civicatlas-newspaper-paste-recovery
description: CivicAtlasMA — recover gap town-years by pasting paywalled newspaper articles; saved candidate/paywalled caches
metadata: 
  node_type: memory
  type: project
  originSessionId: c41c2687-0b88-4d40-bb8e-183be766074d
---

Highest-yield gap-fill path once official docs are exhausted: the owner pastes the text of a
paywalled local-news election article and Claude parses+ingests it (works because recorder.com,
gazettenet.com, wwlp.com, berkshireeagle.com etc. bot-block automated fetch AND paywall). Owner has a
**Greenfield Recorder** subscription (Newspapers of New England → also Daily Hampshire Gazette
/gazettenet.com + Athol Daily News). Pipeline per paste: hand-write `data/staging_leadsN/markdown/{Town}{Year}.md`
→ `logs/_sweep_submit.py --dir staging_leadsN` (batch, ~$0.005/doc) → poll batch ended →
`logs/_sweep_collect.py --dir staging_leadsN` → `logs/_gap_multi_ingest.py --dir data/staging_leadsN --apply`
(NOTE the path convention differs: submit/collect take bare `staging_leadsN`; multi_ingest takes `data/staging_leadsN`).
Then record turnout in `data/turnout.csv` (`total_votes_cast`, source=news-text) and run coverage_report + _revert_wrongtown.

SAVED SEARCH CACHE (answers "did we save the CSE/Haiku candidate picks?" — YES):
`logs/haiku/cand_batch_*.csv` (Haiku picks from first page of results: municipality,year,url,evidence,text_snippet),
`logs/adjudication.csv`, `logs/candidate_verdicts.csv`, and curated `logs/paywalled_sources.csv`
(publisher,impact,municipality,year,url). Cross-ref caches vs no_source to find still-gap newspaper leads.

TWO MORE HIGH-YIELD ROUTES for dark small towns (proven 2026-08-07):
1. **Email the town clerk.** Highest yield for towns that publish nothing online. Russell went 0/6 → 6/6
   (2021-2026) from one clerk reply (a scanned multi-year PDF). When a clerk sends a multi-year scan:
   split into one PDF per page, vision-parse each, then REMAP by the parsed date — pages may be
   REVERSE-chronological and some may be undated (assign by elimination). `logs/_remap_russell.py` +
   `logs/_dump_russell.py` are the template. Cross-check the newest page against any doc you already have.
   Turnout = max over single-winner races of (candidate votes + blanks); `logs/_russell_turnout.py`.
2. **CivicPlus DocumentCenter ID sweep** (Douglas/Tyringham/Russell/Tolland etc.): `curl -s -D - -o NUL`
   on `{base}/DocumentCenter/View/{id}` returns a 301 whose Location slug IS the doc title — read titles
   for a whole ID range cheaply (no downloads), filter for result|warrant|ballot|report|election. Caveats:
   HEAD 404s (GET only); many tiny towns only host results for a few years (Tyringham DC had 2018-21+2026
   only); generic overwritten files (Russell `View/519/Election-Results.pdf`) carry NO date — pin the year
   via the PDF's filename-embedded timestamp / Acrobat creation date. Bigger towns (Douglas) post recent
   results as JS CivicAlerts, not DocumentCenter, so the sweep misses them.

Gotchas: winner-only news → votes=-1 (correct for uncontested); ballot-question results NOT needed
(MA DLS tracks Prop 2½ overrides separately). A prose-heavy article with one contested race + a terse
uncontested list can undercapture — Haiku dropped Topsfield2022's 7 uncontested offices (kept only the
contested one); fix by hand-writing the JSON. Reconstructing integer votes from rounded percentages is
underdetermined — refuse, record winner-only instead. Both Leverett AND Gosnold elect officers at Town
Meeting (news "Leverett is the last" is wrong), so those need ATM minutes not a ballot results sheet.
See [[civicatlas-gapsweep-pending]], [[civicatlas-google-custom-search]], [[civicatlas-detally-toolkit]].
