---
name: civicatlas-parse-identity-checks
description: "ask the record whose election it is before comparing parses; the municipality/date fields settle most disputes, and a placeholder is not an answer"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

When two CivicAtlasMA parses of one town-year disagree, run these BEFORE any
containment or vote arithmetic. Each caught a record that containment would have
decided the wrong way (`src/examine_open_parses.py`):

- **The record names its own town.** Russell2023's publish parse carries
  `municipality = "Town of Oxford"` on all six races. It is Oxford's election,
  filed under Russell — one of the `known_bad_url` mislandings. Ludlow2023's is
  Avon. No PDF needed. This is the cheapest check in the project and it had
  never been run.
- **A placeholder is not a claim.** Hingham2023's data parse says `unknown`, so a
  naive wrong-town test read it as "some town that isn't Hingham" and handed the
  record to the publish parse — which is Hingham's *2024* election. Treat
  `unknown/none/na/null/tbd` as silence.
- **Undated ≠ wrong-year.** Holbrook2021's publish parse dates all 15 races to
  2024-04-06. It survived a first-pass guard only because the data parse is
  undated, so the guard couldn't get corroboration. Saying nothing is a gap to
  fill; saying 2024 is a false claim about which election this is.
- **Zero votes everywhere = read the ballot, not the return** (OakBluffs2025).
- **An office that is a person or a street address** means the parse read the
  candidate column as the office column (Alford2025: "Otis L. Lougheed 290 West
  Road"). Don't adjudicate it race-by-race; it has misread what is being elected.

**Why:** every one of these parses is well-formed and reads as a real return, so
content tests pass them. That is the right answer to the wrong question — the
project's signature defect, a *name/pointer* trusted as an *identity/thing*.

**How to apply:** also distrust the race key before believing a race-set
disagreement. Three separate key bugs invented disputes here: `dist` missing from
the ward/precinct designator (Norwood writes `TMM - DIST. 4`), "Vote for not more
than TWO" parsed as an *unexpired term* (Lexington prints it on every race), and
OCR spelling counted as different candidates (Boermeester/Boermeister). A
ward/precinct **is** the office; test collapse flat-into-granular, since the
granular parse legitimately holds races the flat one missed. Related:
[[civicatlas-two-parse-closure]], [[civicatlas-known-bad-url-is-a-verdict]],
[[civicatlas-wrong-artifact-checks]].
