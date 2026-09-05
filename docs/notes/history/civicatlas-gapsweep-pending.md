---
name: civicatlas-gapsweep-pending
description: CivicAtlasMA comprehensive gap sweep COMPLETE — +13 gap-fills ingested, coverage 82.6→83.3%; near-misses left staged
metadata: 
  node_type: memory
  type: project
  originSessionId: c41c2687-0b88-4d40-bb8e-183be766074d
---

CivicAtlasMA comprehensive gap sweep executed 2026-08-05 (see `CivicAtlasMA/GAPSWEEP_PLAN.md`,
`logs/PENDING_PARSE.txt`). Built [[civicatlas-detally-toolkit]] into a full gap resolver. See
[[civicatlas-gapfill-pipeline]].

**Done:** Track B muni-harvest CI (docsweep+wayback on 157 gap hosts) → 1,739 election-results doc
nodes for 135 gap towns (`_sweep_ci_seeds.py`). Local `_gapsweep.py` (govfiles template, clerk-hop,
lazy Custom-Search cap 250, tally-preferred, + hard red-herring gates: wrong-town-host via 350-town
map, year-conflict, ANTI_URL, town/year re-verify, specimen reject) over 333 gaps, 2 rounds. Staged
**55 town-years (9 tally/11 doc/15 md/19 scan) + 6 dive-ATR crops** = ~61 candidate docs. 279 gaps
unreachable (dark/unpublished tiny towns).

**COMPLETED 2026-08-05:** owner raised the $35 account USAGE LIMIT; Haiku batch
(msgbatch_012jKSQaGnZgiVRwLLfG6eR7, 54 docs, ~$0.48) → gate **13 ACCEPT / 41 REJECT** → **+13 gap
town-years ingested, 0 wrong-town, coverage 82.6%→83.3% town-years (1616/1941), 94.4% people-years**
(backup master_urls.pre_multi-20260805-094100). Filled: Alford2021, Brewster2024, Carlisle2024,
Charlemont2026, Chilmark2021/2022, Colrain2026, Egremont2022, Holland2021, Lanesborough2026,
Millville2022, Northfield2021, Rowley2024. Recoverable near-misses LEFT STAGED (GAPSWEEP_PLAN.md):
~10 wrong-YEAR good docs (Gill/Rowley2021/Petersham — grab the right year off the same clerk page),
~12 EMPTY scans (re-vision higher DPI). Correct rejects: Tyngsborough presidential, WestBrookfield=Ware.

**(historical) the blocker that delayed this:** Anthropic API **USAGE LIMIT** (NOT credit balance):
"You have reached your specified API usage limits. You will regain access on 2026-09-01." Blocks
BOTH batch + messages. Fix = owner RAISES the usage/spend limit in the Anthropic Console
(Settings → Limits) — adding credits does NOT help. Whole parse is only ≈$0.48 batch. All staged
work preserved; oversized PDFs already properly cropped (`_crop_oversized_staged.pages_for_year`),
batch payload split to 40MB sub-batches. (Local Ollama parse tried per owner's open-model pref;
Intel GPU too slow/timeouts; owner said ditch + use Haiku batch. Lesson: CHECK for a usage limit,
not just credit balance, before spending the allowance.)

**RESUME once credits added:** `python logs/_sweep_submit.py` → `_sweep_collect.py` →
`_gap_multi_ingest.py --dir data/staging_sweep [--apply]` → `src/coverage_report.py` +
`_revert_wrongtown.py`. Ingest gate (empty/nonmuni, wrong-year, wrong-town, already-published) =
the high-confidence filter (owner chose high-conf auto-ingest incl. verified OCR; rejects stay
staged for review). Alternative per owner's open-model preference: parse the 36 text docs (md +
text-pdf) with local Ollama; the 19 scans need good vision (accuracy risk — Haiku preferred).
New tools all in `logs/`: `_gapsweep.py`, `_sweep_submit.py`, `_sweep_collect.py`,
`_sweep_ci_seeds.py`. muni-harvest gained `config/gap_hosts.txt` + wayback `hosts_file` input.
