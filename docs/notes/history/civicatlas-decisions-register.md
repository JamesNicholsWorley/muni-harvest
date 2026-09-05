---
name: civicatlas-decisions-register
description: "CivicAtlasMA now has DECISIONS.md (every standing rule, dated, with the code that implements it) and OPEN_QUESTIONS.md (what was raised and never closed) - read both before re-deriving any rule from the corpus; the known_bad_url question is settled for the published half and source_sha256 must NOT be used to test verdict staleness"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Written 2026-08-20 from 518 human turns and 58 compaction summaries across 17
Claude Code transcripts, mined by `src/mine_transcripts.py` (`--batches` splits
typed turns from compaction summaries; `--grep` searches).

**`CivicAtlasMA/DECISIONS.md`** is the register of what is settled: scope, the
ADMIT/HOLD/DROP gate, citation, sources, schema, stores, method, privacy, and a
"corrections that became rules" section. Every entry names where it is
implemented. **If the code and the register disagree, that is a defect, not a
judgement call.** Read it before writing any check that answers a policy
question -- the reason it exists is that a citation check re-derived a settled
ruling from artifacts alone and reported six clerk-supplied town-years as
uncited (see [[civicatlas-infra-baseline]]).

**`CivicAtlasMA/OPEN_QUESTIONS.md`** is the honest half. Its §1 -- the question
the user raised personally -- was **settled 2026-08-20 for the published half**:
of 200 rows citing a URL they also condemned, all 64 published ones were
gate-ADMIT, so the *condemnation* was the stale side, not the citation. Retracted
into `data/setaside/retractions.csv`; debt 200 -> 136 (54 still-live, 82 never
judged, none published). See [[civicatlas-known-bad-url-is-a-verdict]].

The sha256 test this memory used to prescribe **does not work, do not use it**:
`qa/fingerprint_sources.py` BACKFILLS `source_sha256` onto any adjudication
lacking one using whatever is on disk at run time, so a stale verdict gets stamped
with fresh bytes and reads as live (Leverett2021 is the proof). A hash proves what
was on disk when it was *stamped*, never when the verdict was *reached*. What
decides staleness is the gate re-reading the artifact -- ADMIT means the
condemnation is about a document we no longer hold. Contradicts what
[[civicatlas-doc-fingerprints]] implies about using the hash for this.

**The register is not only DECISIONS.md — the per-sweep CSVs adjudicate too, and
they are the ones that get skipped.** 2026-08-20: I built a scan-OCR office
enumerator, ran it over a 17-page Lee 2025 scan, then mined 3.27M harvest nodes,
to establish that Lee's cited document is a town-meeting warrant with no tallies.
All of it was already written, that same day, in
`logs/truncation_2025.csv` — cause `SOURCE_IS_NEWS_SUMMARY`, with the arithmetic
(School Committee 250 of 300, Housing Authority 44 of 150) and the note that the
town's Past-Town-Elections page stops at 2021. **Before interrogating the corpus
about a town-year, grep the logs/ CSVs for its stem.** The adjudication columns
(`why`, `cause`, `in_text_but_not_in_parse`) are prose written by a reader and
they answer "has this already been settled" in one line.

Also open there: the unrotated Google service-account key, a ~440 MB regenerable
cleanup awaiting a yes/no, the deferred data queue (139 unprocessed
manual_finds rows, 16 compilation reports, 43 F1 findings), and whether the
older `docs/*.md` handoffs now contradict the register.
