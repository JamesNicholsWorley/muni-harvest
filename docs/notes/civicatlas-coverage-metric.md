---
name: civicatlas-coverage-metric
description: CivicAtlasMA coverage 2021-2026 is 80.5% by town-year but 93.2% population-weighted; report both
metadata: 
  node_type: memory
  type: project
  originSessionId: 007d3b8f-950c-4487-8e4d-9f7f01fe8087
---

CivicAtlasMA coverage should be read TWO ways, and the report shows both. As of 2026-08-04,
**2026 was MERGED into master_urls.csv as a normal 6th year** (no longer a separate
provisional cohort). Post-merge headline started at **2021-2026: 75.3% town-years** (1,462 / 1,941) / 89.8%
people-years. After the Google Custom Search 2026 sweep (2026-08-04, +57 town-years, see
[[civicatlas-2026-sweep]]) it rose to **78.3% town-years** (1,519 / 1,941) / **92.1%
people-years** (28.49M / 30.92M); **2026 alone 194/296 = 65.5%** (was 137/46%). The merge had
DROPPED the headline from the 2021-25-only figures (~80.5% / 93.9%) because 2026 is only
partially collected; the sweep is closing that gap. The town-year-vs-people-year gap persists because uncovered
town-years are overwhelmingly TINY towns — cities are near-fully covered, so population
weighting tells the truer story. See [[civicatlasma-project]], [[civicatlas-2026-sweep]],
[[civicatlas-history-leads-scope]].

2026 denominator = **296 even-year towns**, derived as towns with an expected 2022 OR 2024
row in master_urls (matches the old hardcoded EXPECTED_2026=296 exactly). Merge script:
`logs/_merge_2026.py` (backs up master to `.pre_merge2026-<stamp>.csv`, copies
`data/json_2026/*.json` -> `data/json/`; 137 published + 159 no_source gaps). The former
`y2026_hosted.csv` + `data/json_2026/` are now superseded (kept as backup, not deleted).
`coverage_report.py` was rewired: PRIOR_YEARS now includes 2026, the provisional candidate
card + y2026_stats() were removed.

`CivicAtlasMA/src/coverage_report.py` (no args, no network, no writes) renders both metrics
per-year to reports/coverage.html; population comes from `open_search_tabs.population()`
(returns a dict of 351 town->pop; call with NO args). The remaining people-year gap is
concentrated in a few cities — the biggest uncovered by population are Springfield 2023
(156k), Newton 2021 (89k), Leominster, Dracut x3, Stoughton, West Springfield, Agawam —
so chasing those larger towns moves the population-weighted number far more than the ~131
tiny dark-floor town-years combined.
