---
name: civicatlas-infra-baseline
description: "CivicAtlasMA infrastructure as of 2026-08-20 - three separate git repos, inventory.py is the only write path, check_invariants.py is the blocking pre-push guard, and a live Google service-account key sits in config/"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CivicAtlasMA got its infrastructure pass on 2026-08-20. Four things are now true
that were not before, and each replaces a habit that had already failed once.

**Three git repositories, deliberately separate.** Root (`.git` at
CivicAtlasMA/) tracks the CODE - 136 `src/` scripts, `qa/`, `research/` notes,
531 files / 33 MB. `data/` and `publish/` each have their own. They are NOT
tracked from the root: different lifecycles, and two histories that could
disagree about the same file is the exact drift failure this project keeps
paying for (see [[civicatlas-two-authorities-drift]]).

**`src/inventory.py` is the only write path to `master_urls.csv`.** All 16
remaining direct writers were converted. It gives a lockfile, atomic
write-to-temp-then-rename, an auto-commit to `data/`'s history labelled with the
caller, and a shrink guard that REFUSES a save losing >2% of rows. The shrink
guard counts the file on disk when the caller did not load through
`inventory.load()` - a guard that needs the caller to cooperate twice is off in
exactly the scripts nobody has revisited. This is the designed answer to
[[row-predicate-cannot-bound-a-row-set]].

**`src/check_invariants.py` is the pre-push guard**, wired into
`sync_to_github.push()`. There is no `--force`: this project has no override
mechanism by decision. It splits BLOCKING (8 structural checks, all green - any
red is damage done since) from DEBT (counted, carried in the open, currently
200 rows citing a URL they also condemned + 6 ADMIT rows with no citation).
That split is what stops a guard from being switched off on day one.

**Why the first run mattered more than it looked:** 5 of 9 checks failed and
THREE of those were the CHECK being wrong, not the corpus - a parse schema I
invented (`elections` is a flat list of races, no nested `races` key), a register
`reason` vocabulary I flattened (`pdf-variant`/`superseded-store`/`orphan` retire
a COPY, not the document), and an equality test on a space-separated column.
Same lesson as [[civicatlas-proximity-not-aboutness]]: the verifier is more often
wrong than the corpus. Grade the checker before believing it.

**Security, unresolved:** `config/hopeful-market-449321-u9-*.json` is a live
Google service-account key with a `private_key` field, in plaintext in the
project directory. The first `git add -A` staged it. `config/*.json` is now
ignored as a shape rather than by guessing filenames, but the key itself is
still on disk and has not been rotated.

**Known code defect, not yet fixed:** `src/retire_wrongdocs_20260819.py:131`
writes `known_bad_url = "wrong-doc: " + url` - prose into a URL column, and an
overwrite that destroys any previously condemned URLs. `known_bad_url` is
space-separated and append-only everywhere else (see
[[civicatlas-known-bad-url-is-a-verdict]]).
