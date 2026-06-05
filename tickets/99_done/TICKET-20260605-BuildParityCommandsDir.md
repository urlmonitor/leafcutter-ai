---
title: "Register templates/commands/ in build parity test allow-list"
status: inbox
components:
  - build_pipeline
created: 2026-06-05
depends_on: []
priority: low
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - tests/test_build_artifact_parity.py
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
complexity: trivial
ac_coverage: 0/2
---

# Register templates/commands/ in build parity test allow-list

## Actor / Goal

As a developer maintaining the build pipeline, I need the build parity test
suite to pass on main so that CI is green and pre-existing failures do not
mask new regressions.

## Context

Commit 80149f7 added `templates/commands/` (slash command definitions for
`/po`, `/ba`, `/it-po`) but did not update the build parity test's
directory allow-list.

`TestTemplateDirectoriesHaveCategories.test_no_unlisted_artifact_template_dirs`
iterates every directory under `templates/` and asserts it is either in
`_USER_FACING_CATEGORIES`, `_INTERNAL_CATEGORIES`, or the `non_artifact_dirs`
exemption set. Because `commands` appears in none of those three sets, the
test fails with:

```
AssertionError: Template directory 'commands' exists but is not listed in
test_build_artifact_parity.py.
```

`templates/commands/` holds static slash-command markdown files. It does not
produce shimmed build outputs and does not need shim_map, managed-artifact-dir,
or drift-detection coverage. The correct fix is to add `"commands"` to
`non_artifact_dirs` — one line, no other changes required.

333 other tests pass. This is the only failing test on main.

## Acceptance Criteria

- [x] AC-1: `"commands"` is present in the `non_artifact_dirs` set inside
  `TestTemplateDirectoriesHaveCategories.test_no_unlisted_artifact_template_dirs`
  in `tests/test_build_artifact_parity.py`.
- [x] AC-2: Running `python -m pytest tests/test_build_artifact_parity.py -v`
  reports 6 passed, 0 failed, with all subtests green including
  `test_no_unlisted_artifact_template_dirs`.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 | test_no_unlisted_artifact_template_dirs PASSED | Added "commands" to non_artifact_dirs set in test_no_unlisted_artifact_template_dirs | ok — 2026-06-05 |
| AC-2 | 6 passed, 0 failed, 30 subtests green | All 6 tests pass: 6 passed, 0 failed, including test_no_unlisted_artifact_template_dirs | ok — 2026-06-05 |

## Sign-offs

- [x] python-coder — 2026-06-05 14:00
- [x] test-runner — 2026-06-05 14:01
- [x] pr-reviewer — 2026-06-05 14:02
- [x] commit — 2026-06-05 14:03
- [x] pull-request — 2026-06-05 14:04

## Comments

### 2026-06-05 14:00 — python-coder (status: ok)
feedback-id: fb_2026-06-05_1d1ee22f
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
"commands" was already added to non_artifact_dirs in test_build_artifact_parity.py (commit a2129a1). All 6 tests pass: 6 passed, 0 failed, 30 subtests green including test_no_unlisted_artifact_template_dirs.

### 2026-06-05 14:01 — test-runner (status: ok)
feedback-id: fb_2026-06-05_b56109e9
completion_manifest:
  tests_green: true
  target_test_file_verified: true
  ac2_confirmed: true
6 passed, 0 failed, 30 subtests green. test_no_unlisted_artifact_template_dirs passed. AC-2 confirmed: test_build_artifact_parity.py reports 6 passed, 0 failed.

### 2026-06-05 14:02 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_447126f5
completion_manifest:
  change_is_minimal_and_correct: true
  acs_satisfied: true
  tests_green: true
  no_quality_concerns: true
One-line fix: `"commands"` added alphabetically to `non_artifact_dirs` set. Commit a2129a1 is clean. All 6 tests pass. AC-1 and AC-2 fully satisfied. No quality concerns.

### 2026-06-05 14:03 — commit (status: ok)
feedback-id: fb_2026-06-05_5a077c49
completion_manifest:
  commit_created: true
  staged_files_match_scope: true
  implementation_in_history: true
Committed ticket sign-offs in 4a2760f. Implementation change (adding "commands" to non_artifact_dirs) was already in commit a2129a1. Staged only the ticket file per explicit-path discipline.

### 2026-06-05 14:04 — pull-request (status: ok)
feedback-id: fb_2026-06-05_51dc64c4
completion_manifest:
  branch_pushed: true
  pr_opened: true
  pr_url_recorded: true
Pushed feature/buildparitycommandsdir and opened PR #64: https://github.com/urlmonitor/leafcutter-ai/pull/64
