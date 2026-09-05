---
name: civicatlas-empty-parse-is-wrong-doc
description: "the 100 EMPTY_PARSE holds were not a parse backlog: 64 are wrong documents and 11 are the wrong election; enumerate what a return IS, never what it isn't, and never give a compilation a whole-document verdict"
metadata:
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

`EMPTY_PARSE` was the biggest HOLD class in CivicAtlasMA's gate (100 stems) and
read like queued work: document in hand, `text_available: yes`, extractor just
hasn't got races out yet. All 100 sat in `pending_parse`. Opening them
(2026-08-19, `src/triage_empty_parse.py`) gave: **WRONG_DOC 64, NO_TEXT_LAYER 23,
WRONG_SCOPE 7, MIXED_SCOPE 4, COMPILATION 1, and exactly ONE genuine extractor
failure.**

Abington2022 is a conflict-of-interest policy. Boylston2021 is a 60-page FY
audit. Gill2024 is a lead-and-copper tap-water notice. Lee2023 is the municipal
telephone directory. Leverett2022/2023 are the Code of the Town. They are all
here because a harvester matched the word **"results"** — *Park Survey Results*,
*COMMUNITY ENGAGEMENT RESULTS*, *TAP WATER RESULTS*.

**Why:** the flag named the SYMPTOM (parse came out empty) and the pipeline read
it as a CAUSE (parser needs improving). Same family as
[[civicatlas-ocr-is-not-the-page]] — an empty parse is not an unparsed document,
it is usually a document with nothing in it to parse.

**How to apply:**
- **Invert the test.** My first cut enumerated kinds that are *not* returns
  (audit, warrant, ethics notice) and left 48/100 UNCLEAR — the enumeration can
  never finish, because there is no finite list of things a town publishes. A
  document is a return only if it SAYS SO in vocabulary only a return uses
  (precinct / ballots cast / blanks / were elected / write-ins). Hit counts
  separated cleanly: 0 hits 41 docs, 1 hit 22, 2 hits 6, 3+ hits 7.
- **Second question, different kind of wrong.** Of the 13 that cleared the
  vocabulary bar, 11 were a state primary, state election, special, or town
  meeting — SENATOR IN CONGRESS on the ballot. Test scope separately from kind;
  neither is fixable by a better parser.
- **Never give a compilation a whole-document verdict.** The scope test first
  condemned Egremont2021 (56pp annual report) for a state-election section inside
  it, and Lenox2022 — a 769-char turnout table whose FIRST row is the annual town
  election — for its second row. Long doc → `COMPILATION`, answer per page.
  Out-of-scope marker *alongside* an annual-municipal marker → `MIXED_SCOPE`,
  never a condemnation. This is [[civicatlas-proximity-not-aboutness]] again.
- **`NO_TEXT_LAYER` is UNCHECKED, never ABSENT** — 23 of these are scans, and the
  hold was correct. See [[civicatlas-blocked-is-a-tool-verdict]]. **But the OCR
  rotation turned out to be EMPTY.** Rendering all 137 pages whole at 170 dpi
  (`src/render_scan.py --whole`) and reading them as images found **zero** annual
  municipal returns: 14 wrong election (state primaries, state generals, SoC
  warrants, town MEETINGS), 9 not election documents at all (two drinking-water
  lab notices, a police survey, a building-needs survey, a Teamsters contract,
  two light-department agendas). Missing text was never the problem — same
  word-"results" harvest error as the text-bearing block. Retired to
  `data/setaside/{wrong-doc,not-a-record}/` + `register.csv` via
  `src/quarantine_notext_scans.py`. **Reading the page image is not OCR** and may
  condemn: it is the richest read available, strictly better than a text layer
  that does not exist.
- **The inventory already knew.** 21 of the 23 carried
  `verification: ocr_triage:wrong_doc` and a `known_bad_url` — the verdict sat in
  a column the gate never reads. Check `verification` before spending a vision
  pass. See [[civicatlas-known-bad-url-is-a-verdict]].
- Generalize the triage: any HOLD class large enough to look like a queue should
  be opened and sorted before any effort is spent making the queue move faster.
