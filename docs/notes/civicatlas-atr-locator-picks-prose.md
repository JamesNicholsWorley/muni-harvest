---
name: civicatlas-atr-locator-picks-prose
description: "the 317 pre-2021 sections holding no contest are locator failures, not parse failures: the return is absent from 83% of those cuts, the picked page is prose in 63%, and score_pages never looked at shape while grow() always did"
metadata:
  node_type: memory
  type: project
---

# The section locator scored vocabulary and ignored shape

`qa/atr_gate.py` held 317 of 1,331 pre-2021 town-years because the transcriber
found no contest in the section. Each one carries the transcriber's own reason,
and grouped (2026-09-10) they are: 125 town meeting warrants and minutes, 65
contents or index pages, 17 departmental narratives, 15 state or primary
returns, 15 officers directories and salary schedules, 4 caucus minutes, and 76
others of the same kind. Not one is a reader that failed on a return.

## The return is not in the cut

Opened the 919 cut PDFs that carry a text layer and asked each page
`atr_sections.is_tally` — three or more ballot words, laid out as a table:

    sections that reach `publish`   96% contain a tally page  (244 of 255 sampled)
    sections holding no contest     17% contain a tally page  (40 of 236)

So this is not a parse backlog and a better model will not touch it. The cutter
took the wrong pages, and the report almost certainly still holds the return.

## Why it took them

`grow()` has always known that a return is a table and minutes are prose: it
uses `prose_score` to decide whether a page CONTINUES the section, with the
comment "a tally page runs 5 to 17 characters a line; the minutes run 47 to
69." The page that STARTS a section was chosen by `score_pages`, which counted
headings, ballot words and office names and never looked at the shape at all.

Town meeting minutes are minutes ABOUT Selectmen, the Moderator and the Finance
Committee. They carry the same vocabulary as the return and beat it on volume.
199 of the 317 failures picked a page over 30 characters a line; the median
failure sits at 38 and the median publishing cut at 13.

## The fix is a weight, never a cutoff

A cutoff at 30 characters takes out Hawley's all-uncontested return, which sits
at 26 — the loss the module's own docstring exists to prevent — and 127 of the
602 sections that publish today with it. So `shape_score` adds +6 below 20
characters a line, +3 below 30, -6 at 45 and above, and a page whose vocabulary
is strong enough still wins.

Tested on the 519 cuts that hold a tally page: the shape term promotes the
tally page in 22 cuts where vocabulary alone had picked prose, and demotes one
in **none**. That is a one-sided result and it is all this test can be: the
cuts are 3 to 6 pages, so it shows the term does no harm and helps inside a
window. How many of the 317 it rescues over a whole 130-page report can only be
measured by re-cutting, which needs the reports fetched again.
