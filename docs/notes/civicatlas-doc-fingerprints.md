---
name: civicatlas-doc-fingerprints
description: "CivicAtlasMA 2026-08-17 - adjudications now carry source_sha256 so replacing a document retires its notes instead of reporting the fix as a false quote; hash not URL, and the backfill trap"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Built 2026-08-17: `qa/fingerprint_sources.py` + `qa/reference/document_fingerprints.csv`.

**The problem.** An adjudication identified its subject only by `stem` (Stow2025), and a stem
never changes. So doing exactly what an UPGRADE-SOURCE / WRONG-DOC note asked -- swapping in a
better document -- made its quoted proof vanish, and `verify_adjudications.py` reported the
successful fix as a false quote. ~150 of 501 notes are that kind and would all do this.

**Hash, not URL.** The URL is wrong in both directions: it changes without the document changing
(CMS renumber, site migration -> retires valid notes) and stays the same while the bytes change
underneath it (the stale-cache defect, see [[civicatlas-ingest-restart]]). PDF metadata is worse --
often absent, template-inherited, or wrong. sha256 changes iff the bytes change. URL is stored as
context, never as identity. A mismatch is written **STALE = re-read this**, never a deletion.

**The backfill trap.** Stamping every note with its stem's CURRENT hash is worse than doing
nothing: the already-replaced documents get the new hash and their stale notes look permanently
fresh -- the exact notes the tool exists to catch. `data/superseded_pdfs/` holds what those notes
were written against, so a stem with a superseded copy is stamped from that copy. Result: 486
current / 7 superseded / 8 no-document; the 7 STALE are exactly the 3 replaced stems.

## It immediately caught a data loss I had caused
`data/superseded_pdfs/Stow2025.pdfs.pdf` was **byte-identical to the new document**. Cause:
`src/wire_2025_replacements.py` guards its preserve step with `if not os.path.exists(dest)`, so on
a SECOND `--apply` it copied the already-replaced file and the original sample ballot was gone from
both `publish/pdfs` and `data/pdfs`. Recovered via `git show HEAD:pdfs/Stow2025.pdf` (publish/ is a
git repo) to `Stow2025.original-ballot.pdf`. **An idempotence guard on the preserve step is not
enough; preserve must be keyed on whether the CURRENT file is still the old one.**

## Two parse stores, and the gate reads only one
`data/json` (1773 files) is what `parse_gate.py` reads -- `cfg.JSON_DIR`. `publish/json` (966) is
the published mirror; 15 files exist only there. Writing a corrected parse to `publish/json` alone
leaves the gate judging the old parse and looks like the script did nothing. Write both.
