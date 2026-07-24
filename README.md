# muni-harvest

Fast, cheap, polite harvester for MA municipal / civic documents (election results,
ZBA/planning minutes, bid tabulations, historic fire records) across **351
municipalities / 429 unique domains**.

**Core reframe:** the browser is a scarce resource to *ration*, not a default. Route
every URL through the cheapest transport that returns real content, avoid the host
entirely when a free archive already has the document, and measure the
browser-required fraction before spending a dollar. Full design + measured evidence:
`../HARVEST_SCALING_HANDOFF.md`.

## Layout

```
src/muni_harvest/
  core/       stdlib-only politeness + JSONL I/O (vendored; zero deps)
  archive/    wayback.py (primary deep source) · commoncrawl.py (discovery only)
  resolve/    tier_cache.py · resolver.py (cheapest-source-wins)
  probe/      tier_probe.py (measures the real browser-required %)
  budget/     ledger.py (append-only $40 ledger -> one-way budget.md)
  fetchers/   T0/T1/T2 live fetcher + BrowserPool  (deferred: post-probe)
  extract/    normalize.py two-layer canonical + markdown (deferred)
```

## Quickstart

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .                 # core is stdlib-only; live/extract are extras

muni-harvest budget seed         # write the opening $40 allocation
muni-harvest budget summary
muni-harvest wayback --limit 5   # free deep enumeration (resumable JSONL)
muni-harvest probe   --limit 20  # measure browser-required % (gates spend)
muni-harvest resolve             # cheapest-source-wins routing summary
```

Optional tiers: `pip install -e ".[live]"` (Selenium browser tier),
`pip install -e ".[extract]"` (fitz/docling/trafilatura normalize layer).

## Dynamic $40 budget

Tracked in `data/budget.jsonl` (append-only truth) → `data/budget.md` (generated).
Heavy spend is **gated on the tier-probe**; the ledger re-balances as free tiers
prove sufficient. Categories: VM, unblocker API, LLM/vision structuring, object
storage, contingency. Record spend with `muni-harvest budget spend ...`, rebalance
with `muni-harvest budget alloc ...`.

**LLM-structuring cost lever — to evaluate:** [TokenRouter](https://tokenrouter.io)
and similar routing/discount layers (also OpenRouter's cheapest-provider routing,
Groq's low per-token rates, Gemini Flash) before spending the `llm` reserve. Goal:
route OCR-text→JSON structuring to the cheapest adequate model per batch. Local
Ollama (Arc GPU, phi4-mini + JSON schema) remains the $0 baseline for bulk.

## Design guarantees
- **Resumable everywhere** — append-only JSONL + done-markers; crash-safe, re-run skips done.
- **Polite** — one shared `RateLimiter`, honors `Retry-After`, exponential backoff on 429/5xx.
- **Canonical → view** — `budget.md` (and later all markdown) generated one-way, never hand-edited.
- **Data never in git** — the multi-GB corpus lives in object storage; `data/` is gitignored.
