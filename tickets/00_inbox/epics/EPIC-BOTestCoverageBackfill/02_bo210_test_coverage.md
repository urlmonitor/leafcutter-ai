---
title: "Establish green test coverage for BO-210 (precommit-safety-net) ACs"
status: todo
components:
  - build_orchestration
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-210a-1
ac_coverage:
  - BO-210a-1
  - BO-210a-1-i
  - BO-210a-2
  - BO-210b-1
  - BO-210b-1-i
  - BO-210b-2
  - BO-210c-1
  - BO-210c-1-i
  - BO-210c-1-ii
  - BO-210c-1-iii
  - BO-210c-2
  - BO-210c-2-i
files_touched:
  - unit_tests/commit_guardian/test_precommit_safety_net.py
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

# 02: Green test coverage for BO-210

## Actor / Goal

As the AC store, I want every BO-210 AC in `ac_coverage` to have a real, green
unit test that **names the AC**, so its `work_status: done` is honestly backed by
verifiable coverage (per the 2026-07-14 test-truth rule).

## Remediation Context (audit 2026-07-14)

These ACs are implemented in code but lack a valid green test link. Two natures:

- **link-or-author** — the audit judged the behaviour built; find the existing
  test that asserts it and add a `covers: <AC>` citation. If no test genuinely
  asserts it, author one. Then run green and record `covered_by` on the AC.
- **author test** — no test asserts the behaviour; author one (test-writer),
  run green, then record `covered_by`.

For BO-210 specifically, note any deploy-layout test-path issues: subprocess tests
that hardcode `leafcutter-ai/scripts/...` must resolve the deployed/template
script so they pass in a source checkout.

### link-or-author
# (none)

### author test
- BO-210a-1  # author test
- BO-210a-1-i  # author test
- BO-210a-2  # author test
- BO-210b-1  # author test
- BO-210b-1-i  # author test
- BO-210b-2  # author test
- BO-210c-1  # author test
- BO-210c-1-i  # author test
- BO-210c-1-ii  # author test
- BO-210c-1-iii  # author test
- BO-210c-2  # author test
- BO-210c-2-i  # author test

## Acceptance Criteria

For each AC in `ac_coverage`: a green test names it; its `covered_by` records the
test path (`::test_function` where applicable); `work_status: done` only after green.

## Test Requirements

```yaml
tests:
  - name: test_bo_210_ac_has_named_green_test
    file: unit_tests/commit_guardian/test_precommit_safety_net.py
    covers: [BO-210a-1]
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
