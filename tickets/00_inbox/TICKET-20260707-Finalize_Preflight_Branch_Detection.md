---
title: "finalize-feature.js pre-flight detects the branch from session CWD, not the epic worktree"
status: todo
components:
  - build-pipeline
created: 2026-07-07
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
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
ac_coverage: 0/1
---

# finalize-feature.js pre-flight detects the branch from session CWD, not the epic worktree

## Goal
So that `/finalize-feature <epic>` works when invoked from a session whose CWD is the
workspace parent or the main clone, make the pre-flight resolve the branch and
worktree root from the epic being finalized (its worktree), not from the ambient
process CWD.

## Context
Observed finalizing EPIC-PhantomDoneFilesTouched (2026-07-07). The pre-flight agent
runs `git branch --show-current` / `git rev-parse --show-toplevel` with no `-C`
anchor, so it reads whatever git repo the session CWD lands in. In this workspace the
session CWD is the parent / main clone (on `main`), so pre-flight detected
`branch: "main"` and the workflow aborted with
`"/finalize-feature must be run from a feature branch, not main/master"` — even
though a valid epic worktree existed on branch `EPIC-PhantomDoneFilesTouched`.

Workaround used: hand-edit the generated workflow script's pre-flight to
`git -C <epic-worktree>` and resume. The workflow already receives the epic name as
`args` and has a `WORKTREE_ROOT` concept it threads to every later `git -C` — the
pre-flight should derive the worktree from the epic arg (e.g. locate the worktree in
`git worktree list` by branch `EPIC-<name>`) and anchor detection there.

See user-memory project_finalize_env_gaps and project_finalize_false_test_regression
(same "pre-flight detects branch from session cwd" note).

## Acceptance Criteria
- [ ] AC-1 (worktree-anchored pre-flight): given the epic name as input and an existing
  epic worktree on branch `EPIC-<name>` (or a single-ticket worktree), the pre-flight
  resolves `branch` and `worktree_root` from that worktree — not from the session CWD.
  Invoking `/finalize-feature <epic>` from a session whose CWD is the main clone (on
  `main`) proceeds past pre-flight instead of aborting with the main/master guard.
  When no matching worktree can be found, it fails with a clear, actionable message
  (not a silent misdetection).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |

## Comments

<!-- Append-only log — leave blank when authoring. -->

## Implementation Tasks
- [ ] In `finalize-feature.js`, derive the target worktree from the epic `args`
  (resolve via `git worktree list` matching branch `EPIC-<name>` / ticket branch).
- [ ] Anchor the pre-flight branch/toplevel detection at that worktree with `git -C`.
- [ ] Keep the main/master guard, but base it on the resolved worktree branch.
- [ ] Add a test covering "invoked from main clone CWD with a valid epic worktree → proceeds".

## Risk & Safety
- Touches money? No.
- Touches data? No — control-flow/detection only.
- Reversibility? Fully reversible.
