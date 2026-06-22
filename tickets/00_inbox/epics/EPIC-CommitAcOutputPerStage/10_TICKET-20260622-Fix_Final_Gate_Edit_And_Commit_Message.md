---
advances_current_outcome: true
agents:
  commit: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  pull-request: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  test-writer: signed_off
components:
- ac-driven-dev
created: '2026-06-22'
depends_on:
- 05_TICKET-20260618-ACD-300g-3.md
- 06_TICKET-20260618-ACD-300g-4.md
files_touched:
- scripts/workflows/plan-feature.js
- templates/workflows-js/plan-feature.js
priority: medium
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
source_ac: ACD-300g-4
status: done
title: 'Fix final-gate edit-fallthrough, add run id to commit message, dedupe stage labels'
---

# Fix final-gate edit-fallthrough, add run id to commit message, dedupe stage labels

## Actor / Goal

As the /plan-feature workflow, I want the final gate to never auto-approve an
unreviewed stage, and the commit message to carry a run id and a canonical stage
label, so that ACD-300g-4 (no commit without approval) and ACD-300g-3 (message
identifies run + stage + AC IDs) are fully satisfied.

## Context

Post-build angle-testing (2026-06-22) found:

1. **MEDIUM — final-gate edit-after-exhaustion auto-commits (violates ACD-300g-4).**
   In `run()`, the final-gate branch `else if (finalAction === "approve" || finalAction === "edit")`
   means a user who requests `edit` a second time (retries exhausted) falls through
   to the APPROVE branch: it sets `readiness: approved` + default priority and commits
   unreviewed ACs against the user's wishes. The non-final gate handles this correctly
   (explicit abort at retries-exhausted); the final gate's `|| "edit"` swallows it.
   Fix: drop `|| finalAction === "edit"` from the approve condition and add an explicit
   exhausted-retries abort branch (no commit) mirroring the non-final gate.

2. **MEDIUM — no run id in commit message (ACD-300g-3 under-met).** The spec asks for
   "run id + stage + AC IDs"; the message has stage + AC IDs but no run identifier.
   Two sequential /plan-feature runs produce indistinguishable commit subjects. Fix:
   generate a short run id at the top of `run()` and include it.

3. **LOW — stale + non-canonical labels.** Commit subject still uses the retired
   `create-ac(...)` prefix (command renamed to plan-feature); `isFinal=true` hardcodes
   the literal `"final"` stage label, bypassing `stageDisplayName` so the IT-PO identity
   is lost from the final commit subject. Fix: use the current command name and a
   documented/canonical label set (e.g. `IT-PO, final`).

4. **LOW — infinite-loop risk.** The final-gate branch chain has no terminal `else`;
   an unrecognized `finalAction` leaves `approved` false and re-dispatches the gate
   forever. Add a terminal else that aborts (no commit).

## AC References

- Hardens ACD-300g-4 (no commit without approval) and ACD-300g-3 (commit message content).

## Acceptance Criteria

```gherkin
Scenario: repeated edit at the final gate does not auto-approve
  Given the user requests "edit" at the final gate after retries are exhausted
  When run() evaluates the final-gate action
  Then the workflow aborts WITHOUT setting readiness: approved and WITHOUT committing
  And the draft ACs remain on disk uncommitted.

Scenario: commit message identifies run, stage, and AC IDs
  Given a stage is committed
  Then the commit message contains a run identifier, the canonical stage label, and the AC IDs
  And the subject uses the current command name (not the retired create-ac prefix)
  And the final stage's label preserves the IT-PO identity (not a bare "final").

Scenario: unrecognized final-gate action aborts instead of looping
  Given the final-gate decision is an unrecognized value
  Then run() aborts cleanly (no commit, no infinite re-dispatch).
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| edit no auto-approve | test_exhausted_edit_at_final_gate_* (3 tests, RED) | | |
| run id + canonical label | test_commit_message_* (4 tests, 3 RED 1 GREEN) | | |
| unrecognized action aborts | test_unrecognized_final_action_* (3 tests, 2 RED 1 GREEN) | | |

## Sign-offs

- [x] test-writer — 2026-06-22 13:45
- [x] python-coder — 2026-06-22 14:00
- [x] test-runner — 2026-06-22 14:15
- [x] pr-reviewer — 2026-06-22 14:30
- [x] commit — 2026-06-22 15:00
- [x] pull-request — 2026-06-22 15:15

## Comments

### 2026-06-22 14:15 — test-runner (status: ok)

feedback-id: (submit-failed)
test_suite: unit_tests/test_final_gate_and_commit_message.py
command: python -m pytest unit_tests/test_final_gate_and_commit_message.py -v
result: 11 passed, 0 failed
breakdown:
  previously_red_now_green: 8
  always_green: 3
  total: 11

All 11 tests pass. The 8 tests that were RED (edit-fallthrough abort, run-id in commit
message, retired-prefix removal, IT-PO label preservation, unrecognized-action abort,
unrecognized-action error status) are now GREEN. The 3 originally GREEN regression guards
(AC IDs in commit message, no-commit on unrecognized action, scripts/templates parity)
remain GREEN.

### 2026-06-22 14:00 — python-coder (status: ok)

feedback-id: fb_2026-06-22_b71d7579
completion_manifest:
  final_gate_edit_fallthrough_fixed: true
  run_id_added_to_commit_message: true
  retired_create_ac_prefix_replaced: true
  terminal_else_added_to_final_gate: true
  parity_applied_to_templates: true
  all_11_tests_green: true

Fixed all four defects in both `scripts/workflows/plan-feature.js` and `templates/workflows-js/plan-feature.js` (byte-identical parity). Changes: (1) dropped `|| finalAction === "edit"` from the approve condition and added an explicit exhausted-retries abort branch; (2) generated a short 8-char hex `runId` at the top of `run()` and threaded it through both `commitStageOutput()` call sites; (3) replaced the retired `create-ac(` subject prefix with `plan-feature(` and routed the final-stage label through `stageDisplayName()` (e.g. `IT-PO, final`); (4) added a terminal `else` that returns `status: error` for unrecognized `finalAction` values. All 11 tests now pass (8 previously RED, 3 previously GREEN all remain GREEN).

### 2026-06-22 14:30 — pr-reviewer (status: ok)

feedback-id: fb_2026-06-22_5c375495
completion_manifest:
  ac1_edit_fallthrough_fixed: true
  ac2_run_id_in_commit_message: true
  ac3_unrecognized_action_aborts: true
  plan_feature_prefix_correct: true
  itpo_label_preserved_in_final_commit: true
  template_parity_verified: true
  all_11_tests_green: true

All three ACs verified against the implementation. (1) The `|| finalAction === "edit"` fallthrough is gone — exhausted-edit at the final gate hits the explicit abort branch (lines 645–655) and returns `status: error` without committing. (2) `runId` is generated at line 389 as an 8-char hex string, threaded through both `commitStageOutput()` call sites, and appears as `run-id: <runId>` in the commit message body. (3) The terminal `else` at line 698 aborts on any unrecognized `finalAction` with `status: error` and no commit. The `create-ac(` prefix is replaced with `plan-feature(` and the final stage label routes through `stageDisplayName()` yielding `IT-PO, final`. `scripts/` and `templates/` are byte-identical (diff empty). All 11 tests pass per test-runner sign-off.

### 2026-06-22 15:00 — commit (status: ok)

feedback-id: fb_2026-06-22_b4e1b373
completion_manifest:
  files_staged_correctly: true
  commit_executed_cleanly: true
  ticket_signed_off: true

All 4 files were already staged from prior agents (scripts/workflows/plan-feature.js, templates/workflows-js/plan-feature.js, unit_tests/test_final_gate_and_commit_message.py, ticket file). Committed with the prescribed message referencing ticket 10 and EPIC-CommitAcOutputPerStage. Frontmatter set to commit: signed_off; Sign-offs checkbox checked.

### 2026-06-22 15:15 — pull-request (status: ok)

feedback-id: fb_2026-06-22_dc66d63b
completion_manifest:
  branch_ahead_of_origin_confirmed: true
  push_to_existing_pr_succeeded: true
  pr_114_verified_open: true

Pushed 1 commit (50695d2) to existing PR #114 (EPIC-CommitAcOutputPerStage → main). PR title: "feat(plan-feature): commit approved AC stage output before next dispatch (ACD-300g-1)". No new PR was opened.

### 2026-06-22 13:45 — test-writer (status: ok)

feedback-id: fb_2026-06-22_80d7ddd7
completion_manifest:
  tests_written: true
  red_baseline_confirmed: true
  behavioral_replay_pattern_followed: true
  mock_sentinel_correctness_verified: true

Wrote `unit_tests/test_final_gate_and_commit_message.py` — 11 behavioral vm.Script tests
covering all four defects in ticket 10. Discovered and fixed a mock-detection ambiguity:
the final gate instruction text contains "readiness: approved" as UX prose, so the
approval-update sentinel was changed to "update their YAML files" to avoid false detection.

red_baseline:
  suite: unit_tests/test_final_gate_and_commit_message.py
  command: python -m pytest unit_tests/test_final_gate_and_commit_message.py -v
  result: 8 failed, 3 passed
  failing_tests:
    - TestFinalGateEditFallthrough::test_exhausted_edit_at_final_gate_returns_error_status
        reason: run() returns status=ok (approve/commit) instead of error (abort)
    - TestFinalGateEditFallthrough::test_exhausted_edit_at_final_gate_does_not_commit_final_stage
        reason: 1 commit captured — the || finalAction=edit fallthrough commits unreviewed ACs
    - TestFinalGateEditFallthrough::test_exhausted_edit_at_final_gate_has_no_acs_approved
        reason: acs_approved key present — approve branch ran without user consent
    - TestCommitMessageShape::test_commit_message_contains_run_id
        reason: no run-id token found in extracted commit message text
    - TestCommitMessageShape::test_commit_message_does_not_use_retired_create_ac_prefix
        reason: create-ac( found in commit message (retired prefix)
    - TestCommitMessageShape::test_final_stage_commit_message_preserves_itpo_label
        reason: IT-PO absent from final commit message (hardcoded literal final)
    - TestFinalGateTerminalElse::test_unrecognized_final_action_causes_loop_redispatch
        reason: 4 final-gate dispatches for single unrecognized action (no terminal else)
    - TestFinalGateTerminalElse::test_unrecognized_final_action_returns_error_status
        reason: run() returns status=ok via defer safety valve instead of status=error
  passing_tests:
    - TestCommitMessageShape::test_commit_message_contains_ac_ids (GREEN — AC IDs already included)
    - TestFinalGateTerminalElse::test_unrecognized_final_action_does_not_commit (GREEN — regression guard)
    - TestRunFunctionParityWithTemplate::test_scripts_and_templates_run_function_are_in_parity (GREEN — files in sync)

## Implementation Tasks
- [x] Remove `|| finalAction === "edit"` from the final-gate approve condition; add explicit exhausted-retries abort (no commit).
- [x] Generate a run id in run() and thread it into the commit message.
- [x] Replace the `create-ac(...)` subject prefix with the current command name; route the final-stage label through a canonical label set.
- [x] Add a terminal else to the final-gate chain that aborts on unrecognized actions.
- [x] Apply identical changes to templates/workflows-js/plan-feature.js (parity).
- [x] Tests for the edit-fallthrough abort and commit-message shape.

## Risk & Safety
- Touches money? No.
- Touches data? Affects approval/commit gating in the AC-authoring workflow; no destructive ops.
- Reversibility? Fully reversible.
