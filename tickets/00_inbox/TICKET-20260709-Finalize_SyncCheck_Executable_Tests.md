---
title: "Make the finalize push-before-merge sync-check decision logic executable/unit-testable (H-4 follow-up)"
status: todo
components:
  - build_pipeline
created: 2026-07-09
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: internal
requires_diagram: false
requires_adr: false
tags:
  - finalize-feature
  - test-coverage
  - phantom-green
files_touched:
  - templates/workflows-js/finalize-feature.js
  - unit_tests/workflows/test_finalize_feature_push_before_merge.py
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

# Make the finalize push-before-merge sync-check decision logic executable/unit-testable (H-4 follow-up)

## Actor / Goal
In order to guarantee that the finalize push-before-merge guard actually behaves
fail-closed (not merely *contains the right strings*), we need the sync-check
status→action decision to be exercised by an executing test — so that an inverted
comparison or a mis-ordered branch is caught by the suite instead of shipping green.

## Context
Follow-up to TICKET-20260708-Finalize_Push_Before_Merge (merged via PR #246), which
added a fail-closed "Pre-Step-4 Sync Check" to `templates/workflows-js/finalize-feature.js`
that pushes/ verifies the local branch head before `gh pr merge`.

During the review of that fix (finding **H-4**), the code-review agent confirmed the guard
is currently fail-closed and correct, but flagged a residual risk: the 22 tests in
`unit_tests/workflows/test_finalize_feature_push_before_merge.py` are **100% source-string
assertions** — they grep the `.js` source for halt reasons, the `KNOWN_SYNC_STATUSES` gate,
SHA-comparison tokens, and the absence of `fail-open`. They **never execute the branching
logic**. Concretely, an inverted comparison (`if (localSha === originSha)` in the mismatch
branch) or a re-ordered `else if` would still pass every test.

This is exactly the phantom-green / "green sign-offs prove the code runs, not that it works"
failure mode this repo has been repeatedly burned by (see EPIC-PhantomDoneFilesTouched
retrospective; the real-artifact behavioral spot-check convention in CLAUDE.md). The root
cause is that the workflow `.js` is run by the custom Workflow engine and is not executable
under pytest, so the decision logic has no runtime test harness.

## Acceptance Criteria
- [ ] AC-1: The sync-check status→action decision (given a parsed status-checker result,
  return one of: proceed | halt(reason)) is exercised by an EXECUTING test — not a
  source-string grep. For each terminal state the current guard handles
  (malformed/null, unknown-status, fetch_failed, push_failed, diverged, pushed+SHA-match,
  pushed+SHA-mismatch, up_to_date+SHA-match, up_to_date+SHA-mismatch) the test asserts the
  correct proceed-vs-halt outcome and, on halt, the correct `reason`.
- [ ] AC-2: The safety invariant is behaviorally proven: a test feeds an "ahead / SHA
  mismatch / malformed / unknown / fetch_failed / diverged" result and asserts the decision
  is HALT (never proceed). Inverting any single comparison in the decision logic must turn
  at least one test RED.
- [ ] AC-3: No regression to the existing fail-closed behavior on `finalize-feature.js` —
  the full-flow HALT return shapes (keys: status, halted_at_step, reason, branch, pr_number,
  pr_url, completed_steps, skipped_steps, action_required) are preserved.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Decide the harness approach (Open Question below) and record it in the ticket before
  coding: extract the pure status→action mapping into an importable/executable unit, or add
  a small Node-based smoke test that drives the decision with stubbed status-checker output.
- [ ] Extract the sync-check decision (status + local_sha/origin_sha → {action, reason})
  into a pure, side-effect-free function in the workflow JS so it can be invoked in
  isolation without the Workflow engine, agents, or git.
- [ ] Add executing tests covering every terminal state (see AC-1) and the fail-closed
  invariant (AC-2), including a mutation sanity check (inverting a comparison flips a test
  RED).
- [ ] Keep (or fold into) the existing source-assertion tests as a cheap secondary guard;
  the executing tests are the primary evidence.

## Open Questions
- Which test runner? The workflow `.js` is not executable under pytest (per
  docs/reference/workflow-constraints.md). Options: (a) extract the decision into a tiny
  pure-JS module and add a Node test runner to CI; (b) a self-contained Node smoke script
  invoked from a pytest wrapper via subprocess; (c) port the decision to a Python-mirrored
  pure function tested directly. Pick the lowest-friction option that actually executes the
  branching. Resolve before implementation.

## Risk & Safety
- Touches money? No.
- Touches data? No — test/refactor only; hardens the guard that prevents committed-work loss.
- Reversibility? Fully reversible; extracts a pure function and adds tests.
