---
title: "Worktree bootstrap: the build step leaves dozens of tracked files modified in a fresh worktree"
status: todo
components:
  - worktree_manager
  - build_pipeline
created: 2026-10-02
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - worktree
  - build
  - windows
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# Worktree bootstrap: the build step leaves dozens of tracked files modified in a fresh worktree

## Actor / Goal
In order to start every piece of work from a clean tree, we need `setup_ticket_worktree.py`'s
bootstrap (`_bootstrap`, which runs `build.py`) to leave a freshly created worktree with no
modified tracked files.

## Context
- **Observed 2026-10-02, on Windows,** on three worktrees created with `create-only`, both
  before and after resetting them to current `origin/main`. Right after bootstrap,
  `git status` showed 5 to 62 modified tracked files:
  - `LEAFCUTTER_VERSION`
  - `docs/INDEX.md`
  - most of `docs/agents/cards/*.card.md`
- **Every one** came with git's "CRLF will be replaced by LF the next time Git touches it"
  warning. That suggests the build writes generated files with platform line endings (CRLF on
  Windows) while the repository stores LF. It may also include real drift between committed
  generated files and current build output. Both need checking.
- **Effect:** every new worktree starts dirty. Agents must `git restore` the build's side effects
  before they can stage cleanly, and a careless `git add -A` would commit them.

## Scope
- Find out which part is line endings and which is real content drift.
- Make generated outputs byte-stable across platforms, for example by writing with `newline="\n"`.
- If committed generated files are stale on `main`, regenerate and commit them once.
- Add a check that bootstrapping a fresh worktree yields a clean `git status`.

## Out of Scope
- The base-branch choice of `create-only`, handled separately.

## Comments
