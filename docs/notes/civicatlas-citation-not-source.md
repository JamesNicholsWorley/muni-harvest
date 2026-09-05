---
name: civicatlas-citation-not-source
description: "CivicAtlas reported 184 town-years as no_source while holding both the document and a parse - a rotted URL was being read as a missing election. Also: votes=-1 is the uncontested-winner schema, not a hole."
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

> **Schema note, 2026-09-05.** This note predates the retirement of the `-1` and
> `-3` sentinels. Wherever it says `votes = -1`, the corpus now holds
> `votes: null` with `status: "uncontested"`; `-3` is `status:
> "write_in_winner"`. The reasoning below is unaffected -- only the spelling
> changed.

**A citation is not the source.** The owner spot-checked the towns CivicAtlas
reported as having no 2025 results and found all but three (Douglas, Tolland, New
Ashford) were online, several as the first Google hit. He was right, and nothing
had been discarded: of 21 towns checked, **20 already had a complete parse in
`data/json`** (7-13 races each) and 17 still had the document on disk. Their URL
had rotted, and a broken URL was reading as a missing election.

Three rules keyed on the URL field instead of the artifact:
* `NO_NATIVE_URL` was a **DROP** -- 101 town-years, 89 carrying no other flag.
* `NEEDS_UPGRADE` (71): condemning a URL correctly *moves* it to `known_bad_url`,
  which empties `native_url`, and the emptied field then read as "no source".
* `reconcile_inventory.py` **skipped ADMIT entirely**, so it could demote a row but
  never restore one -- 19 stems sat at `no_source` while the gate read them clean.

Total: **184 town-years asserted `no_source` while we held document AND parse.**

**The rule that settles it** is one the project already had: *content condemns,
everything else only raises*. A missing citation is not content -- it says nothing
about whether the return is real, only that we failed to write down where we got
it. So `NO_NATIVE_URL` is now a **HOLD**, `coverage_state` follows the artifact
(HOLD -> `pending_parse` whenever the document is on disk), and ADMIT ->
`published` is enforced. DROP fell 115 -> 16; `no_source` 378 -> 210 and now means
what it says. Same shape as [[civicatlas-ingest-restart]]'s stale cache and
[[civicatlas-divergence-resolved]]'s office key: a pointer trusted as the thing.

**`votes = -1` is the official schema for an uncontested winner whose exact count
the town never published** -- a correct record, not a placeholder or a hole. It
means the race has no total, so it cannot carry the ballot-closure invariant and
must be SKIPPED by arithmetic checks, never summed (summing docks a vote and makes
a good parse look broken). Fixed in `src/check_parse_arithmetic.py`;
`qa/analyze_a5_uncontested.py` already had it right.

**How to apply:** the largest class of unpublished-but-held records is now ~150
rotted citations. That is *collection* work -- go find a live URL -- not QA debt,
and it must not be confused with a coverage gap. State written up in
`CONSOLIDATION_2026-08-19.md`.
