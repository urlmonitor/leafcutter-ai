---
title: "Write check_fixture_orphans.py CI script"
status: done
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_conftest_fixture_helper.md
priority: low
phase: "Phase 2"
roadmap_phase: phase_1
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/ci/check_fixture_orphans.py
  - unit_tests/commit_guardian/test_check_fixture_orphans.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# 04: Write check_fixture_orphans.py CI script

## Actor / Goal

In order to prevent stale fixture directories from accumulating as test files
are renamed or deleted, we need a `scripts/ci/check_fixture_orphans.py` script
that cross-references every directory under `tests/fixtures/` against the set
of `tests/test_*.py` files, so that orphaned fixture directories are flagged
before they silently consume disk space and confuse future authors.

## Context

The fixture convention established by ticket 01 maps each test file
(`test_<module>.py`) to a fixture subdirectory (`tests/fixtures/<module>/`).
Over time, test files may be renamed, merged, or deleted while their
corresponding fixture directories remain — creating orphans.

This script is intentionally a standalone CI check (not a pre-commit hook) to
avoid adding latency to every commit. It can be run in CI on PRs that touch
`tests/` or registered as an optional pre-commit hook for end-of-sprint cleanup.

### Algorithm

```
orphans = []
for each dir in tests/fixtures/ (excluding _shared/ and __pycache__):
    expected_test_file = tests/test_<dir_name>.py
    if expected_test_file not in set(tests/test_*.py):
        orphans.append(dir)

if orphans:
    print each orphan with a "no corresponding test file found" message
    exit(1)
else:
    exit(0)
```

### _shared/ exclusion

`tests/fixtures/_shared/` is explicitly excluded from orphan checking — shared
fixtures by definition have no single corresponding test file.

### Output format

```
ORPHAN: tests/fixtures/old_build_phase/ — no corresponding tests/test_old_build_phase.py
ORPHAN: tests/fixtures/removed_module/ — no corresponding tests/test_removed_module.py

2 orphan fixture director(ies) found. Remove or migrate them.
```

## Acceptance Criteria

```gherkin
Given tests/fixtures/removed_module/ exists but tests/test_removed_module.py does not
When check_fixture_orphans.py runs against the tests/ directory
Then it prints "ORPHAN: tests/fixtures/removed_module/" with an explanation
 And exits 1

Given tests/fixtures/build_clean/ exists and tests/test_build_clean.py exists
When check_fixture_orphans.py runs
Then tests/fixtures/build_clean/ is not flagged as an orphan

Given tests/fixtures/_shared/ exists with no corresponding test file
When check_fixture_orphans.py runs
Then _shared/ is not flagged as an orphan

Given all fixture directories have corresponding test files
When check_fixture_orphans.py runs
Then it prints "No orphan fixtures found." and exits 0
```

## Sign-offs

- [x] test-writer — 2026-06-04 10:00
- [x] python-coder — 2026-06-04 10:05
- [x] pr-reviewer — 2026-06-04 10:10
- [x] commit — 2026-06-04 10:15
- [x] pull-request — 2026-06-04 10:20

## Comments

### 2026-06-04 10:00 — test-writer (status: ok)
feedback-id: fb_2026-06-04_09925147
completion_manifest:
  test_file_created: true
  all_ac_covered: true
  tmp_path_fixture_used: true
Wrote unit_tests/commit_guardian/test_check_fixture_orphans.py with 7 test cases covering all acceptance criteria: orphan detection (exit 1 + ORPHAN line), matched fixture (exit 0), _shared/ exclusion, __pycache__ exclusion, empty fixtures dir (exit 0), multiple orphans, and plain-file entries being ignored. All tests invoke the script as a subprocess via sys.executable for exit-code contract verification.

### 2026-06-04 10:05 — python-coder (status: ok)
feedback-id: fb_2026-06-04_e8f27da0
completion_manifest:
  script_created: true
  cli_args_implemented: true
  exclusions_implemented: true
  exit_codes_correct: true
  docstring_with_usage: true
  init_py_created: true
  tests_green: true
Created scripts/ci/check_fixture_orphans.py with --fixtures-dir/--tests-dir argparse CLI, _find_orphans() helper, _shared/ and __pycache__ exclusions, correct exit codes (0/1/2), and a full docstring with usage and CI registration instructions. Also created scripts/ci/__init__.py (consistent with other script directories). All 7 tests pass (7 passed in 1.02s).

### 2026-06-04 10:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_934c0804
completion_manifest:
  all_acs_met: true
  error_handling_compliant: true
  docstring_complete: true
  tests_green: true
  no_regressions: true
All four Gherkin ACs satisfied. Error handling compliant with project rules (OSError wrapped, no bare except, stderr logging + re-raise). Docstring includes usage example and CI registration YAML snippet. 7 tests pass. No regressions or blockers found.

### 2026-06-04 10:15 — commit (status: ok)
feedback-id: fb_2026-06-04_09a9579a
completion_manifest:
  files_staged_correctly: true
  commit_clean: true
  pre_commit_hooks_passed: true
Committed 4 files (scripts/ci/__init__.py, scripts/ci/check_fixture_orphans.py, unit_tests/commit_guardian/test_check_fixture_orphans.py, ticket file) in commit 6bbde68. Stale lock from ticket 03 (dead PID 1349800) was cleaned before acquiring. PRE_COMMIT_ALLOW_NO_CONFIG=1 used as no .pre-commit-config.yaml is present in this worktree.

### 2026-06-04 10:20 — pull-request (status: ok)
feedback-id: fb_2026-06-04_0c91076f
completion_manifest:
  branch_pushed: true
  pr_open: true
Pushed commit 6bbde68 to origin/EPIC-TestFixtureConvention. Existing PR #44 (feat: add tests/fixtures/ convention and load_fixture() conftest helper (ADR-028)) on github.com/urlmonitor/leafcutter-ai updated automatically with the new commit.

## Implementation Tasks

### python-coder
- [x] Create `scripts/ci/check_fixture_orphans.py`:
  - Accept optional `--fixtures-dir` and `--tests-dir` arguments (default to
    `tests/fixtures/` and `tests/` relative to repo root)
  - Scan immediate subdirectories of `fixtures-dir`, skipping `_shared`,
    `__pycache__`, and any entry that is not a directory
  - Build the expected test file name: `test_<dir_name>.py` in `tests-dir`
  - Collect all orphans; print one `ORPHAN: <path>` line per orphan
  - Exit 0 on no orphans, exit 1 otherwise
  - Add a docstring with usage example and CI registration instructions
- [x] Create `scripts/ci/` directory if it does not already exist
  (add `__init__.py` if other scripts in the project use `__init__.py` in
  their script directories; otherwise omit)

### test-writer
- [x] Add `unit_tests/commit_guardian/test_check_fixture_orphans.py`:
  - `test_orphan_detected` — fixture dir exists, no test file → exits 1, prints ORPHAN
  - `test_no_orphan_when_test_exists` — fixture dir + test file both exist → exits 0
  - `test_shared_dir_excluded` — `_shared/` present, no test file → not flagged
  - `test_pycache_excluded` — `__pycache__/` present → not flagged
  - `test_empty_fixtures_dir` — fixtures dir exists but is empty → exits 0
  - Use `tmp_path` fixture (pytest) to construct synthetic directory trees

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only script.
- Reversibility? Fully reversible — the script is additive. Removing it from
  CI has no effect on tests or hooks.
- False-positive risk: the naming convention (test file stem = fixture dir name)
  is one-to-one. Test files using a different naming pattern may trigger false
  positives. The `_shared/` exclusion handles the most common multi-file case.
  Document the limitation in the script's docstring.
