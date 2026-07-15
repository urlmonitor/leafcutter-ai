---
title: "Fix AC-schema drift: components required + axis fields accepted (check_ac_schema, readiness_gate)"
status: todo
components:
  - commit_guardian
created: 2026-07-15
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: schema
risk_surface: contract_boundary
files_touched:
  - config/ac_store_schema.json
  - templates/scripts/commit_guardian/check_ac_schema.py
  - scripts/ac_store/validate_ac_schema.py
  - unit_tests/commit_guardian/test_check_ac_schema.py
  - tests/ac_store/test_readiness_gate.py
  - unit_tests/ac_store/test_readiness_gate.py
agents:
  test-writer: not_needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 01: Fix AC-schema drift (components required + axis fields)

## Actor / Goal

As a maintainer, I want the AC schema and its validators to accept the AC shape that
the store actually uses post-#277, so valid ACs stop being rejected and both
`test_check_ac_schema` and `test_readiness_gate` go green.

## Context

Two files fail for the SAME root cause (verified by running with `-o addopts=""`, which
lifts the `pytest_ac_enforcement` xfail-mask):

- `unit_tests/commit_guardian/test_check_ac_schema.py` — **13 failures**. `[check-ac-schema]:
  N file(s) failed validation`. The `#277` component-vocab work made `components` a
  required property, and added axis fields, but the schema/hook were not updated: the
  hook rejects valid ACs that carry `change_target` / `risk_surface` / `pattern_slots` /
  `implements_pattern`, and `validate_manually()` applies stricter-than-schema rules on
  the jsonschema **success** path (rejecting hierarchical ids / free-form `origin_agent`).
- `tests/ac_store/test_readiness_gate.py` (+ dup in `unit_tests/ac_store/`) — **3 failures**
  (currently masked to xfail). `validate_ac_schema.py` exits 1 `Missing required field
  'components'` because the test's `_make_ac_yaml()` fixture omits `components`, now
  mandatory (AC ACS-100a-1).

This is the residual of "cluster 2" — the salvage PR #300 fixed only 1 of 14
`test_check_ac_schema` cases and explicitly deferred the rest. Not owned by any epic.

## Acceptance Criteria

```gherkin
Given the current AC store shape (components required; change_target/risk_surface/
  pattern_slots/implements_pattern axes; hierarchical ids; historical origin_agent values)
When check-ac-schema and validate_ac_schema run against real store AC files
Then valid ACs exit 0 and only genuinely-invalid ACs are rejected
  and test_check_ac_schema (both copies) and test_readiness_gate pass with addopts=""

Given the fix
When the suite runs with AC_ENFORCE_STRICT=1
Then none of these tests are xfail-masked — they are genuinely green (anti-mask check)

Given the assertions
Then each still verifies the real schema contract (a deliberately-invalid AC — missing
  components, bad axis enum — is STILL rejected); the fix does NOT pass by loosening the
  schema to accept anything or by deleting assertions
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_check_ac_schema.py | ac_store_schema.json / check_ac_schema.py | |
| AC-2 | test_readiness_gate.py | validate_ac_schema.py | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Add `components` (required, non-empty list) and the axis fields (`change_target`,
      `risk_surface`, `pattern_slots`, `implements_pattern`) to `config/ac_store_schema.json`
      with correct enums; confirm `additionalProperties` posture is intentional.
- [ ] Reconcile `validate_manually()` in `check_ac_schema.py` with the schema so it does
      not reject schema-valid ACs on the success path (hierarchical ids, historical
      `origin_agent`).
- [ ] Fix `_make_ac_yaml()` in both `test_readiness_gate.py` copies to include `components`
      (test-side — the schema mandate is correct).
- [ ] Run all three files with `-o addopts=""` AND `AC_ENFORCE_STRICT=1`; confirm genuinely green.
- [ ] Add/keep a negative case proving invalid ACs are still rejected.

## Risk & Safety
- Touches money? No.
- Touches data? Schema contract for the AC store — validate against real store files; reversible.
- Reversibility? Fully reversible.
