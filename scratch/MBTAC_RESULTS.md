# MBTA Communities Act (40A §3A) zoning-vote finder — results & handoff

*Built 2026-07-30. Finds + fully extracts municipal votes on MBTA Communities Act compliant
zoning across the 175 designated MBTA-C towns, at both board (Planning/Select) and legislative
(Town Meeting / City Council) levels. Mirrors the elections `dive_*` content-dive template.*

## Pipeline (scratch/mbtac_*)

| Stage | Script | Output |
|---|---|---|
| 0 reference | `mbtac_towns.py` | `config/mbtac_towns.csv` — 175 towns × type × governing body × deadline tier |
| 1 candidates | `mbtac_candidates.py` | `mbtac_candidates.csv` — 20,352 minutes/warrant docs, 173/175 towns |
| 1b live sweep | `docsweep-shard.yml` (Actions) + `mbtac_livesweep.py` (browser tier) | `data/discover/nodes_mbtac_{actions,live}.jsonl` |
| 2 screen | `mbtac_screen.py` | `mbtac_screen.csv` — TOPIC∧VOTE∧BODY signal screen |
| 3 extract | `mbtac_extract_prep.py` → `mbtac_extract_workflow.js` | `mbtac_votes.jsonl` / `.csv` |
| 4 coverage | `mbtac_coverage.py` | `mbtac_audit.csv`, `mbtac_gap_*.txt` |

Extraction is done by an **agent workflow** (26 Sonnet agents over batched, snippet-cropped
docs — ~2M tokens total), not an API script. Snippets = ±3500-char windows around 3A-topic
anchors and topic-adjacent vote lines, ~12 docs/batch.

## Coverage (corpus + targeted live sweep)

- **Candidate docs:** 173/175 towns (only Somerville, Watertown lack candidates — WAF/JS cities).
- **Screen CONFIRMED (topic+vote+body co-occur):** 105/175 towns (60%); +8 PROBABLE-fallback.
- **Extracted vote events:** **69 events across 35 towns**; **22 towns with a terminal (binding)
  vote** — 21 adopted, plus rejections (Berkley, Dracut, North Reading, Winthrop). 15 numeric
  tallies (e.g. Dover 250-29 2/3-met; Cohasset Art 20 majority; Beverly City Council 2024-11-12).
  Also 22 board recommendation votes (Planning/Select) + 4 referrals.

## Why extract (35) < confirmed (105)

The screen's topic+vote+body co-occurrence surfaces many **warrants** (article text +
board recommendations, no final tally) and **informational materials** (zoning maps, info
forms, memos, slides) that discuss 3A but do not *record* the legislative vote. Extraction is
the honest filter: `has_3a_vote=false` for those. The towns that yielded binding votes did so
from (a) Town Meeting **results minutes**, or (b) MBTA **project pages that summarize the
outcome**. This is a candidate-*targeting* limit, not a cropping bug (widening snippets already
lifted 29→35 towns and recovered e.g. Berkley's full recommend→adopt chain).

## Highest-value next lever (to push past 35 towns)

Targeted **results-doc hunt**, per town lacking a binding vote:
1. Town Meeting **results/minutes** for the 3A article date (doctype=minutes, board=town_meeting)
   — search corpus + live for "Article N ... PASSED/FAILED YES-NO" and the ATM/STM results table.
2. **City Council** journal/minutes with the ordinance roll-call for the ~39 city-council towns.
3. Mine each town's **MBTA project page** (many state the outcome) — extend the live sweep to the
   non-gap towns' `/mbta`, `/3a`, `/multifamily` pages (currently only gap towns were swept).
4. Cross-check against the **EOHLC compliance/adoption tracker** (config/mbtac_groundtruth.csv,
   not yet fetched — mass.gov is Akamai-walled; use `waf_session.mint_session`) as the recall
   denominator and to flag towns EOHLC lists as adopted but we have no vote for.

## Gap audit

62 towns still lack even a confirmed vote-bearing doc (`mbtac_audit.csv`): 42 fetched-no-signal,
16 WAF/JS-blocked (Somerville, Watertown, Arlington, Quincy, Chelsea, Everett…), 2 topic-no-vote,
2 no-candidate. These are fetch-access limited, not document-absent — the same hard tail as the
elections work.

## Deliverables

- `scratch/mbtac_votes.jsonl` / `mbtac_votes.csv` — the vote panel (town, body, date, article,
  outcome, tally, threshold, terminal flag, evidence quote, source url).
- `scratch/mbtac_audit.csv` — per-town coverage + reason buckets.
- `scratch/mbtac_extract_index.csv` — doc_id → screened doc metadata.
