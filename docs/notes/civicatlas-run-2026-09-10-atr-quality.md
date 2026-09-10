---
name: civicatlas-run-2026-09-10-atr-quality
description: "unattended run 2026-09-10 on the pre-2021 ATR corpus: publish 547->602, what was read and what it concluded, and the three things it deliberately did not do"
metadata:
  node_type: memory
  type: project
---

# Run of 2026-09-10 — pre-2021 ATR quality

    publish  547 -> 602
    review   336 -> 280
    hold     448 -> 449

58 records moved review -> publish. Three left publish because the page dates
them outside their town-year. Belmont 2018 moved review -> hold. Everything not
publishing is listed in `qa/reference/atr_still_waiting.csv`, ranked by
population.

## What was changed, and on what evidence

**A ballot question is not an office.** 61 contests. Every one prints YES and
NO where a contest prints people; every one left its seat count null; the tool
schema has a `questions` field of its own and the published 2021-2026 corpus
holds no question at all in 19,642 contests. Each of the 61 was found in the
section text before the rule was written — 54 in a text layer, 5 by OCR of the
scan, 2 in a multi-column layout that a key match missed and a wider read
found. 26 returns were being withheld over one.

**A dash is not an unreadable figure.** Sterling 2011 prints `-` for a write-in
row whose precinct cells read 0 and 0, and the contest closes on its own
printed total. Two fills, each refusing where a blank has been seen to lie:
Belmont 2018's eighth column is its town total, so whether a breakdown may be
summed is asked of the record first and one disagreeing row stops all of them;
Granby 2015 prints "Sworn" beside every winner with the winner's own precinct
figures, so a row repeating another row's breakdown is a column and not a
candidate. A residual against a printed total is taken only for a Blanks or
Write-ins row. A named person's blank is never filled — that is what a dropped
candidate looks like.

**Dates the reader could read and the bridge could not.** The word form ("the
Eighth Day of May, 2010") was described in a comment and never implemented; the
pattern demanded `\d`. Added with the spreadsheet form (15-May-18), the
day-first form (11 May 2017) and the two-digit year (5/21/19). Each of the 19
was verified against its section text first.

**Two refusals the other way.** The fiscal-year offset is a year at most, which
the code said in a comment and never enforced: Salem 2010's section prints
"NOVEMBER 6, 2018" and was publishing. And 1 January is what an empty date cell
prints — Barnstable 2018's table heads itself `DATE 1/1/17` while the Clerk's
report in the same section says November 2017, and no election in either corpus
falls in January.

**The locator scored vocabulary and ignored shape.** Full account in
`civicatlas-atr-locator-picks-prose.md`. `shape_score` added to `score_pages`,
tested one-sided over 519 cuts: 22 improvements, 0 regressions.

## What was deliberately not done

**The bridge drops the transcriber's flags.** `atr_bridge.bridge()` builds its
output without `document_problems` or per-contest `problems`, so
`escalate.review` never sees them and the gate's own "the document is not a
return" branch cannot fire on a bridged record. Carrying them through moves 244
records down a rung. Not applied: the `WRONG_DOCUMENT` pattern fires on a
mention rather than on the document's identity — it holds Duxbury 2012 for
"contains Annual Town Meeting minutes" and Medway 2017, whose date this run
read off its own return, for "the first page shows an unrelated list". Switching
the flags on without fixing that regex would hold real returns.

**A seat count from the town's other years.** 90 null seat counts in 44 records
have a unanimous answer across two or more other years of the same town and
office. Checked against the ballot arithmetic where it can speak: 32 agree, 29
of them exactly — and 15 are contradicted. A 32% contradiction rate is not a
derivation. It is a lead.

**The precinct denominator.** `escalate.derive_ballots` exempts
`regional_district` and pools `sub_town` with the rest, so a Town Meeting
Member race is measured against the town's ballots instead of its precinct's.
Framingham 2015 derives a ballot count of 91 and reads as six impossible
contests. It affects 12 of the 132 impossible-arithmetic records — real, small,
and a change to the arithmetic every record rests on, so it goes to the owner.

## What blocked the biggest pile

The 317 sections holding no contest are locator failures and re-cutting is the
fix. Re-cutting needs the reports fetched and the cuts parsed, and this
environment has no Anthropic API key — `tools/atr_parse.py` has no workflow, it
runs from the owner's machine. So a re-cut here could not have converted a
record this run, and the effort went into the locator change that the next
re-cut needs. Wayback is reachable from this runner (200 on `web.archive.org`;
the one Bedford 2019 snapshot tried returns a robots-excluded 404).
