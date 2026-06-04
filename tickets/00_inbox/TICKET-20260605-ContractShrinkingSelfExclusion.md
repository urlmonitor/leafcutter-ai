---
title: "Fix check_contract_shrinking false-positive when hook's own source is staged"
status: todo
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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
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

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
