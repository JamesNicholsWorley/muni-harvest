---
name: civicatlas-two-parse-closure
description: "the 60 open two-parse town-years are CLOSED; all 25 decidable went to the data parse; decide identity, then scope, then completeness"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CLOSED 2026-08-19. The 60 CivicAtlasMA town-years holding two parses were mostly
not disagreements. `src/close_variants.py` settled 34 structurally; the residual
26 went to `src/examine_open_parses.py`, which decided **25 — every one of them
to the `data` parse**. `data/json` was already correct throughout; the only edit
was reverting Adams2025, which held a publish variant from an earlier apply.

The 26th, Holland2025, was closed later the same day and went the OTHER way — to
`publish` — once someone finally looked at the image. See
[[civicatlas-ocr-is-not-the-page]]; the "needs a replacement document" verdict
recorded here first was wrong about the document.

**Why:** almost none of the 26 needed a document. Three did. The rest fell to
cheap checks nobody had run — and the ones that looked like disagreements were
usually a defect in the comparison key, not in the data.

**How to apply:** order the tests **identity → scope → completeness**, and only
ever adopt the bigger parse at the end. Report:
`data/setaside/open_parse_examination.csv`. See
[[civicatlas-parse-identity-checks]] for the checks themselves and
[[civicatlas-scope-municipal-only]] for what counts as in scope. Related:
[[civicatlas-divergence-resolved]], [[civicatlas-wrong-artifact-checks]].
