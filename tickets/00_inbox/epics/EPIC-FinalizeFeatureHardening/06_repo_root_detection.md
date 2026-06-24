---
title: "Replace CWD-trusting git detection with explicit repo-root anchoring"
status: todo
components:
  - worktree_manager
  - build_pipeline
created: 2026-06-24
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/workflows-js/finalize-feature.js
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 06: Replace CWD-trusting git detection with explicit repo-root anchoring

## Actor / Goal

In order to stop the finalize and worktree-setup scripts from resolving the wrong
(or no) git repo in the self-hosting layout, we need them to anchor on an explicit
repo path / `git -C <path>` instead of trusting the process CWD.

## Context

The git root here is `leafcutter-ai/`, but the session/working CWD is its
**untracked parent** `leafcutter/` (ADR-001 self-hosting boundary). Both scripts
resolve repo context via `git rev-parse` in the process CWD:

- `setup_ticket_worktree.py::_git_toplevel()` (≈ lines 58-75) runs
  `git rev-parse --show-toplevel` with no `cwd=` / no `--repo`. Its result seeds
  `worktrees_dir = main_repo.parent / "worktrees"` and all downstream bootstrap.
  This session reproduced the failure: run from `leafcutter/`, it raised
  `CalledProcessError ... returned non-zero exit status 128`.
- `finalize-feature.js` pre-flight (≈ lines 74-96) dispatches `status-checker`
  with bare `git branch --show-current` / `git rev-parse --show-toplevel` and no
  explicit path; every later step (`git checkout main`/`git pull`, the merge probe,
  the reconciliation) inherits the agent's ambient CWD.

When run from the wrong directory these either error to the `{branch:"unknown"}`
abort path or, given nested `.git` dirs in the workspace, resolve to the *wrong*
repository.

## Acceptance Criteria

- [ ] AC-1: `setup_ticket_worktree.py` accepts an explicit `--repo-root` argument;
  `_git_toplevel()` runs `git -C <repo_root> rev-parse --show-toplevel` when
  provided, falling back to CWD only when omitted.
- [ ] AC-2: With `--repo-root` pointing at `leafcutter-ai/`, the script completes
  repo detection successfully even when the process CWD is the untracked parent.
- [ ] AC-3: `finalize-feature.js` threads the pre-flight-resolved `worktree_root`
  into every dispatched step's git commands as an explicit `git -C "<root>" ...`
  prefix (sync, merge probe, and any commit/move steps that remain after ticket 04).
- [ ] AC-4: Existing callers (build-single-ticket, feature, worktree-agent) pass the
  known repo path so the common path no longer relies on CWD.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] Add `--repo-root` to setup_ticket_worktree.py; route `_git_toplevel()` through `git -C`.
- [ ] Update callers to pass the repo path.
- [ ] Thread `git -C "<root>"` into finalize-feature.js step instructions.
- [ ] Tests for explicit-path detection from a non-repo CWD.

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High — argument is additive with a CWD fallback.
