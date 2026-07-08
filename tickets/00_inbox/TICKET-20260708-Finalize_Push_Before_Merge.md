---
title: "finalize-feature.js merges the PR without pushing local commits — unpushed fixes are silently dropped"
status: todo
components:
  - build_pipeline
created: 2026-07-08
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: contract_boundary
requires_diagram: false
requires_adr: false
tags:
  - finalize-feature
  - data-loss
files_touched:
  - templates/workflows-js/finalize-feature.js
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# finalize-feature.js merges the PR without pushing local commits — unpushed fixes are silently dropped

## Actor / Goal
In order to prevent finalize from silently shipping a stale tree to `main`, we need
`finalize-feature.js` to guarantee the local feature-branch HEAD is on origin before it
merges the PR (Step 4), so that any commit made on the branch after the last ticket's
`pull-request` phase is included in the merge instead of dropped.

## Context
Observed while finalizing **EPIC-TrustworthyTestGate** (2026-07-08).
`finalize-feature.js` contains **no `git push`** anywhere — Step 4 merges the epic PR via
`gh pr merge` against the **origin** PR head. During a normal drive this is fine because
each ticket's `pull-request` phase pushes as it completes. But any commit made on the
branch **after** the last ticket signed off — e.g. a code-review fix, a
`origin/main`-into-branch merge, or a manual edit at finalize time — is local-only. If
finalize runs as-is, `gh pr merge` merges the older origin head and the local commits are
**silently excluded from `main`**.

Concretely today: code-review fix commit `2a377f91` (and later a merge commit) were local
and unpushed; had finalize run without a manual `git push`, the H-1/M-1 fixes would not
have reached `main`. The gap was caught only because the finalize script was read and the
branch pushed by hand first. This is a silent-data-loss class bug — the merge "succeeds"
and reports success while dropping work.

Related (already fixed, do not re-do): the pre-flight CWD branch-detection bug is closed by
TICKET-20260707-Finalize_Preflight_Branch_Detection (PR #231). This ticket is a distinct
Step-4 gap.

## Acceptance Criteria
- [ ] AC-1: Before Step 4 (`gh pr merge`), `finalize-feature.js` compares the local
  feature-branch HEAD against the origin branch head and, when they differ (local ahead),
  pushes the branch to origin (or HALTs with a clear, actionable message) — so the PR head
  that gets merged always contains every local commit. A run with an unpushed local commit
  must NOT merge a stale head to `main`.
- [ ] AC-2: The `/finalize-feature` command/doc no longer instructs callers to pass an
  object (`{ branch: ... }`); it documents the plain-string argument that the script
  actually consumes (`typeof args === 'string'`). Passing the epic name as a string is the
  documented, working invocation. (Optional hardening: tolerate an object arg with a
  `branch`/`epic` key instead of falling through to CWD detection.)

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] In `finalize-feature.js`, add a pre-Step-4 sync check: resolve local HEAD and
  `origin/<branch>` head; if local is ahead, `git -C <worktree> push origin <branch>` (or
  HALT with `action_required: push_local_commits`).
- [ ] Verify origin head == local HEAD after the push before invoking `gh pr merge`.
- [ ] Fix the `/finalize-feature` command doc's invocation example to the plain-string form
  (remove the misleading `{ branch: ... }` example).
- [ ] Tests: a scenario asserting finalize refuses/repairs a stale origin head before merge;
  a doc/static check for the corrected invocation example.

## Risk & Safety
- Touches money? No.
- Touches data? No user data — but prevents loss of committed source work at merge time.
- Reversibility? Fully reversible; adds a guard/push step to the workflow script.
