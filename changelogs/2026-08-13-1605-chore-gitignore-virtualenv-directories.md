---
title: "chore: gitignore virtualenv directories"
date: "2026-08-13"
time: "16:05"
type: manual
components: 
  - infrastructure
summary: "Adds .venv/, venv/, and root-anchored /env/ to .gitignore so a local virtualenv can no longer be staged by a git add -A."
description: "The .gitignore # Python section covered only __pycache__/ and *.pyc. The primary checkout carries an untracked 130 MB .venv/ that git check-ignore did not match, so a git add -A in leafcutter-ai/ would have staged the entire virtualenv. Adds .venv/ and venv/ unanchored (no realistic collision with a source directory) and /env/ root-anchored so a legitimately-named env subdirectory elsewhere in the tree is not silently swallowed. Verified no tracked file matches the new patterns. Merged via PR #429."
pr: 429
commits: 
  - 7ff58f247
---

## Entry

Repo hygiene: the `# Python` section of `.gitignore` covered only
`__pycache__/` and `*.pyc`, so a local virtualenv was stageable. `git add -A`
in the primary checkout would have committed ~130 MB. `.venv/` and `venv/` are
unanchored; `/env/` is root-anchored so a legitimately-named `env`
subdirectory elsewhere in the tree is not silently swallowed.
