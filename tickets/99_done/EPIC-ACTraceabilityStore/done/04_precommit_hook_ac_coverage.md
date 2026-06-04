---
title: "Pre-commit hook: every active AC must appear in at least one test's covers tag"
status: done
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_ac_store_schema.md
  - 03_precommit_hook_test_tagging.md
priority: medium
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/commit-guardian/check_ac_coverage.py
  - templates/commit-guardian/commit_guardian.json
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 04: Pre-commit hook: every active AC must appear in at least one test's covers tag

## Actor / Goal

In order to prevent ACs from going untested after they are created or amended,
we need a pre-commit hook that scans all active ACs in `docs/acceptance-criteria/`
and verifies each one appears in at least one `# covers:` tag across the test
suite, so that newly created ACs without tests are flagged at commit time.

## Context

This is the reverse direction of ticket 03. Ticket 03 checks that tests point
to ACs. This ticket checks that ACs are pointed to by tests. Together, they
enforce bidirectional coverage.

The check is asymmetric in severity:
- Missing `covers:` tag on a test (ticket 03) → configurable warn/error.
- Active AC with no test coverage (this ticket) → **warning only, always.**
  The warning is a prompt to the author to write a test; it is not a block,
  because the AC may have been created in a ticket that expects `test-writer`
  to add coverage in the same build cycle.

The hook works by:
1. Reading all `.yaml` files in `docs/acceptance-criteria/**/*.yaml`.
2. Filtering to `status: active` ACs.
3. Scanning all test files in `unit_tests/**/*.py` for `# covers: XX-NNN` tags.
4. For each active AC ID not found in any `covers:` tag: emit a warning.

### Performance

The hook scans the full test suite on every commit. For large repos with many
tests, this may be slow. The implementation should use a simple `grep`-style
scan (stdlib `re`) rather than full AST parsing to keep it fast.

## Acceptance Criteria

```gherkin
Given an active AC with ID FIN-001 exists in docs/acceptance-criteria/
 And no test file contains # covers: FIN-001
When check_ac_coverage.py runs
Then it prints a warning: "AC FIN-001 has no test coverage"
 And exits 0 (does not block the commit)

Given an active AC with ID FIN-001 exists
 And at least one test file contains # covers: FIN-001
When check_ac_coverage.py runs
Then no warning is emitted for FIN-001

Given an AC with status: deprecated exists
 And no test file covers it
When check_ac_coverage.py runs
Then no warning is emitted for the deprecated AC

Given docs/acceptance-criteria/ does not exist in the target project
When check_ac_coverage.py runs
Then it exits 0 silently (hook degrades gracefully when store not yet installed)
```

## Sign-offs

- [x] test-writer — 2026-06-04 14:00
- [x] python-coder — 2026-06-04 14:15
- [x] test-runner — 2026-06-04 14:20
- [x] pr-reviewer — 2026-06-04 14:25
- [x] commit — 2026-06-04 14:30
- [x] pull-request — 2026-06-04 14:35

## Comments

### 2026-06-04 14:00 — test-writer (status: ok)
feedback-id: fb_2026-06-04_4be81ad6
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
red_baseline:
  - test_name: TestEndToEndCheckAcCoverage::test_missing_ac_dir_exits_0
    file: unit_tests/commit_guardian/test_check_ac_coverage.py
    error: "AssertionError: 2 != 0 : Expected exit 0, got 2 — check_ac_coverage.py script not yet implemented"
  - test_name: TestEndToEndCheckAcCoverage::test_uncovered_active_ac_warns_exits_0
    file: unit_tests/commit_guardian/test_check_ac_coverage.py
    error: "AssertionError: 2 != 0 : Expected exit 0, got 2 — check_ac_coverage.py script not yet implemented"
  - test_name: TestEndToEndCheckAcCoverage::test_covered_ac_exits_0_no_warning
    file: unit_tests/commit_guardian/test_check_ac_coverage.py
    error: "AssertionError: 2 != 0 : Expected exit 0, got 2 — check_ac_coverage.py script not yet implemented"
  - test_name: TestEndToEndCheckAcCoverage::test_deprecated_ac_no_warning
    file: unit_tests/commit_guardian/test_check_ac_coverage.py
    error: "AssertionError: 2 != 0 : Expected exit 0, got 2 — check_ac_coverage.py script not yet implemented"
  - test_name: TestEndToEndCheckAcCoverage::test_multiple_uncovered_acs_all_warned
    file: unit_tests/commit_guardian/test_check_ac_coverage.py
    error: "AssertionError: 2 != 0 : Expected exit 0, got 2 — check_ac_coverage.py script not yet implemented"
Wrote 17 test stubs for check_ac_coverage.py in unit_tests/commit_guardian/test_check_ac_coverage.py. All subprocess tests are RED (exit 2 because script does not exist). Unit-level tests are properly skipped pending import. Red baseline captured above. Handoff to python-coder.

### 2026-06-04 14:15 — python-coder (status: ok)
feedback-id: fb_2026-06-04_eab6e992
completion_manifest:
  check_ac_coverage_written: true
  hook_registered_in_commit_guardian_json: true
  stdlib_only_no_dependencies: true
  graceful_degradation_on_missing_ac_dir: true
  always_exits_0: true
  all_tests_green: true
Implemented templates/commit-guardian/check_ac_coverage.py with load_active_ac_ids(), collect_covered_ids(), and report_uncovered() functions using stdlib only (re, pathlib, argparse). Registered as check-ac-coverage hook in commit_guardian.json hooks_manifest with pass_filenames: false. Also fixed test import mechanism to use importlib.util for robust path resolution. All 17 tests green; ruff E722/BLE001/TRY checks pass on both files.

### 2026-06-04 14:20 — test-runner (status: ok)
feedback-id: fb_2026-06-04_8d208ca0
completion_manifest:
  target_tests_all_green: true
  broader_suite_regression_free: true
Ran unit_tests/commit_guardian/test_check_ac_coverage.py: 17/17 passed. Ran the full unit_tests/commit_guardian/ suite: 97/97 passed. No regressions introduced.

### 2026-06-04 14:25 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_5200d317
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Reviewed working diff: check_ac_coverage.py (238 lines, stdlib-only), commit_guardian.json (+12 lines, new hook entry), test_check_ac_coverage.py (370 lines, 17 tests). All 4 ACs from the ticket are covered by tests. JSON indentation fixed for consistency. No high-confidence findings; ruff passes on both Python files. Approving.

### 2026-06-04 14:30 — commit (status: ok)
feedback-id: fb_2026-06-04_4b4fba60
completion_manifest:
  files_staged_correctly: true
  commit_created: true
Staged templates/commit-guardian/check_ac_coverage.py (new), templates/commit-guardian/commit_guardian.json (modified), unit_tests/commit_guardian/test_check_ac_coverage.py (new), tickets/00_inbox/epics/EPIC-ACTraceabilityStore/04_precommit_hook_ac_coverage.md (updated sign-offs). Committing.

### 2026-06-04 14:35 — pull-request (status: ok)
feedback-id: fb_2026-06-04_168f40ae
completion_manifest:
  commits_pushed: true
  pr_available: true
Pushed commit b0feef5 to remote EPIC-ACTraceabilityStore branch. Existing PR #46 (feat(ac-store): AC YAML schema, validator hook, and ADR-007) updated with ticket-04 implementation. PR URL: https://github.com/urlmonitor/leafcutter-ai/pull/46

## Implementation Tasks

### python-coder
- [x] Write `templates/commit-guardian/check_ac_coverage.py`:
  - Stdlib only (re, yaml if available; manual YAML parse for `id:` and
    `status:` if yaml not installed).
  - `load_active_ac_ids(ac_dir)` — recursively glob `*.yaml`, parse `id`
    and `status`, return set of IDs where `status == "active"`.
  - `collect_covered_ids(test_dir)` — recursively glob `test_*.py` and
    `*_test.py`, scan for `# covers: XX-NNN` regex, return set of found IDs.
  - `report_uncovered(active_ids, covered_ids)` — print warnings for each
    `active_ids - covered_ids`.
  - Graceful degradation: if `docs/acceptance-criteria/` does not exist,
    exit 0 with no output.
  - Always exit 0 (warnings only, never block).
- [x] Register `check_ac_coverage.py` in `commit_guardian.json` hooks
  (pass_filenames: false, no file filter — runs on every commit).

### test-writer
- [x] Write `unit_tests/commit_guardian/test_check_ac_coverage.py`:
  - `test_uncovered_active_ac_warns` — active AC with no test coverage prints warning.
  - `test_covered_ac_passes_silently` — active AC with coverage emits no warning.
  - `test_deprecated_ac_ignored` — deprecated AC with no coverage emits no warning.
  - `test_missing_ac_dir_exits_0` — no docs/acceptance-criteria/ → exit 0.
  - `test_multiple_uncovered_acs_all_warned` — three uncovered ACs → three warnings.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? New file. Removing from hook dispatch restores prior behaviour.
- Warning-only ensures the hook never blocks a commit. Teams can iterate
  on AC creation and test coverage in the same feature branch without friction.
