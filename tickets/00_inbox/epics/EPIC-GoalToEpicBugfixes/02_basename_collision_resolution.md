---
title: "A ticket whose basename already exists at the epic-folder path is resolved deterministically, never duplicated to a second location"
status: done
source_ac: ACD-1200a-9-i
components:
  - ac-driven-dev
created: 2026-06-22
depends_on:
  - 01_single_location_write_and_backref.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/goal_to_epic.py
agents:
  python-coder: signed_off
  test-writer: signed_off
  test-runner: signed_off
  sql-coder: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# A ticket whose basename already exists at the epic-folder path is resolved deterministically, never duplicated to a second location

## Actor / Goal

As the leafcutter-ai system, I want a ticket whose computed basename already
exists at the epic-folder path resolved deterministically — by overwriting the
existing epic-folder file in place — so that re-runs converge on exactly one
ticket file per leaf AC and never mint a renamed sibling or a second copy
elsewhere.

## Context

This ticket implements AC store entry `ACD-1200a-9-i` (component
`ac-driven-dev`, assigned `python-coder`, complexity S). It is the edge-case
companion to `ACD-1200a-9`: given the single-location write contract, this
pins down what happens on a basename collision inside the epic folder.

Part of EPIC-GoalToEpicBugfixes. Depends on
`01_single_location_write_and_backref.md` (ACD-1200a-9), which establishes the
single-location write contract this edge case refines.

## AC References

- Implements ACD-1200a-9-i (deterministic in-place collision resolution)
- Depends on ACD-1200a-9 (single-location epic-folder write contract)

## Acceptance Criteria

```gherkin
Given the epic folder tickets/00_inbox/epics/EPIC-ValidateApiInputs/ already
  contains a file named 01_validate-input-schema.md from a prior run,
And the system is generating a ticket for a leaf AC whose computed filename is
  also 01_validate-input-schema.md,
When the system writes that ticket,
Then it resolves the collision deterministically by writing to the existing
  epic-folder path (overwriting it in place) and reports that the existing
  file was replaced,
And it does not create a second ticket file at any other location for that
  leaf AC (neither a renamed sibling inside the epic folder nor a copy at the
  tickets inbox root),
And after the run exactly one ticket file with that basename exists for that
  leaf AC, at the epic-folder path,
And the leaf AC's implemented_by back-reference names that single
  epic-folder path.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACD-1200a-9-i | `test_goal_to_epic_basename_collision.py` — 5 tests all green (in-place overwrite, no second copy, single file, warning emitted, correct `implemented_by`) | `assemble_epic_folder()` overwrites colliding files in place with `exist_ok=True` mkdir + `shutil.copy2`; WARNING logged per overwrite; `EpicFolderConflictError` no longer raised for folder-level conflicts | ok — 2026-06-22 |

## Comments

### 2026-06-22 00:00 — ticket-supervisor (status: ok)
feedback-id: (pre-epoch)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-22 14:30 — python-coder (status: ok)
feedback-id: fb_2026-06-22_cea10d5b
completion_manifest:
  in_place_overwrite_implemented: true
  warning_log_emitted: true
  single_file_invariant_enforced: true
  io_wrapped_per_error_handling_policy: true
  tests_written_and_green: true
  files_touched_match_plan: true
Implemented ACD-1200a-9-i in `assemble_epic_folder()`: changed from raising `EpicFolderConflictError` on folder existence to using `exist_ok=True` mkdir, detecting destination file existence before each `shutil.copy2`, and emitting a WARNING log when a file is overwritten in place. The `run()` exception handler was updated to catch `OSError` instead of `EpicFolderConflictError`. Five tests written in `tests/test_goal_to_epic_basename_collision.py` covering all four required scenarios (in-place overwrite, no second copy, single resulting file, correct `implemented_by`) — all green.

### 2026-06-22 15:00 — test-runner (status: ok)
feedback-id: fb_2026-06-22_2dc597ef
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
5/5 new tests in `test_goal_to_epic_basename_collision.py` pass. Pre-existing failure in `test_goal_to_epic_worktree_skip.py` (BP-901) confirmed as not a regression from this ticket’s changes (it predates this commit, targets a separate AC, and the diff for this ticket does not touch the relevant `main()` code path).

### 2026-06-22 15:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-22_f11aa6d7
completion_manifest:
  in_place_overwrite_verified: true
  warning_observable_confirmed: true
  oserror_wrapping_compliant: true
  implemented_by_backref_correct: true
  test_coverage_adequate: true
  no_regressions_detected: true
Reviewed 3-file diff (494 ins, 27 del): assemble_epic_folder() correctly overwrites colliding basenames in place using exist_ok=True mkdir + shutil.copy2, emits a WARNING before each overwrite, and wraps both I/O operations in specific OSError handlers that log and re-raise — fully compliant with the project error-handling policy. All 5 new tests map to the 4 Gherkin AC scenarios. No high-confidence issues found; EpicFolderConflictError class is now dead code but not a blocker. AC Coverage Validated column filled: ok — 2026-06-22.

### 2026-06-22 16:00 — commit (status: ok)
Auto-authorized commit gate: subject "feat(goal_to_epic): resolve basename collision in-place (ACD-1200a-9-i)"; staged files: scripts/goal_to_epic.py tests/test_goal_to_epic_basename_collision.py tickets/00_inbox/epics/EPIC-GoalToEpicBugfixes/02_basename_collision_resolution.md.
feedback-id: fb_2026-06-22_b77c199e
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committed 3 staged files (507 insertions, 29 deletions): in-place collision resolution in scripts/goal_to_epic.py, 5 new tests in tests/test_goal_to_epic_basename_collision.py, and ticket sign-off. Batch-drive auto-authorized per COMMIT_AGENT_MODE=1.

### 2026-06-22 17:00 — pull-request (status: ok)
feedback-id: fb_2026-06-22_a7533bf8
completion_manifest:
  branch_pushed: true
  pr_created: true
  pr_body_complete: true
Pushed commit cef89d7 (feat(goal_to_epic): resolve basename collision in-place ACD-1200a-9-i) to origin/EPIC-GoalToEpicBugfixes. PR #127 at https://github.com/urlmonitor/leafcutter-ai/pull/127 is already open and now includes this commit. Ticket status flipped to done — all agents signed_off or not_needed.

## Sign-offs

- [x] python-coder — 2026-06-22 14:30
- [x] test-writer — 2026-06-22 00:00
- [x] test-runner — 2026-06-22 15:00
- [x] pr-reviewer — 2026-06-22 15:30
- [x] commit — 2026-06-22 16:00
- [x] pull-request — 2026-06-22 17:00

## Implementation Tasks

- [x] On a basename collision inside the epic folder, overwrite the existing epic-folder path in place rather than minting a renamed sibling or a second copy elsewhere.
- [x] Emit a report/log line at an appropriate severity stating the existing file was replaced, so the overwrite is observable and not silent.
- [x] Ensure after the run exactly one ticket file with that basename exists (at the epic-folder path) and the AC's `implemented_by` names that single path, consistent with ACD-1200a-9. Wrap overwrite I/O per the project error-handling policy.
- [x] Tests for: in-place overwrite on collision, no second-location copy, single resulting file, correct `implemented_by`.

## Risk & Safety

- Touches money? No.
- Touches data? Yes — overwrites a ticket file in place and updates `implemented_by`; targeted updates only.
- Reversibility? High — behavior-only change to a generator script.
