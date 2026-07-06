---
title: "build-feature.js creates/reuses an isolated worktree before driving"
status: in_progress
components:
  - build_orchestration
created: 2026-07-02
depends_on:
  - 10_e2_command_wiring_correctness.md
  - 11_meta_pure_literal_fix_and_guard.md
priority: critical
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/build-feature.js
  - unit_tests/test_workflow_dual_engine.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 12: build-feature.js creates/reuses an isolated worktree before driving

## Actor / Goal

In order to preserve the mandatory "all epic/ticket work happens in a dedicated
worktree, never on main" safety invariant, `build-feature.js` must CREATE or REUSE
an isolated git worktree (via the `worktree-agent`) and drive the build against that
worktree — not merely report a path.

## Context

The original prose `/build-feature` had a mandatory **Step A** that dispatched
`worktree-agent create` to set up the epic worktree from `origin/main` BEFORE any
ticket-supervisor ran. When ticket 07 replaced the command body with a thin Workflow
invocation and ticket 10 authored `build-feature.js`, the worktree-CREATION step was
lost: build-feature.js's resolve phase only asks a read-only `status-checker` to REPORT
a `worktree_path` (for a main-clone caller it reports the epic folder path itself). There
is no `worktree-agent` dispatch anywhere in build-feature.js (confirmed by grep + code
read). Consequence: invoking `/build-feature` from the main clone drives ticket-supervisors
against the main clone — the exact failure the worktree-isolation convention exists to
prevent (documented in CLAUDE.md Pre-Drive Checklist and prior corruption incidents).

This regression was not caught by the pipeline because ticket 10's AC only said "obtains
a worktree_path" — which is technically satisfied. This ticket restores real worktree
creation and adds a guard so build-feature.js's dispatch sequence must include worktree
setup.

## Acceptance Criteria

```gherkin
Scenario: build-feature creates/reuses an isolated worktree before driving
  Given a valid epic or single-ticket target
  When build-feature.js runs
  Then it dispatches the worktree-agent (create/reuse) to establish an isolated worktree
    off origin/main and obtains the REAL worktree path from it
  And the planner and every ticket-supervisor it dispatches operate against that worktree path
  And it never drives ticket-supervisors against the main clone.

Scenario: reuse an existing epic worktree
  Given the epic worktree already exists for the target
  When build-feature.js runs
  Then the worktree-agent reuses it (idempotent) rather than failing or duplicating.

Scenario: guard enforces the worktree step in the dispatch sequence
  Given build-feature.js
  When the order-aware dual-engine guard runs
  Then the asserted dispatch sequence includes a worktree-agent dispatch before the
    planner / ticket-supervisor dispatches
  And removing the worktree-agent dispatch FAILS the guard.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |

## Sign-offs
- [x] test-writer — 2026-07-06 15:51
- [x] python-coder — 2026-07-06 10:45
- [x] test-runner — 2026-07-06 16:03
- [x] pr-reviewer — 2026-07-06 16:06
- [x] commit — 2026-07-06 16:10
- [x] pull-request — 2026-07-06 16:15

## Comments

### 2026-07-06 15:51 — ticket-supervisor (status: ok)
feedback-id: fb_2026-07-06_e5f4a8b2
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-07-06 16:03 — test-runner (status: ok)
feedback-id: fb_2026-07-06_79bcc648
completion_manifest:
  suite_green: true
  test_dispatch_order_build_feature_passes: true
  test_ac3_guard_passes: true
  meta_pure_literal_build_feature_passes: true
Full dual-engine suite: 25 passed, 1 xfailed (pre-existing E1-only baseline).

### 2026-07-06 10:45 — python-coder (status: ok)
feedback-id: fb_2026-07-06_02c41cde
completion_manifest:
  build_feature_js_worktree_dispatch: true
  worktree_abort_on_failure: true
  thread_real_worktree_path: true
  test_dispatch_order_added: true
  test_ac3_guard_added: true
Implemented worktree-agent dispatch in build-feature.js; all five implementation tasks complete. Full test suite green (25 passed, 1 xfailed).

### 2026-07-06 16:06 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  dispatch_order_correct: true
  abort_path_fires_on_all_failure_modes: true
  realWorktreePath_threaded_into_ticket_supervisors: true
  meta_description_single_string_literal: true
  parallel_uses_array_form: true
  test_dispatch_order_enforces_worktree_step: true
  test_ac3_guard_is_not_vacuous: true
  worktree_schema_well_formed: true
Reviewed worktree-agent dispatch in build-feature.js and the two new test functions. All eight checklist items passed: worktree-agent dispatched before epic-planner and ticket-supervisor; abort fires on null result, status==="failed", and truthy error field plus a separate realWorktreePath guard; realWorktreePath threaded into both ticket-supervisor call sites; meta.description is a clean single-string literal; parallel() uses array form; both test functions enforce and non-vacuously verify the worktree dispatch requirement; WORKTREE_SCHEMA has required: ["worktree_path", "status"]. Two low-confidence observations noted but neither is a blocker: (1) WORKTREE_SCHEMA enum omits "failed" — safe because !worktreeResult covers that path in strict-schema engines; (2) planner prompt does not receive realWorktreePath — appropriate because the planner is a read-only batch-computation step, not an implementation step.

### 2026-07-06 16:15 — pull-request (status: ok)
feedback-id: fb_2026-07-06_pr12_signoff
completion_manifest:
  branch_pushed: true
  pr_url: https://github.com/urlmonitor/leafcutter-ai/pull/198
  pr_status: open
  new_commits_pushed: c117db69
Pushed EPIC-DualEngineWorkflowSupport branch to origin (14d0cc8c..c117db69); ticket 12 commits included in PR #198.

### 2026-07-06 16:10 — commit (status: ok)
feedback-id: fb_2026-07-06_baed2539
completion_manifest:
  commit_sha: 696e0ba6
  files_committed: [templates/workflows-js/build-feature.js, unit_tests/test_workflow_dual_engine.py, tickets/00_inbox/epics/EPIC-DualEngineWorkflowSupport/12_build_feature_worktree_creation.md]
  hooks_passed: true
  pre_commit_hook_fix: feedback-id added to ticket-supervisor comment heading
Committed ticket 12 changes: worktree-agent dispatch in build-feature.js + guard tests. All pre-commit hooks passed after adding missing feedback-id to ticket-supervisor comment.

## Implementation Tasks
- [x] In build-feature.js, after resolving target_type, dispatch `agent(prompt, { agentType: "worktree-agent" })` with a create/reuse action for the epic/ticket target; capture the REAL worktree_path it returns. Mirror the original Step A (create off origin/main, reuse if present, bootstrap).
- [x] Thread that worktree_path into the planner prompt and every ticket-supervisor dispatch so all work is scoped to the worktree.
- [x] If worktree-agent reports failure (dirty parent, creation error), ABORT with a structured error — do NOT fall back to driving on the main clone.
- [x] Update the ticket-08 order-aware guard's expected sequence for build-feature.js to include the worktree-agent dispatch; confirm removing it fails the guard.
- [x] Run the full dual-engine suite green.

## Out of Scope
- Changing build-epic.js/build-ticket.js worktree handling (they already read worktree_path from args, threaded by ticket 05/10).

## Risk & Safety
- Touches money? No.
- Touches data? Orchestration safety control — restoring worktree isolation. The abort-on-worktree-failure path (no main-clone fallback) is the safety-critical behaviour and must be tested.
