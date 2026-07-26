# muni-harvest — project status

_Last updated: 2026-07-26. Repo: https://github.com/JamesNicholsWorley/muni-harvest (public)._

## What it is
Fast, cheap, polite harvester for MA municipal / civic documents across 351 towns /
405 municipal hosts. Wayback-first, tiered (T0 HTTP → T1 cookie-lift → T2 browser),
resumable, index-only (no byte downloads yet). Built from `HARVEST_SCALING_HANDOFF.md`.

## Pipeline (all shipped, tested)
`probe` → `wayback` (sharded on GitHub Actions) → `discover` (crawl+sitemaps+CMS+
browser tier, unioned) → `scorecard` / `groundtruth` / `verify` · `budget` ledger · `store` (R2).

## Headline numbers (measured)
- **Sweep coverage:** 338/351 towns have documents. Wayback 402/405 hosts (1.87M docs);
  discover 408 hosts (1.98M nodes).
- **Doc-type coverage:** agendas 91.5%, minutes 87.2%, election 95.4%, budget/warrant/
  bylaws 95.2%, all-four 85.2%.
- **Ground-truth election recall** (vs 942 known PDFs): town-level **95.9%** (281/293),
  document-level (town+year) **70.9%** — the doc-level ceiling is 2025 recency (Wayback
  lag) + year-in-URL matching, not coverage.
- **Content-verified election precision:** ~46–70% on clean samples — i.e. a large
  fraction of URL-"election" docs are NOT results by content (the URL heuristic
  over-counts). The full content pass was throttled by archive.org and needs a
  distributed/block-aware re-run to pin down.

## Key engineering wins
- **Distributed Wayback (GitHub Actions matrix):** sharding across runner IPs beat the
  archive.org per-IP throttle — 402/405 hosts, 3 errors (vs 121 from one IP). Free.
- **Block-aware retry** (`_cdx_get`): long jittered backoff on IP-throttle signatures.
- **Per-host 429 circuit-breaker:** ends one-town stalls (Barnstable bailed at 5×429).
- **Browser tier in discover:** T2 towns (e.g. Arlington: 0→files) now live-crawled.
- **Content verifier:** opens PDFs, checks results signals — replaces URL guessing.
- **Municipal-only scoping:** 22 news hosts excluded, 8 dead domains corrected.

## Budget: $40 allocated, **$0 spent**
VM $18 · LLM $12 · storage $6 · unblocker $2 · contingency $2. Probe proved 0 municipal
sites need a paid unblocker; VM deferred (full sweep ran free locally + on Actions).

## Open issues / next
1. **Content-verify at scale** — distribute PDF downloads (Actions shards) or prefer
   live URLs; archive.org throttles bulk snapshot fetches from one IP. Then a trustworthy
   precision/recall, and tighten the results content-classifier.
2. **Doc-level recall ceiling** — 2025 results lag in Wayback (need live-crawl freshness);
   improve year matching (use parent-page/breadcrumb context, not just file URL).
3. **13 towns with no docs / 7 dns_fail towns** needing manual domain research.
4. **Gated fetch/download stage** — actually download the corpus (adds sha256 to the
   manifest for true content-dedup); provision R2 + VM when this starts.
5. Extend news/junk exclude list (a few leaked: winthroptranscript.com, etc.).
