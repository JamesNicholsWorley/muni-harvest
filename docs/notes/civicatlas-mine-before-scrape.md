---
name: civicatlas-mine-before-scrape
description: "before crawling municipal sites, mine the 3.27M nodes muni-harvest already holds; 95 of 225 date-held town-years were already answered, cutting the scrape from 147 hosts to 89"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

2026-08-19. CivicAtlasMA held ~225 town-years on their **date alone** — the return
is in hand and parsed, only the voting day never made it onto the page. The
obvious move was to crawl 147 town websites. Instead `src/mine_harvest_dates.py`
streamed the 1.5 GB `muni-harvest/data/discover/nodes.jsonl` (3,271,525 nodes)
and found **95 town-years already had a date lead** — 55 high-confidence, many
pointing straight at official results PDFs (`official_results_may_10_2022_ate.pdf`,
`City-Election---November-2-2021-Official-Results-PDF`). Zero new requests.

Residual = **130 town-years across 89 hosts**, written to
`config/civicatlas_date_residual_hosts.txt` in muni-harvest and swept with
`docsweep-shard` at 10 shards.

**Why:** a crawl against live town sites is the most expensive and most
outward-facing thing this project does. "Don't redo expensive work" means the
first question is not *what should we fetch* but *what did we already fetch and
never read*.

**How to apply:**
- **A date in a URL or anchor is a LEAD, never a source.** Never write it to the
  inventory; it only names a URL to fetch. Two traps proved it: Groveland's
  high-confidence lead was `2013_town_election_results.pdf` sitting under a
  `/2022/04/` upload path (the path is a *posting* date), and Medfield's was a
  **special** town election, which must never occupy an annual slot — see
  [[civicatlas-special-elections]].
- Reuse the **same gates** as the ATR pass by importing them
  (`state_election_day`, `PRIMARIES`, year range) so a date can't be rejected by
  one pass and accepted by the other. See [[civicatlas-proximity-not-aboutness]].
- Shard workflows take `--hosts-file` + `--shard i/N`, so **targeting a scrape is
  a shorter host list, not a code change**. They upload CI artifacts and commit
  nothing back. See [[muni-harvest-repo]].
- Name the residual, don't just count it (`logs/harvest_date_residual.csv`) —
  audit trail over silent exclusion.

Related: [[civicatlas-citation-not-source]], [[muni-harvest-election-recovery]],
[[wayback-muni-coverage]].
