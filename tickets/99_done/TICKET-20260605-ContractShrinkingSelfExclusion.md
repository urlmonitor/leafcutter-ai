---
title: "Fix check_contract_shrinking false-positive when hook's own source is staged"
status: done
components:
  - build_pipeline
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/scripts/commit_guardian/check_contract_shrinking.py
  - templates/commit-guardian/check_contract_shrinking.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
ac_traceability:
  l1: BP-100d
  l2:
    - BP-100a-3
  l3:
    - BP-100a-3-i
  ac_path: docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
---

# Fix check_contract_shrinking false-positive when hook's own source is staged

## Actor / Goal

As a developer modifying hook infrastructure, I need to be able to stage and
commit changes to pre-commit hook scripts without being blocked by the very hook
I am fixing. The `check_contract_shrinking` hook should recognize its own source
files as infrastructure — not production code — and skip them during analysis.

## Context

`_TEST_PATH_RE` in `check_contract_shrinking.py` defines which file paths are
excluded from production-file classification. The current exclusion list covers
`unit_tests/`, `tests/`, `test_*.py`, `conftest.py` — but does not exclude
`commit_guardian/` paths.

When the hook's own source file (at `templates/scripts/commit_guardian/` or
`templates/commit-guardian/`) is staged alongside production files, the hook
classifies itself as production code. If any weakening patterns appear in the
diff — including the hook's own source containing those pattern strings — the
hook blocks the commit. This creates a false-positive that prevents developers
from modifying hook infrastructure.

Fix: extend `_TEST_PATH_RE` to also exclude paths matching `commit_guardian/`,
since hook infrastructure is not production application code.

## Acceptance Criteria

- [ ] AC BP-100a-3: `check_contract_shrinking.py`'s `_TEST_PATH_RE` is extended to exclude paths containing `commit_guardian/` (covering both `scripts/commit_guardian/check_*.py` and `templates/scripts/commit_guardian/check_*.py`). The same change is applied to both the canonical template and the legacy copy.
- [ ] AC BP-100a-3-i: Unit test verifies that a diff modifying `templates/scripts/commit_guardian/check_contract_shrinking.py` alongside a `pytest.mark.xfail` removal is NOT classified as contract-shrinking.

## AC Traceability

| AC ID | Level | Title | Agent |
|-------|-------|-------|-------|
| BP-100a-3 | L2 | Contract-shrinking hook excludes commit_guardian paths from production classification | python-coder |
| BP-100a-3-i | L3 | Test verifies commit_guardian paths are excluded from production file classification | test-writer |

AC files: `docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100a-*.yaml`

## Sign-offs

- [x] test-writer — 2026-06-05 00:00
- [x] python-coder — 2026-06-05 00:01
- [x] test-runner — 2026-06-05 00:02
- [x] pr-reviewer — 2026-06-05 00:03
- [x] commit — 2026-06-05 00:04
- [x] pull-request — 2026-06-05 00:05

## Comments

### 2026-06-05 00:00 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-05 00:01 — python-coder (status: ok)
feedback-id: fb_2026-06-05_8e45fc33
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Verified existing implementation: `_TEST_PATH_RE` in both `templates/scripts/commit_guardian/check_contract_shrinking.py` and `templates/commit-guardian/check_contract_shrinking.py` already includes `commit[_-]guardian/` exclusion (covers both underscore and hyphen variants). All 10 unit tests pass (3 in `test_check_contract_shrinking.py` + 7 in `test_contract_shrinking.py`). AC BP-100a-3 and BP-100a-3-i are fully satisfied by the existing implementation and test coverage.

### 2026-06-05 00:02 — test-runner (status: ok)
feedback-id: fb_2026-06-05_1ce37a4e
completion_manifest:
  tests_passing: true
  coverage_adequate: true
10/10 tests pass: 3 self-exclusion tests (`test_check_contract_shrinking.py`) verify the `commit_guardian/` path exclusion does not trigger false-positive detection, and 7 behavioral tests (`test_contract_shrinking.py`) verify the hook correctly blocks and allows commits. Command: `python3 -m pytest unit_tests/commit_guardian/test_check_contract_shrinking.py unit_tests/commit_guardian/test_contract_shrinking.py -v`.

### 2026-06-05 00:03 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_2c3d59ec
completion_manifest:
  implementation_correct: true
  tests_adequate: true
  no_regressions: true
  acs_satisfied: true
Code review complete. Both `templates/scripts/commit_guardian/check_contract_shrinking.py` and `templates/commit-guardian/check_contract_shrinking.py` correctly use `commit[_-]guardian/` in `_TEST_PATH_RE`, satisfying AC BP-100a-3 for both canonical and legacy paths. `test_check_contract_shrinking.py` provides the required unit test for AC BP-100a-3-i. All 10 tests green, no regressions. Approve.

### 2026-06-05 00:04 — commit (status: ok)
feedback-id: fb_2026-06-05_5b29154d
completion_manifest:
  staged_correctly: true
  commit_clean: true
Staged ticket file with all phase sign-offs. Committing ticket sign-off record for TICKET-20260605-ContractShrinkingSelfExclusion.

### 2026-06-05 00:05 — pull-request (status: ok)
feedback-id: fb_2026-06-05_468cbb0e
completion_manifest:
  branch_pushed: true
  pr_opened: true
PR #57 opened: https://github.com/urlmonitor/leafcutter-ai/pull/57. Branch `feature/contractshrinkingselfexclusion` pushed to origin and tracking set.

