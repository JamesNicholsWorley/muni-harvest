---
name: civicatlas-credentials-and-git
description: How to push to GitHub and run paid API scripts in the CivicAtlasMA project
metadata: 
  node_type: memory
  type: reference
  originSessionId: aada0ce6-9430-4ae7-b56d-3a0d25e402d7
---

CivicAtlasMA (`C:\Users\Owner\documents\civicatlasma`) credential + git facts:

- The git repo is the **`publish/`** subdirectory (remote `origin` = github.com/JamesNicholsWorley/civicatlasma, branch `main`). The project root itself is **not** a git repo. `data/json` is the local working copy; `publish/json` is the git-tracked mirror that gets pushed.
- **Pushes authenticate via `GITHUB_TOKEN` in `config/.env`** (a fine-grained PAT scoped to the repo). `git push` alone fails auth. Push with the token in an auth header, e.g. load `GITHUB_TOKEN`, then `git -C publish -c http.extraheader="Authorization: Basic $(printf 'x-access-token:%s' "$TOKEN" | base64)" push origin main`. Keep the token in a shell variable so it isn't printed.
- When staging `publish/` changes, use `git -C publish add -u json/` — `publish/` has many **untracked** PDFs/markdown, so never `git add -A`.
- `ANTHROPIC_API_KEY` in `config/.env` was blank early on but was populated by the user on 2026-07-06, so paid scripts (`src/parse_corpus.py`, `src/measure_parse_cost.py`, `src/test_parse_model.py`) now authenticate. If it's ever empty again, that's the first thing to check.
- The Bash tool here is real bash, not PowerShell — don't use PowerShell here-strings (`@'...'@`) or `if ($?){}` in Bash calls.
