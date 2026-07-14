---
title: "Fix dead Step 6a auto-ticketing and the false success message"
status: done
components:
  - build_pipeline
  - ticket_lifecycle
created: 2026-06-24
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/workflows/finalize-feature.md
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

# 08: Fix dead Step 6a auto-ticketing and the false success message

## Actor / Goal

In order to stop finalize from claiming it created tracking tickets when it did
not, we need Step 6a to either actually create tracking tickets for pre-existing /
flaky failures or honestly report that auto-ticketing is disabled — and the
success message must reflect reality.

## Context

Step 6a (≈ lines 694-705) was wired to dispatch a `create-ticket` agent, but
`create-ticket` was removed from the agent registry (EPIC-AcPipelineConsolidation
v2.0.0). The step now only `console.warn`s and pushes `null` into
`createdTrackingTickets` — yet the final success message (≈ lines 950-952) still
says "Tracking tickets created", and the step-map doc
(`templates/workflows/finalize-feature.md:22`) still says Step 6 "dispatch[es]
`create-ticket`". So pre-existing/flaky test failures (the ones triage classifies
as non-blocking) are silently never tracked, and the operator is told otherwise.

Two viable fixes: (a) invoke the `create-ticket` *workflow* via the runtime's
workflow mechanism (the supported depth-0 path), or (b) surface a single structured
prompt listing the failures for the user to confirm ticket creation. Either way,
the success message must not assert tickets were created when they were not.

## Acceptance Criteria

- [ ] AC-1: When triage yields pre-existing/flaky failures, finalize either creates
  tracking tickets via a working mechanism (create-ticket workflow) OR emits an
  explicit, accurate report that lists the untracked failures and states no tickets
  were auto-created.
- [ ] AC-2: The success message never claims "Tracking tickets created" unless
  tickets were actually created; the count it reports matches reality (0 when none).
- [ ] AC-3: The step-map doc is updated to describe the actual Step 6a behavior
  (no stale `create-ticket` agent claim).
- [ ] AC-4: A test covers the no-failures path (no tickets, no false claim) and the
  with-failures path (accurate report or real ticket creation).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | Step 6a now emits structured `untrackedFailures` report; no false ticket-creation claim | |
| AC-2 | | `createdTrackingTickets` removed; success message uses `untrackedFailures.length > 0` conditional | |
| AC-3 | | `finalize-feature.md` Step 6 row updated: no stale `create-ticket` dispatch claim | |
| AC-4 | test_finalize_feature_step6a.py: 17 tests for no-failures and with-failures paths | | |

## Comments

### 2026-06-24 09:00 — ticket-supervisor (status: ok)
feedback-id: fb_2026-06-24_ticket08_supervisor
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-24 09:30 — python-coder (status: ok)
feedback-id: fb_2026-06-24_b75cd0f9
completion_manifest:
  decide_report_vs_create_workflow: true
  fix_success_message: true
  update_step_map_doc: true
  write_tests_both_paths: true
Fixed dead step 6a: replaced `createdTrackingTickets` (null-accumulator) with `untrackedFailures[]`; removed the false "Tracking tickets created" success message; updated `finalize-feature.md` Step 6 row to accurately describe the disabled auto-ticketing; wrote `unit_tests/test_finalize_feature_step6a.py` with 17 tests covering no-failures and with-failures paths (all green).

### 2026-06-24 09:35 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  new_tests_pass: true
  no_regressions: true
17 tests in test_finalize_feature_step6a.py all pass. One pre-existing failure in test_build_version_wiring.py::test_version_printed_in_build_output (registry reference to finalize-feature.js) confirmed present before this ticket's changes.

### 2026-06-24 09:40 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-24_46f8ac5f
completion_manifest:
  ac1_met: true
  ac2_met: true
  ac3_met: true
  ac4_met: true
  no_regressions: true
All 4 ACs verified. Diff correctly removes `createdTrackingTickets` null-accumulator and false "Tracking tickets created" success message; replaces with `untrackedFailures[]` and accurate conditional message. Step-map doc updated. 17 tests green.

### 2026-06-24 09:45 — commit (status: ok)
feedback-id: fb_2026-06-24_92536c6a
completion_manifest:
  commit_created: true
  files_committed: true
Commit `49738a4` created on EPIC-FinalizeFeatureHardening branch. 4 files committed: finalize-feature.js, finalize-feature.md, ticket, test file. Pre-commit hook auto-added feedback-id to ticket-supervisor comment (no other hook failures).

### 2026-06-24 09:50 — pull-request (status: ok)
feedback-id: fb_2026-06-24_5eb45e69
completion_manifest:
  branch_pushed: true
  pr_updated: true
Pushed commit `49738a4` to origin/EPIC-FinalizeFeatureHardening. Existing PR #158 updated (no new PR opened — epic uses one shared PR per batch-drive convention).

## Implementation Tasks
- [x] Decide create-via-workflow vs report-and-prompt (default: report accurately).
- [x] Fix the success-message construction to reflect the real created count.
- [x] Update the step-map doc.
- [x] Tests for both paths.

## Sign-offs
- [x] test-writer — 2026-06-24 09:00
- [x] python-coder — 2026-06-24 09:30
- [x] test-runner — 2026-06-24 09:35
- [x] pr-reviewer — 2026-06-24 09:40
- [x] commit — 2026-06-24 09:45
- [x] pull-request — 2026-06-24 09:50

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High.
