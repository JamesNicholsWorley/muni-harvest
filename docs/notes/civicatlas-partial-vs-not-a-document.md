---
name: civicatlas-partial-vs-not-a-document
description: "check_truncation's DOCUMENT_IS_PARTIAL was a catch-all that assumed a town document existed; ask the citation's HOST first, and make every class overridable by a human read"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

`src/check_truncation.py` classifies a SHORT 2025 return by cause. Two defects,
both fixed 2026-08-20.

**1. A verdict a reader cannot correct is a verifier that has become the bug.**
`ADJUDICATED` was consulted only inside the `PROSE_NAMES_WINNER` branch, so the
catch-all `else` — `DOCUMENT_IS_PARTIAL` — re-asserted "this is not the whole
return" forever, no matter what a human had established. It said that of
Taunton2025, whose 6 races ARE the whole citywide ballot. Adjudications now
override **every** class (a plain string replaces the explanation; a dict with
`cause`/`why` replaces both).

**2. Ask WHOSE document it is before calling it a partial one.**
`DOCUMENT_IS_PARTIAL` claims "we hold page 1 of 4" and sends a reader to find
the rest. Lenox, Norwell and Aquinnah 2025 all carried it and **none cites a
document at all** — the sources are a Berkshire Eagle, a South Shore Times and
an MV Times story. There is no page 2. New class `SOURCE_IS_NOT_A_DOCUMENT`,
tested on a fact already on disk: the citation's host vs the town's own domain
in `data/inventory/sources/towns_websites.csv`. Unknown town or empty url keeps
the old class — an unknown must not manufacture a finding.

Confirmed by scraping all three (dead ends now recorded in `ADJUDICATED`, per
the never-silently-exclude rule): **Lenox publishes no results documents in any
year**; **Norwell's clerk posts only the current year's** (its Election Results
page holds exactly one file) and its annual town reports stop at 2023;
**Aquinnah posts returns as news items** and has none for 2025. All three are
records requests, not parsing work. Easthampton2025 by contrast IS genuinely
partial — its citation is titled "…RANK CHOICE RACES" and holds exactly the 3
ranked-choice races.

Sibling of [[civicatlas-citation-not-source]] and
[[civicatlas-empty-parse-is-wrong-doc]]: enumerate what a source IS before
labelling what it lacks. SHORT is now 10, all source problems, none unexamined.
