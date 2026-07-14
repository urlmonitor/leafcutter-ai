---
title: "Establish green test coverage for BO-600 (change-driven-guardrails) ACs"
status: todo
components:
  - commit_guardian
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-650-2
ac_coverage:
  - BO-650-2
  - BO-650-3
files_touched:
  - unit_tests/test_generate_ticket_from_ac.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 06: Green test coverage for BO-600

## Actor / Goal

As the AC store, I want every BO-600 AC in `ac_coverage` to have a real, green
unit test that **names the AC**, so its `work_status: done` is honestly backed by
verifiable coverage (per the 2026-07-14 test-truth rule).

## Remediation Context (audit 2026-07-14)

These ACs are implemented in code but lack a valid green test link. Two natures:

- **link-or-author** — the audit judged the behaviour built; find the existing
  test that asserts it and add a `covers: <AC>` citation. If no test genuinely
  asserts it, author one. Then run green and record `covered_by` on the AC.
- **author test** — no test asserts the behaviour; author one (test-writer),
  run green, then record `covered_by`.

For BO-600 specifically, note any deploy-layout test-path issues: subprocess tests
that hardcode `leafcutter-ai/scripts/...` must resolve the deployed/template
script so they pass in a source checkout.

### link-or-author
# (none)

### author test
- BO-650-2  # author test
- BO-650-3  # author test

## Acceptance Criteria

For each AC in `ac_coverage`: a green test names it; its `covered_by` records the
test path (`::test_function` where applicable); `work_status: done` only after green.

## Test Requirements

```yaml
tests:
  - name: test_bo_600_ac_has_named_green_test
    file: unit_tests/test_generate_ticket_from_ac.py
    covers: [BO-650-2]
    asserts: at least one green test names this AC and asserts its behaviour.
```

## Sign-offs

- [x] test-writer — 2026-07-14 15:30
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-07-14 15:30 — test-writer (status: ok)
feedback-id: fb_2026-07-14_010fd4d2
completion_manifest:
  tests_written: true
  tests_red_before_implementation: true
  covers_bo650_2: true
  covers_bo650_3: true
red_baseline:
  - test_name: test_bo650_2_adr_author_supports_supersedes_scenario
    file: unit_tests/test_generate_ticket_from_ac.py
    error: "AssertionError: BO-650-2: The adr-author.md template prohibits supersession with the line: 'Do not edit or supersede existing ADRs.' — assert 'Do not edit...xisting ADRs' not in '---\\ndescri...'"
  - test_name: test_bo650_3_architect_review_directs_write_c4_diagram_skill
    file: unit_tests/test_generate_ticket_from_ac.py
    error: "AssertionError: BO-650-3: The architect-review.md template does not reference the 'write-c4-diagram' skill by name. — assert 'write-c4-diagram' in '---\\ndescription...'"
  - test_name: test_bo650_3_write_c4_diagram_skill_prevents_duplicate_diagrams
    file: unit_tests/test_generate_ticket_from_ac.py
    error: "AssertionError: BO-650-3: The write-c4-diagram skill does not instruct agents to check for an existing diagram before creating a new one (duplicate prevention). — assert False"
  - test_name: test_bo650_3_write_c4_diagram_skill_records_triggering_ticket
    file: unit_tests/test_generate_ticket_from_ac.py
    error: "AssertionError: BO-650-3: The write-c4-diagram skill does not include a frontmatter field for recording the triggering ticket ID in diagram metadata. — assert False"

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_generate_ticket_from_ac.py | unit_tests/ | pytest | 4 tests appended (classes TestBO650ArchitectADRProduction, TestBO650ArchitectC4DiagramProduction) |

### Verification Run
- Command (plugin disabled): `python -m pytest unit_tests/test_generate_ticket_from_ac.py::TestBO650ArchitectADRProduction unit_tests/test_generate_ticket_from_ac.py::TestBO650ArchitectC4DiagramProduction -v -p 'no:scripts.ac_store.pytest_ac_enforcement'`
- Result: **red — 4 failures (exit code 1)** — assertions genuinely fail before implementation
- Note: when run with the project's default `pytest_ac_enforcement` plugin, tests show as XFAILED (exit 0) because BO-650-2 and BO-650-3 have `work_status: todo`. This is intentional project behavior — the plugin converts known-failing tests for non-done ACs to XFAILED to avoid blocking CI during development. The underlying assertions ARE failing.

### Notes
- BO-650-2 is covered by `test_bo650_2_adr_author_supports_supersedes_scenario`: asserts the adr-author.md prohibition on supersession is removed and supersession handling instructions are added.
- BO-650-3 is covered by three tests: (1) architect-review must reference write-c4-diagram skill; (2) write-c4-diagram skill must have explicit duplicate-avoidance step; (3) write-c4-diagram skill frontmatter must include ticket reference field.
- All 4 tests append to the existing `unit_tests/test_generate_ticket_from_ac.py` file (282 lines inserted).
- The `# covers: BO-650-2` and `# covers: BO-650-3` tags are present on every new test function as required.
