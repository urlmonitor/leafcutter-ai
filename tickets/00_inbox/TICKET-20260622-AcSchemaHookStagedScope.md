---
title: "Scope check-ac-schema hook to staged files instead of the whole store"
status: in_progress
components:
  - guardrail-engine
created: 2026-06-22
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/scripts/commit_guardian/check_ac_schema.py
  - unit_tests/commit_guardian/test_check_ac_schema.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Scope check-ac-schema hook to staged files instead of the whole store

## Actor / Goal

In order to keep the `check-ac-schema` pre-commit hook fast and relevant to the
commit at hand, the hook should validate only the AC YAML files that are actually
staged for the commit — not all files in the AC store on every commit — so that a
commit is never blocked or slowed by a pre-existing violation in an unrelated,
unstaged file.

## Context

### Background

This is **Bug 2** of the `check-ac-schema` regression diagnosed on 2026-06-22.
Bug 1 (the strict `validate_manually()` running on the jsonschema success path)
was fixed in PR #141 (AC GE-112, merge commit 120036d). This ticket tracks the
second, independent defect.

In `templates/scripts/commit_guardian/check_ac_schema.py`, `main()` calls
`_find_ac_files(root)` which does `sorted(ac_dir.rglob("*.yaml"))` — it validates
the **entire** AC store on every commit, regardless of what is staged. Combined
with `pass_filenames: false` in the hook registration, this means:

- Every commit pays the cost of validating the whole store.
- A pre-existing schema violation in any unstaged file blocks an otherwise-valid
  commit that does not touch that file.

The Phase 2 `implements_pattern` field-preservation check already demonstrates
the correct pattern: `_get_modified_ac_paths()` uses
`git diff --cached --name-only --diff-filter=M` to find staged AC files. Phase 1
(schema validation) should be scoped the same way — to staged AC YAML files only.

### Why this was split from the Bug 1 fix

The existing test suite in `unit_tests/commit_guardian/test_check_ac_schema.py`
drives the hook via `HOOK_ROOT` over a whole temp store **without git staging**.
Scoping Phase 1 to staged files would make the existing exit-1 tests
(`TestMissingRequiredField`, `TestInvalidStatus`, `TestInvalidIdFormat`,
`TestMalformedIdRejectedAfterWidening`, `TestUnknownFieldRejectedAfterWidening`,
`TestMissingRequiredFieldAfterWidening`, etc.) pass trivially (nothing staged →
nothing validated → exit 0). The test harness must be reworked to stage files
(or simulate staging via an env hook like the existing `HOOK_TEST_FILES_MODIFIED`
seam) before the scope change can land. That rework exceeds a single-file
quick-fix, hence this dedicated ticket.

## Acceptance Criteria

- [ ] AC-1: Phase 1 schema validation processes only AC YAML files that are
  staged for the current commit (staged-added or staged-modified under
  `docs/acceptance-criteria/`), determined via `git diff --cached`. Files present
  in the store but not staged are not validated in Phase 1.
- [ ] AC-2: A staged AC file that violates the schema still blocks the commit
  (exit 1) with the same per-file error reporting as today.
- [ ] AC-3: A commit that stages no AC YAML file exits 0 without scanning the
  store.
- [ ] AC-4: Cross-file pattern checks (`validate_pattern_bindings_completeness`,
  `validate_deprecated_pattern_reference`, `validate_criteria_not_pattern_duplicate`)
  continue to resolve referenced pattern ACs against the full on-disk store, so a
  staged consuming AC can still be checked against an unstaged pattern AC. Only
  the set of files that are *validated* is narrowed; the cross-file *lookup index*
  is not.
- [ ] AC-5: The hook remains fail-open — git unavailability or a `git diff`
  failure must not hard-block the commit.
- [ ] AC-6: The unit-test harness is reworked so the existing exit-1 schema tests
  exercise the staged-files path (e.g. via a staging simulation env var) rather
  than passing trivially because nothing is staged.

## Sign-offs

- [x] test-writer — 2026-06-23 10:35
- [x] python-coder — 2026-06-23 11:45
- [x] test-runner — 2026-06-23 12:30
- [x] pr-reviewer — 2026-06-23 13:15
- [x] commit — 2026-06-23 14:00
- [ ] pull-request

## Comments

### 2026-06-23 10:35 — test-writer (status: ok)
feedback-id: fb_2026-06-23_44716984
completion_manifest:
  ac1_unstaged_not_validated_stubs: true
  ac2_staged_invalid_blocks_stubs: true
  ac3_no_staged_exits_zero_stubs: true
  ac4_cross_file_lookup_full_store_stubs: true
  ac5_fail_open_git_unavailable_stubs: true
  ac6_seam_wired_stubs: true
  all_prior_tests_still_pass: true
  new_tests_are_red: true
Wrote 14 new test stubs covering AC-1 through AC-6. Ran pytest: 51 tests collected — 37 pre-existing tests remain GREEN, 6 new tests are RED (guard tests for the HOOK_TEST_STAGED_FILES seam and staged-scope behavior), 8 new tests pass immediately (AC-2 positive cases and AC-4/AC-6 edge cases that don't require the seam). The red_baseline is: TestAC1UnstagedFilesNotValidated::test_unstaged_invalid_file_does_not_block_commit, TestAC1UnstagedFilesNotValidated::test_unstaged_file_with_invalid_status_does_not_block, TestAC3NoStagedAcFilesExitsZero::test_empty_staged_list_exits_zero_even_with_invalid_store, TestAC3NoStagedAcFilesExitsZero::test_hook_test_staged_files_unset_falls_back_to_git, TestAC5FailOpenOnGitUnavailable::test_hook_no_git_env_makes_phase1_use_empty_staged_list, TestAC6StagingSeamWiredForExistingExitOneTests::test_seam_empty_string_ignores_store_violations.

### 2026-06-23 11:45 — python-coder (status: ok)
feedback-id: fb_2026-06-23_061d39b7
completion_manifest:
  ac1_staged_scope_only: true
  ac2_staged_invalid_blocks: true
  ac3_no_staged_exits_zero: true
  ac4_cross_file_lookup_full_store: true
  ac5_fail_open_git_unavailable: true
  ac6_seam_wired_existing_tests: true
  all_51_tests_green: true
  files_touched_match_plan: true
Added `_get_staged_ac_paths(root)` to `check_ac_schema.py` — checks `HOOK_TEST_STAGED_FILES` env seam first, then falls back to `git diff --cached --name-only --diff-filter=AM`, and returns `[]` when `HOOK_NO_GIT=1` or git is unavailable (fail-open). Modified `main()` to use this function for Phase 1 validation instead of `_find_ac_files()`, while keeping the full-store `_build_ac_index()` for cross-file lookups (AC-4 preserved). Reworked `_run_hook()` in the test file to set `HOOK_TEST_STAGED_FILES` to all yaml files in the temp AC dir so existing exit-1 tests continue to exercise the validation path. All 51 tests pass (45 pre-existing + 6 formerly-RED new tests now GREEN).

### 2026-06-23 12:30 — test-runner (status: ok)
feedback-id: fb_2026-06-23_a5e84747
completion_manifest:
  all_51_tests_pass: true
  ac1_unstaged_not_validated: true
  ac2_staged_invalid_blocks: true
  ac3_no_staged_exits_zero: true
  ac4_cross_file_pattern_full_store: true
  ac5_fail_open_git_unavailable: true
  ac6_seam_wired_existing_tests: true
Ran `pytest unit_tests/commit_guardian/test_check_ac_schema.py -v`: all 51 tests collected and passed in 15.51 s. All AC-1 through AC-6 coverage tests (TestAC1UnstagedFilesNotValidated, TestAC2StagedInvalidFileBlocksCommit, TestAC3NoStagedAcFilesExitsZero, TestAC4CrossFilePatternChecksUseFullStore, TestAC5FailOpenOnGitUnavailable, TestAC6StagingSeamWiredForExistingExitOneTests) are green, confirming the staged-scope implementation is correct and no regressions in the 37 pre-existing tests.

### 2026-06-23 13:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-23_pr_reviewer_01
completion_manifest:
  ac1_staged_scope_only: true
  ac2_staged_invalid_blocks: true
  ac3_no_staged_exits_zero: true
  ac4_cross_file_lookup_full_store: true
  ac5_fail_open_git_unavailable: true
  ac6_seam_wired_existing_tests: true
  error_handling_policy_compliant: true
  no_regressions: true
  test_quality: true
Reviewed the working diff. _get_staged_ac_paths() correctly implements the HOOK_TEST_STAGED_FILES seam and git diff --cached fallback, returning [] on git unavailability (fail-open). main() correctly calls _get_staged_ac_paths() for Phase 1 scope and _find_ac_files() for the full-store cross-file lookup index (AC-4 preserved). Error handling uses specific exceptions (subprocess.SubprocessError, OSError) with a stderr WARNING and no silent swallow — compliant with the project error handling policy. The failed variable is correctly initialized in both branches of the if/else before Phase 2 reads it. _run_hook() rework sets HOOK_TEST_STAGED_FILES to all yaml files in the temp AC dir, preserving pre-existing exit-1 test behaviour via the staged-scope path (AC-6). All 14 new tests are meaningful and well-structured. No high-confidence blockers found.

### 2026-06-23 14:00 — commit (status: ok)
feedback-id: fb_2026-06-23_commit_acschemahook
completion_manifest:
  staged_files_verified: true
  all_pre_commit_hooks_passed: true
  commit_sha: 302fa33
  commit_message_matches_plan: true
  ac1_through_ac6_covered: true
Commit succeeded on first attempt. All 29 pre-commit hooks passed (secrets, ADR, schema, agent-diagrams, etc.). 3 files committed: templates/scripts/commit_guardian/check_ac_schema.py, unit_tests/commit_guardian/test_check_ac_schema.py, tickets/00_inbox/TICKET-20260622-AcSchemaHookStagedScope.md. SHA: 302fa33. Commit message includes Ticket traceability tag.

## Out of Scope

- The Bug 1 fix (manual validator as fallback only) — already shipped in PR #141
  (AC GE-112).
- Changing the JSON Schema contract itself.

## Risk & Safety

- Touches money? No.
- Touches data? No — pre-commit validation only.
- Reversibility? High — the change is localized to file selection in `main()` /
  `_find_ac_files`.
- Risk of regressions: medium — the test-harness rework is the delicate part;
  the staged-file scoping must not silently stop validating genuinely-staged
  files. AC-6 exists specifically to guard against the "tests pass because
  nothing is staged" trap.
