---
title: "Write check_fixture_orphans.py CI script"
status: todo
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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
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

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder
- [ ] Create `scripts/ci/check_fixture_orphans.py`:
  - Accept optional `--fixtures-dir` and `--tests-dir` arguments (default to
    `tests/fixtures/` and `tests/` relative to repo root)
  - Scan immediate subdirectories of `fixtures-dir`, skipping `_shared`,
    `__pycache__`, and any entry that is not a directory
  - Build the expected test file name: `test_<dir_name>.py` in `tests-dir`
  - Collect all orphans; print one `ORPHAN: <path>` line per orphan
  - Exit 0 on no orphans, exit 1 otherwise
  - Add a docstring with usage example and CI registration instructions
- [ ] Create `scripts/ci/` directory if it does not already exist
  (add `__init__.py` if other scripts in the project use `__init__.py` in
  their script directories; otherwise omit)

### test-writer
- [ ] Add `unit_tests/commit_guardian/test_check_fixture_orphans.py`:
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
