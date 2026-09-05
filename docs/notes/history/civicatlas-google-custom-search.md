---
name: civicatlas-google-custom-search
description: Existing Google Custom Search (Programmable Search) scripts for finding MA election docs — the engine to point at gap towns
metadata: 
  node_type: memory
  type: reference
  originSessionId: 007d3b8f-950c-4487-8e4d-9f7f01fe8087
---

Prior working **Google Custom Search API (Programmable Search Engine)** setup for finding MA
municipal election documents (the user notes Google surfaces docs other search tools miss):
- `C:\Users\Owner\documents\Python Scripts\Election Search Queries\search_election_results.py`
  (main; year-agnostic `site:{town}.gov` queries, parses result URLs) + copy in
  `...\City Election Results\`. Diagnostics: `debug_api.py`, `test_setup.py`.
- Config/creds in `Election Search Queries\config.env` (API key + `cx` CSE ID).
- Session notes (`...\Municipal Web Scraping\Session_2_Summary_and_Lessons.md`) report it found
  ~460 URLs for 92 munis in only 194 queries (2.4-3.4 URLs/search).

This is the natural engine to aim at the [[civicatlas-coverage-metric]] gap towns — esp. the
**52 towns missing >=3 of 5 years** (Leicester/Russell/Richmond/Heath/Florida missing all 5),
which Annual Town Reports can bulk-fill (one ATR archive -> 3-5 town-years; user's example:
leicesterma.org/Archive.aspx?AMID=40). See [[civicatlas-2026-sweep]], [[civicatlas-history-leads-scope]].

**SECURITY:** those files hold **plaintext API keys** — Google Custom Search + Gemini, and an
**Anthropic key** in `City Election Results\apikey.txt`. Recommended (not yet done): rotate the
Anthropic key, move all to a gitignored `.env`. Do not echo the key values.
