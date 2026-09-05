---
name: civicatlas-detally-toolkit
description: CivicAtlasMA de-tally upgrade tools + scraper wins that recover REAL vote counts for winner-only contested races
metadata: 
  node_type: memory
  type: reference
  originSessionId: c41c2687-0b88-4d40-bb8e-183be766074d
---

CivicAtlasMA "de-tally" upgrade (built 2026-08-05). Recovers real NUMERIC vote counts for the
contested-but-untallied races that were `published` only as winner-only (`votes=-1`). See
[[civicatlas-gapfill-pipeline]], [[civicatlas-history-leads-scope]].

**Tools (in `CivicAtlasMA/logs/`):**
- `_detally.py` — tally-STRICT resolver: accepts only a doc with numeric per-candidate counts (≥8
  multi-digit numbers + office + tally signal); prefers "Official Results/Summary Vote/recap"
  anchors; REJECTS specimen/sample/absentee ballots by URL+anchor even when scanned (the trap that
  polluted Littleton); 2-hop follow; routes scanned image PDFs to Haiku vision. `--stage [Stem...]`
  → `data/staging_contested/`.
- `_detally_ingest.py` — sync-parses staged PDFs (Haiku vision) or staged markdown, upgrades a
  published record ONLY if new numeric-tally count > old (tally-count gate; `_upgrade_ingest`'s
  race-count gate can't see −1→number). Backs up master. `--apply`. Hand-staged markdown URLs go in
  its `STEM_URL`.

**Results (of the 7 races): 6 of 7 recovered, contested-untallied 7→3.** Weston 2024 Select Board ✅
(followed clerk page → linked Official Results PDF, 279/1043), West Springfield 2025 Mayor ✅
(theReminder tally 4,618/1,783, markdown), Adams 2026 Select Board ✅ (town-clerk scanned tally
sheets, Haiku vision, VERIFIED vs the doc's grand-total page: Rice 633/Hoyt 353), Agawam 2023 Mayor
✅ (MassLive citing town clerk: Johnson 3,221/Calabrese 2,713; the nepm/AP result was a JS
Datawrapper widget with no numbers in HTML — MassLive had the raw counts). STILL OPEN: **Littleton
2026 ×3** — numeric results NOT published online anywhere (exhaustive: DocumentCenter ID scan
11249–12010 + CivicPlus search — town skipped its usual "Post Election Results" upload for 2026;
newsletters, AgendaCenter, Wayback, Lowell Sun all negative). Winners known (Morrison/Bubp) but
counts only in clerk's office / town Facebook. Needs a human/records request — do NOT fabricate.

**Generalizable scraper wins (for the goal-2 gap sweep; port into `_resolve_auto`/`_gap_fetch2`):**
(1) always follow a winner-only landing PAGE → its linked numeric "Summary Vote" PDF; (2) govfiles
CMS towns post results at `www.{town}.ma.us/town-clerk/files/{m-d-yyyy}-unofficial-election-results`
— template-probe before searching; (3) reject specimen/sample ballots by URL even when scanned;
(4) scanned tally sheets parse via Haiku PDF-vision but VERIFY against the grand-total page;
(5) news-with-numbers markdown fallback when official is a JS widget.

**Owner rule (winner-only vs turnout):** genuinely-uncontested = winner-only is CORRECT, only
turnout (total ballots cast, from cert header/ATR) is missing — don't chase nonexistent tallies.
Contested-untallied = numbers exist → strict. Filling a `no_source` gap where the only doc is a
winner-only list = ACCEPT it (beats a gap) + queue turnout; so the gap resolver should be
tally-PREFERRED, not tally-required.
