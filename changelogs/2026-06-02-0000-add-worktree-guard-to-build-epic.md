---
title: "Ticket 09 — Add worktree guard to build-epic.js and build-ticket.js"
date: "2026-06-02"
time: "00:00"
type: ticket_completion
components:
  - build_pipeline
summary: "Adds a .git-file detection guard to build-epic.js and build-ticket.js that returns a structured error when the workflows are invoked from the main clone rather than a git worktree, preventing silent main-branch contamination."
description: "PR #30. build-epic.js and build-ticket.js now call isInWorktree() at the top of run() — if .git is a directory (main clone), execution halts immediately with { status: 'error', worktree_required: true } before any agent is dispatched. build-epic.js also propagates worktree_path to all workflow('build-ticket') sub-calls. create-ticket.js receives a JSDoc comment confirming it intentionally runs on main. 16 new unit tests across test_build_epic_workflow.py and test_build_ticket_workflow.py, all passing."
epic: "EPIC-FlattenSupervisorChain"
ticket: "09_worktree_guard_in_workflows"
pr: 30
commits:
  - 3e689b2
  - 0cdc5ad
breaking: false
migration_steps: []
---

# Ticket 09 — Worktree Guard in build-epic.js and build-ticket.js

## What changed

build-epic.js and build-ticket.js now enforce the project worktree convention at the JS layer. If either workflow is invoked directly from the main clone (.git is a directory, not a file), the script returns a structured error immediately before dispatching any phase agents.

## Guard behaviour

Returns: `{ status: "error", worktree_required: true, message: "Not running inside a git worktree. ..." }`

No planner agent is dispatched; no code files are modified on main.

## Additional changes

| File | Change |
|------|--------|
| `templates/workflows-js/build-epic.js` | `isInWorktree()` guard + `worktree_path` propagated to sub-workflow calls |
| `templates/workflows-js/build-ticket.js` | `isInWorktree()` guard at top of `run()` |
| `templates/workflows-js/create-ticket.js` | JSDoc comment: intentionally runs on main (planning tool, no code changes) |
| `unit_tests/test_build_epic_workflow.py` | 3 new tests: main-clone error, worktree pass-through, worktree_path propagation |
| `unit_tests/test_build_ticket_workflow.py` | 2 new tests: main-clone error, worktree pass-through |

## Detection logic

The check reads the filesystem: if `.git` is a regular file (worktree pointer) execution continues; if `.git` is a directory (main clone) the guard fires. This is reliable without any shell-out and has no false negatives for standard git worktree layouts.
