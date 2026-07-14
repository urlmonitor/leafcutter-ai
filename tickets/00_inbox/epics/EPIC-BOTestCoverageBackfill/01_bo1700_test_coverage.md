---
title: "Establish green test coverage for BO-1700 (worktree-quality-gate-guard) ACs"
status: todo
components:
  - build_orchestration
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-1700a-1
ac_coverage:
  - BO-1700a-1
  - BO-1700a-10
  - BO-1700a-11
  - BO-1700a-2
  - BO-1700a-3
  - BO-1700a-3-i
  - BO-1700a-3-ii
  - BO-1700b-1
  - BO-1700b-2
  - BO-1700c-1
  - BO-1700c-1-i
  - BO-1700c-1-ii
  - BO-1700c-1-iv
  - BO-1700c-2
  - BO-1700c-3
  - BO-1700d-1
  - BO-1700d-4
  - BO-1700e-1
  - BO-1700e-2
  - BO-1700e-4
  - BO-1700e-5
  - BO-1700f-1
  - BO-1700f-1-i
  - BO-1700h-2
  - BO-1700b-3
  - BO-1700d-2
  - BO-1700d-3
  - BO-1700d-3-i
  - BO-1700e-1-i
files_touched:
  - unit_tests/commit_guardian/test_verify_precommit_active.py
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
---

# 01: Green test coverage for BO-1700

## Actor / Goal

As the AC store, I want every BO-1700 AC in `ac_coverage` to have a real, green
unit test that **names the AC**, so its `work_status: done` is honestly backed by
verifiable coverage (per the 2026-07-14 test-truth rule).

## Remediation Context (audit 2026-07-14)

These ACs are implemented in code but lack a valid green test link. Two natures:

- **link-or-author** — the audit judged the behaviour built; find the existing
  test that asserts it and add a `covers: <AC>` citation. If no test genuinely
  asserts it, author one. Then run green and record `covered_by` on the AC.
- **author test** — no test asserts the behaviour; author one (test-writer),
  run green, then record `covered_by`.

For BO-1700 specifically, note any deploy-layout test-path issues: subprocess tests
that hardcode `leafcutter-ai/scripts/...` must resolve the deployed/template
script so they pass in a source checkout.

### link-or-author
- BO-1700a-1  # link-or-author
- BO-1700a-10  # link-or-author
- BO-1700a-11  # link-or-author
- BO-1700a-2  # link-or-author
- BO-1700a-3  # link-or-author
- BO-1700a-3-i  # link-or-author
- BO-1700a-3-ii  # link-or-author
- BO-1700b-1  # link-or-author
- BO-1700b-2  # link-or-author
- BO-1700c-1  # link-or-author
- BO-1700c-1-i  # link-or-author
- BO-1700c-1-ii  # link-or-author
- BO-1700c-1-iv  # link-or-author
- BO-1700c-2  # link-or-author
- BO-1700c-3  # link-or-author
- BO-1700d-1  # link-or-author
- BO-1700d-4  # link-or-author
- BO-1700e-1  # link-or-author
- BO-1700e-2  # link-or-author
- BO-1700e-4  # link-or-author
- BO-1700e-5  # link-or-author
- BO-1700f-1  # link-or-author
- BO-1700f-1-i  # link-or-author
- BO-1700h-2  # link-or-author

### author test
- BO-1700b-3  # author test
- BO-1700d-2  # author test
- BO-1700d-3  # author test
- BO-1700d-3-i  # author test
- BO-1700e-1-i  # author test

## Acceptance Criteria

For each AC in `ac_coverage`: a green test names it; its `covered_by` records the
test path (`::test_function` where applicable); `work_status: done` only after green.

## Test Requirements

```yaml
tests:
  - name: test_bo_1700_ac_has_named_green_test
    file: unit_tests/commit_guardian/test_verify_precommit_active.py
    covers: [BO-1700a-1]
    asserts: at least one green test names this AC and asserts its behaviour.
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
