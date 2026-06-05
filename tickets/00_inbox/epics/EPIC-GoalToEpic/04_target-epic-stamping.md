---
title: "target_epic stamping — tag included ACs with the generated epic name"
status: in_progress
components:
  - ac-driven-dev
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-GoalToEpic/01_tree-traversal-ticket-generation.md
  - tickets/00_inbox/epics/EPIC-GoalToEpic/02_readiness-gate.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
target_epic: EPIC-GoalToEpic
files_touched:
  - scripts/goal_to_epic.py
  - unit_tests/ac_store/test_target_epic_stamping.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  test-runner: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
ac_coverage: 0/3
source_ac: ACD-1200d
---

# 04: target_epic stamping — tag included ACs with the generated epic name

## Actor / Goal

In order to make it clear which shipping batch each AC belongs to and enable
future scope additions to land in the right place, all AC YAML files in the
included set must be stamped with a `target_epic` field matching the generated
epic folder name — after the epic folder is created, and with conflict detection
for ACs already tagged with a different epic.

## Context

`target_epic` is a metadata field written directly into AC YAML files using a
targeted field update (not a full `yaml.dump` round-trip, per ADR-010 convention).
Stamping only happens after the epic folder creation succeeds — no partial stamps
on failure. ACs excluded by the readiness gate must NOT receive the tag.

## AC References

- Implements ACD-1200d-1 (all in-scope leaf ACs receive `target_epic` matching the epic folder name)
- Implements ACD-1200d-1-i (AC already tagged with a different `target_epic` triggers per-AC conflict warning)
- Implements ACD-1200d-2 (ACs excluded by approval gate do NOT receive `target_epic`)

## Agent Contracts

### python-coder

- [x] AC-1: Given the epic folder `EPIC-ValidateApiInputs` has been successfully created and the included leaf set is [ACD-050a-1, ACD-050a-2-i, ACD-050b-1], all three AC YAML files are updated with `target_epic: EPIC-ValidateApiInputs` using a targeted field write (not full yaml.dump), the value case-exactly matches the folder name, and the operation is idempotent (re-running with the same epic name does not produce duplicate values or malformed YAML). <!-- signed: python-coder -->
- [x] AC-2: Given leaf AC ACD-050a-1 already has `target_epic: EPIC-OldBatch` and it appears in the included set for a new run that would assign `EPIC-ValidateApiInputs`, the system detects the conflict per-AC before overwriting, prompts "ACD-050a-1 already belongs to EPIC-OldBatch. Overwrite with EPIC-ValidateApiInputs? (yes / skip)", updates if "yes", retains original if "skip", and generates the ticket regardless of the tag decision. <!-- signed: python-coder -->
- [x] AC-3: Given the readiness gate (ticket 02) excludes ACD-050a-2-i and ACD-050b-1 from the generation set, those two AC YAML files are never modified during the stamping step and retain no `target_epic` field. <!-- signed: python-coder -->

**Delivers to:** Nothing downstream — this is the last mutating step in the pipeline.

**Depends on ticket 01:** `str` — epic folder name (e.g. `'EPIC-ValidateApiInputs'`) to use as the `target_epic` value. Stamping only begins after the folder is confirmed to exist.

**Depends on ticket 02:** `list[str]` — final included AC IDs (after readiness gate filtering). Only these IDs are stamped.

## Acceptance Criteria

- [ ] AC-1: All included ACs receive `target_epic` via targeted field write after folder creation; idempotent; case-exact match
- [ ] AC-2: Per-AC conflict detection for existing `target_epic`; prompt per-AC; ticket generated regardless of tag decision
- [ ] AC-3: Excluded ACs receive no `target_epic` write during stamping; their YAML files are never touched

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| ACD-1200d-1   | test_target_epic_stamping.py:TestCleanStamp | stamp_target_epic() targeted line-level write; idempotent same-value no-op | |
| ACD-1200d-1-i | test_target_epic_stamping.py:TestConflictDetection | per-AC conflict prompt with yes/skip routing in stamp_target_epic() | |
| ACD-1200d-2   | test_target_epic_stamping.py:TestExclusionGuard | exclusion guard: only IDs in included_ids are scanned/written | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/ac_store/test_target_epic_stamping.py
    covers: [ACD-1200d-1, ACD-1200d-1-i, ACD-1200d-2]
    type: unit
    rationale: >
      Targeted field update logic is pure file-mutation; unit tests cover:
      clean stamp (no existing target_epic), idempotent re-run, conflict
      detection (existing different value), conflict-yes path, conflict-skip
      path, and exclusion guard (excluded AC files not touched).
```

## Implementation Tasks

- [x] Add `stamp_target_epic(included_ids, epic_name, store_root)` to `goal_to_epic.py`:
      - Verify epic folder exists before starting (fail-safe guard)
      - For each AC ID in `included_ids`:
        - Read current YAML from disk
        - If `target_epic` is absent or matches `epic_name`: write `target_epic: <epic_name>` with targeted field update
        - If `target_epic` exists and differs from `epic_name`: emit conflict prompt; route on user answer
      - Never touch AC IDs not in `included_ids`
- [x] Implement targeted field update using a line-level edit approach (e.g. regex
      substitution or ruamel.yaml with round-trip preservation) — not `yaml.dump`
      (prevents comment stripping and field reordering)
- [x] Ensure idempotency: re-stamping with the same value is a no-op (read field,
      compare, skip write if already correct)
- [x] Conflict prompt: "ACD-xxx already belongs to EPIC-OldName. Overwrite with
      EPIC-NewName? (yes / skip)" — per-AC, not batched
- [x] Ticket generation for a conflict AC proceeds regardless of the user's tag
      decision (ticket is created either way)
- [x] Write unit tests for all 3 ACs

## Risk & Safety

- Touches money? No.
- Touches data? Yes — writes `target_epic` field to AC YAML files on disk.
  This is the highest-risk write operation in the ACD-1200 pipeline.
  Mitigations:
  - Targeted field update preserves all other fields, comments, and ordering.
  - Stamping is gated behind epic folder creation success (no partial stamps).
  - Conflict detection prevents silent overwrites of existing `target_epic` values.
  - Idempotency guarantee prevents corruption on re-runs.
- Reversibility? High — `target_epic` field can be manually removed from AC YAML
  to restore the AC to its pre-epic state. The field has no semantic effect outside
  the goal-to-epic pipeline.

## Sign-offs

- [x] test-writer — 2026-06-05 10:30
- [x] python-coder — 2026-06-05 10:35
- [x] test-runner — 2026-06-05 10:40
- [x] pr-reviewer — 2026-06-05 10:42
- [x] commit — 2026-06-05 10:45
- [ ] pull-request

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-06-05 10:30 — test-writer (status: ok)
feedback-id: fb_2026-06-05_bab92d30
completion_manifest:
  test_file_written: true
  tests_are_red: true
  ac_coverage_table_filled: true
  all_three_acs_covered: true
Wrote failing test stubs in unit_tests/ac_store/test_target_epic_stamping.py covering ACD-1200d-1 (TestCleanStamp: 5 tests), ACD-1200d-1-i (TestConflictDetection: 6 tests), and ACD-1200d-2 (TestExclusionGuard: 4 tests), plus edge cases (TestEdgeCases: 2 tests). Tests are red with ImportError: cannot import name 'stamp_target_epic' from 'goal_to_epic'. python-coder must implement stamp_target_epic() to make them green.

red_baseline:
  - test_name: test_ac1_stamps_all_included_acs
    file: unit_tests/ac_store/test_target_epic_stamping.py
    error: "ImportError: cannot import name 'stamp_target_epic' from 'goal_to_epic'"
  - test_name: test_ac2_conflict_detected_per_ac
    file: unit_tests/ac_store/test_target_epic_stamping.py
    error: "ImportError: cannot import name 'stamp_target_epic' from 'goal_to_epic'"
  - test_name: test_ac3_excluded_acs_not_touched
    file: unit_tests/ac_store/test_target_epic_stamping.py
    error: "ImportError: cannot import name 'stamp_target_epic' from 'goal_to_epic'"

### 2026-06-05 10:35 — python-coder (status: ok)
feedback-id: fb_2026-06-05_ec2ea3e1
completion_manifest:
  stamp_target_epic_implemented: true
  targeted_field_write_not_yaml_dump: true
  idempotency_verified: true
  conflict_detection_per_ac: true
  exclusion_guard_verified: true
  all_tests_green: true
  ruff_clean: true
Implemented stamp_target_epic(included_ids, epic_name, store_root) in scripts/goal_to_epic.py with helper functions _find_ac_yaml_path(), _read_target_epic_from_file(), and _write_target_epic_field(). Targeted field write uses regex-based line replacement (not yaml.dump) to preserve comments and field ordering. All 17 new tests pass; full ac_store suite 71/71 green. Ruff clean. DECISION HISTORY entry added per convention.

### 2026-06-05 10:40 — test-runner (status: ok)
feedback-id: fb_2026-06-05_69fe5d02
completion_manifest:
  new_tests_green: true
  full_suite_no_regression: true
  test_count_correct: true
Ran unit_tests/ac_store/ suite: 71 passed, 0 failed (17 new target_epic tests + 54 existing). No regressions introduced by the implementation. python3 -m pytest unit_tests/ac_store/ -v confirmed all green.

### 2026-06-05 10:42 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_e3596e46
completion_manifest:
  implementation_correct: true
  all_acs_covered: true
  error_handling_correct: true
  targeted_field_write_verified: true
  idempotency_verified: true
  ruff_clean: true
  no_regressions: true
Code review passed. stamp_target_epic() correctly implements targeted line-level field update (not yaml.dump), idempotency guard, per-AC conflict prompt with yes/skip routing, and exclusion guard (only included_ids touched). Error handling follows project conventions. 71/71 tests green. No architectural concerns.

### 2026-06-05 10:45 — commit (status: ok)
feedback-id: fb_2026-06-05_f12acdcc
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committing 3 in-scope files: scripts/goal_to_epic.py (stamp_target_epic + helpers, +174 lines), unit_tests/ac_store/test_target_epic_stamping.py (17 unit tests), and tickets/00_inbox/epics/EPIC-GoalToEpic/04_target-epic-stamping.md (all agents signed off).
