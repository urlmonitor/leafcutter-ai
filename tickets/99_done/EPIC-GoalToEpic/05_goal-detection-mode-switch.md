---
title: "Goal detection and mode switch — /build-ac auto-routes leaf vs goal"
status: done
components:
  - ac_driven_dev
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-GoalToEpic/01_tree-traversal-ticket-generation.md
  - tickets/00_inbox/epics/EPIC-GoalToEpic/02_readiness-gate.md
  - tickets/00_inbox/epics/EPIC-GoalToEpic/03_dependency-wiring.md
  - tickets/00_inbox/epics/EPIC-GoalToEpic/04_target-epic-stamping.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
target_epic: EPIC-GoalToEpic
files_touched:
  - templates/agents/build-ac.md
  - templates/skills/build-ac/SKILL.md
  - unit_tests/agents/test_build_ac_mode_detection.py
  - scripts/build_ac_mode_detection.py
  - unit_tests/agents/conftest.py
agents:
  test-writer: signed_off
  llm-expert: signed_off
  test-runner: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
ac_coverage: 3/3
source_ac: ACD-1200e
---

# 05: Goal detection and mode switch — /build-ac auto-routes leaf vs goal

## Actor / Goal

In order to keep a single mental model ("build-ac means build from the AC store"),
the `/build-ac` command must detect whether the target AC is a leaf or a goal and
route to the appropriate mode without requiring the user to know the distinction
or pass a separate flag.

## Context

This ticket wires together all sub-features from tickets 01–04 into the existing
`build-ac` agent template. The detection logic reads `level` and `covered_by`
from the target AC YAML: a leaf has an empty or absent `covered_by`; a goal has
non-empty `covered_by`. An L1 with empty `covered_by` is a special edge case —
it is not a leaf (single-ticket path) nor a viable goal (no leaves to collect);
it requires its own error path.

## AC References

- Implements ACD-1200e-1 (leaf AC → single-ticket path unchanged; no regression)
- Implements ACD-1200e-2 (L0 or L1 with children → epic-generation mode; user sees mode message)
- Implements ACD-1200e-2-i (L1 with no children → error + decompose suggestion; no ticket, no epic)

## Agent Contracts

### llm-expert

- [x] AC-1: Given `/build-ac --ac <leaf-id>` where the target AC has `covered_by: []` or absent, the agent follows the existing single-ticket path (propose AC, confirm, generate one ticket, hand off to /build-feature), does NOT invoke epic-generation mode, does NOT create an EPIC- folder, and does NOT display a readiness report or approval gate — identical behavior to the pre-ACD-1200 build-ac agent. <!-- signed: llm-expert -->
- [x] AC-2: Given `/build-ac --ac ACD-050` where ACD-050 has `level: L0` and non-empty `covered_by`, the agent detects the goal-level AC, prints "ACD-050 is a goal — generating epic from all leaf ACs beneath it.", then invokes the epic-generation flow (tree traversal → readiness gate → dependency wiring → ticket generation → target_epic stamping → folder assembly). Given `/build-ac --ac ACD-050a` where ACD-050a has `level: L1` and non-empty `covered_by`, the agent also switches to epic-generation mode scoped to the ACD-050a subtree only. <!-- signed: llm-expert -->
- [x] AC-3: Given `/build-ac --ac ACD-070a` where ACD-070a has `level: L1` but `covered_by: []`, the agent detects the L1-with-no-children condition, prints "ACD-070a is an L1 with no leaf ACs beneath it. Decompose into L2/L3 first, or use /ba to generate behavioral specifications.", creates no ticket and no epic folder, and exits cleanly. <!-- signed: llm-expert -->

**Delivers to:** User (terminal output) — the completed epic folder path or single-ticket path, per routing decision.

**Depends on tickets 01–04:** the epic-generation flow that this ticket wires into the agent template.

## Acceptance Criteria

- [ ] AC-1: Leaf AC → single-ticket path unchanged; no EPIC folder; no readiness report; backward compatible with ACD-700a behavior
- [ ] AC-2: L0/L1 with children → mode switch message printed; full epic-generation flow invoked; L1-scoped when L1 is targeted
- [ ] AC-3: L1 with no children → clear error with decompose suggestion; no ticket; no folder; clean exit

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| ACD-1200e-1   | test_build_ac_mode_detection.py:test_ac1_leaf_l2_empty_covered_by_returns_leaf_mode | build-ac.md Step 2a Case A: leaf route, no mode message, proceeds to single-ticket path | ok — 2026-06-06 |
| ACD-1200e-2   | test_build_ac_mode_detection.py:test_ac2_l0_with_children_returns_goal_mode | build-ac.md Step 2a Case B: goal route, mode message printed, invokes goal_to_epic.py | ok — 2026-06-06 |
| ACD-1200e-2-i | test_build_ac_mode_detection.py:test_ac3_l1_no_children_returns_l1_no_children_mode | build-ac.md Step 2a Case C: error message printed, exits cleanly with no writes | ok — 2026-06-06 |

## Test Requirements

```yaml
tests:
  - path: unit_tests/agents/test_build_ac_mode_detection.py
    covers: [ACD-1200e-1, ACD-1200e-2, ACD-1200e-2-i]
    type: unit
    rationale: >
      Mode detection is a pure branch on level + covered_by; unit tests cover:
      leaf AC (L2, covered_by empty), L0 goal with children, L1 goal with
      children (scoped), L1 with no children (error path). Mocks the epic-
      generation flow to isolate mode detection from the pipeline.
```

## Implementation Tasks

- [x] Extend `build-ac.md` Step 2 (Generate a Ticket from the AC):
      - Before generating: read `level` and `covered_by` from the target AC YAML
      - Add detection branch:
        - `covered_by` empty or absent AND level is L2/L3 (or any level with no children): leaf path (current behavior, unchanged)
        - `covered_by` non-empty AND level is L0 or L1: goal path → print mode message → invoke `goal_to_epic.py --ac <id>`
        - `covered_by` empty AND level is L1: L1-no-children error path → print error + decompose suggestion → exit
- [x] Add mode-switch message to goal path: "ACD-<id> is a goal — generating epic from all leaf ACs beneath it."
- [x] Add L1-no-children error: "ACD-<id> is an L1 with no leaf ACs beneath it. Decompose into L2/L3 first, or use /ba to generate behavioral specifications."
- [x] Update `.claude/skills/build-ac/SKILL.md` to document the three routing modes
- [x] Verify that `--dry-run` flag (existing) propagates correctly through both the
      leaf path and the goal path (dry-run in goal mode prints the proposed leaf set
      without writing any files)
- [x] Write unit tests for all 3 ACs

## Risk & Safety

- Touches money? No.
- Touches data? No — this ticket modifies agent template markdown and skill docs only.
  The actual file writes happen in tickets 01 and 04; this ticket wires the control
  flow.
- Reversibility? High — agent template and skill doc are text files; reverting to the
  pre-ACD-1200 version restores the original behavior.
- Regression surface: the leaf path (AC-1) must be behaviorally identical to the
  pre-ACD-1200 `build-ac` agent. The unit test for AC-1 must cover the exact same
  input/output contract as the existing ACD-700a behavior.

## Sign-offs

- [x] test-writer — 2026-06-05 12:00
- [x] llm-expert — 2026-06-06 09:00
- [x] test-runner — 2026-06-06 09:30
- [x] pr-reviewer — 2026-06-06 09:45
- [x] commit — 2026-06-06 10:00
- [x] pull-request — 2026-06-06 10:15

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-06-05 12:00 — test-writer (status: ok)
feedback-id: fb_2026-06-05_6d4d29f2
completion_manifest:
  tests_written: true
  tests_are_red: true
  ac_coverage_table_filled: true
red_baseline:
  - test_name: test_ac1_leaf_l2_empty_covered_by_returns_leaf_mode
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac1_leaf_l3_absent_covered_by_returns_leaf_mode
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac1_leaf_mode_has_no_user_message
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac1_leaf_does_not_invoke_goal_to_epic
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac2_l0_with_children_returns_goal_mode
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac2_l1_with_children_returns_goal_mode
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac2_goal_mode_emits_correct_message
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac2_goal_mode_sets_invoke_flag
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac2_goal_mode_does_not_follow_single_ticket_path
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac3_l1_no_children_returns_l1_no_children_mode
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac3_l1_no_children_emits_correct_message
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac3_l1_no_children_does_not_invoke_goal_to_epic
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac3_l1_no_children_does_not_follow_single_ticket_path
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_ac3_l1_no_children_none_covered_by_also_errors
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_l0_empty_covered_by_is_not_valid_goal
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
  - test_name: test_l2_with_covered_by_falls_back_to_leaf_mode
    file: unit_tests/agents/test_build_ac_mode_detection.py
    error: "AssertionError: ImportError: cannot import detect_ac_mode from scripts.build_ac_mode_detection — implementation not yet written."
16 failing test stubs written for all 3 ACs (ACD-1200e-1, ACD-1200e-2, ACD-1200e-2-i). All tests red on AssertionError/ImportError — implementation not yet written. Handoff to llm-expert.

### 2026-06-06 10:15 — pull-request (status: ok)
feedback-id: fb_2026-06-05_6b4388ee
completion_manifest:
  branch_pushed: true
  pr_exists: true
  no_new_pr_created: true
Pushed commit 249ec59 to origin/EPIC-GoalToEpic. Existing PR #69 updated (6cf51a5..249ec59). No new PR created — PR already open per epic convention.

### 2026-06-06 10:00 — commit (status: ok)
feedback-id: fb_2026-06-05_3547141a
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
SHA 249ec59 on branch EPIC-GoalToEpic. 7 files committed (967 insertions). Pre-commit hooks passed; no autofix needed.

### 2026-06-06 09:45 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_63919d40
completion_manifest:
  contract_validation_passed: true
  ac_coverage_table_filled: true
  no_high_confidence_findings: true
Reviewed staged diff for 5 files. Pure detection function has no I/O, no side-effects. All 3 AC contracts match implementation (exact message strings, correct mode routing, no false positives on leaf path). AC Coverage Validated column filled with ok dates for all 3 ACs.

### 2026-06-06 09:30 — test-runner (status: ok)
feedback-id: fb_2026-06-05_14ee182c
completion_manifest:
  tests_green: true
  all_acs_covered: true
16/16 tests pass for unit_tests/agents/test_build_ac_mode_detection.py. All three ACs (ACD-1200e-1, ACD-1200e-2, ACD-1200e-2-i) are covered by green tests. No regressions detected.

### 2026-06-06 09:00 — llm-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true
Extended `templates/agents/build-ac.md` Step 2 with three-way mode detection branch (Step 2a: leaf/goal/l1_no_children cases). Created `scripts/build_ac_mode_detection.py` (pure detection helper, 16/16 tests now green). Created `.claude/skills/build-ac/SKILL.md` documenting all three routing modes, detection algorithm, output contracts, dry-run propagation, and test coverage map. Created `unit_tests/agents/conftest.py` to add repo root to sys.path for package-qualified imports. All acceptance criteria implemented.
