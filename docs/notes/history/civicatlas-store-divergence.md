---
name: civicatlas-store-divergence
description: CivicAtlas kept two copies of every artifact (data/ and publish/) that silently disagreed; 216 town-years had different parses under the same name. data/ is now authoritative and publish/ is derived.
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CivicAtlasMA stored every artifact twice — `data/` and `publish/` — with nothing
comparing them. Discovered 2026-08-17: the two stores disagreed about **216
town-years** (180 substantively) and **26 PDFs**. Salem2023 was 10 races in
`data/json` and 76 in `publish/json`. For 159 ADMIT stems the corpus was
publishing a parse `parse_gate.py` had never seen, under the name of one it had
approved.

**Why:** this is the stale-cache defect at corpus scale — a *name* was trusted to
identify a document when two documents held that name. Whichever directory a
reader looked in first decided what a town-year "was," and no error was ever
raised. It is the same root cause as the keyed-on-stem PDF cache (see
[[civicatlas-ingest-restart]]) and as the fingerprint problem
([[civicatlas-doc-fingerprints]]).

**Authority is not correctness — this was tested and the test bit.** Scoring both
parses against the held document (`src/compare_divergent_parses.py`) decided 40 of
180: **23 favour `data/`, 17 favour the withdrawn `publish/` parse**, 14 of those
ADMIT records currently shipping. Athol2023 ships 5 races when 13 are on the page;
Needham2022 ships vote totals 2–4 higher than the page shows. `logs/parse_validation.csv`
is a July artifact describing the *publish* generation, so it cannot adjudicate.
Score only the **disputed** cells — averaging over races both parses agree on
diluted 107 of 180 to "too close" and hid all of this.

**How to apply:** `data/` is authoritative because it is what the gate reads —
that is an *authority* argument, not a correctness one, and publish/ often held
the richer parse. Never resolve a divergence by picking a store and deleting the
loser: every variant was preserved to `data/divergent_parses/` and
`data/conflicting_pdfs/` with a register, because those 180 + 26 unsettled
readings are a worklist, not garbage. `publish/` is now exactly the ADMIT set and
genuinely derived; regenerate it, never edit it.

Related: [[civicatlas-qa-tail-close]], [[civicatlas-consolidation]].
