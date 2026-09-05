---
name: civicatlas-consolidation
description: "CivicAtlasMA is the hub for the MA muni-election work; folder map, archived precursors, and the unpushed-publish state"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4ef371b9-c9df-4085-b6f9-912a8d19872a
---

Consolidation pass 2026-08-12 on the MA municipal-election work.

**Hub = `C:\Users\Owner\Documents\CivicAtlasMA`.** Read `PROJECT_MAP.md` there first — it maps how
the sibling folders connect and which are kept-in-place vs archived. The folders are wired by
hardcoded absolute paths, so they were NOT physically merged (owner chose "hub + index, clean in
place"):
- `muni-harvest` (public git repo, the doc-finder) → feeds CivicAtlas via `scratch/dive_confirmed.csv`. See [[muni-harvest-repo]], [[muni-harvest-election-recovery]], [[mbtac-vote-finder]].
- `ResearchLab` (OCR/parse R&D sidecar, read-only consumer). See [[researchlab-project]].
- `Python Scripts\Archives\Reports` = `REPORTS_DIR` (~10.5 GB ATR corpus, in place); `Python Scripts\.env` = Custom Search keys; `Python Scripts\XLSX\election_results (4).sql` = gold.

**Archived** (moved 2026-08-12, nothing deleted, all restorable): `_archive\civicatlas-precursors\` = superseded precursors (`ma-municipal-crawl`, `Municipal Web Scraping`, `City Election Results`, `Election Parsing`, `Review Sources`; nothing active references them). `_archive\civicatlas-working\` = CivicAtlasMA's regenerable/superseded intermediates (fetch pools, `staging*`, `json_pre_*`, `raw_ocr`, `ci_artifacts`, crawl logs, 52 old inventory backups — newest 5 kept in place); rejected doc pools kept here with `REJECTED_POOLS_MANIFEST.txt` (357-name avoid-list). Main folder 4.31→1.94 GB; `__pycache__` left in place. `Exploratory\` is mostly unrelated projects.

**Publish state (non-obvious):** the site is `github.com/JamesNicholsWorley/civicatlasma` (public
Pages). The publish clone is `CivicAtlasMA\publish\` (parent folder is NOT git). **Last push was
2026-07-06**, so the whole gap-fill arc (coverage ~64%→84.7%, 1,644/1,941 published) is UNPUSHED:
4 commits ahead + 771 working-tree changes (716 new pdfs/markdown, 30 deletions to review, 25 mods).
Owner now wants to *get ready* to publish the missing docs — a shift from the 08-07 "local only"
rule. Steps + blockers staged in `CivicAtlasMA\PUBLISH_READINESS.md` (do NOT push without explicit
go; rotate the `config/.env` ROTATE-marked secrets first). A fresh QA sweep (`qa_archive/`,
`python -m tests.civicqa.cli`, PyMuPDF present) is read-only and ready.
