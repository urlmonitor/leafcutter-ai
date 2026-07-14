---
title: "Frontmatter guard: require change_target/risk_surface and reject null/empty"
status: todo
components:
  - commit_guardian
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-610-4
ac_coverage:
  - BO-610-3-i
  - BO-610-4
  - BO-610-4-i
  - BO-630-1-i
files_touched:
  - templates/hooks/ticket_frontmatter_guard.py
  - unit_tests/test_ticket_frontmatter_guard.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: signed_off
  pull-request: needed
---

# 03: Frontmatter guard requires fields + rejects null/empty

## Actor / Goal

As the guardrail engine, I want `ticket_frontmatter_guard` to *require*
`change_target`/`risk_surface` and reject null/empty values, so the BO-610 ACs
are actually enforced rather than contradicted.

## Remediation Context (audit 2026-07-14)

**Opposite behaviour + phantom tests.** The guard currently makes both fields
*optional* and accepts null/empty; its tests (`test_null_change_target_passes`,
`test_absent_risk_surface_passes`) assert **exactly the behaviour the ACs say to
reject**. `BO-630-1-i` model-tier default/validation is dead (helpers never
called, no `XL`-invalid error, no default `M`).

**Do: make the fields required, reject null/empty with a "Missing required
field"/"invalid value" error, and rewrite the inverted tests to assert the AC
behaviour (not its opposite).** Confirm no legitimate caller relied on the fields
being optional before flipping (call-site audit).

## Acceptance Criteria

Resolves BO-610-3-i, BO-610-4, BO-610-4-i, BO-630-1-i (verbatim Gherkin under
`.../guardrail-engine/BO-600-change-driven-guardrails/`).

## Test Requirements

```yaml
tests:
  - name: test_absent_change_target_is_rejected
    file: unit_tests/test_ticket_frontmatter_guard.py
    covers: [BO-610-4, BO-610-4-i]
    asserts: a ticket missing change_target/risk_surface fails with a required-field error.
  - name: test_null_or_empty_axis_is_rejected
    file: unit_tests/test_ticket_frontmatter_guard.py
    covers: [BO-610-3-i]
    asserts: null or empty change_target/risk_surface is rejected (replaces the inverted test).
```

## Sign-offs

- [x] test-writer — 2026-07-14 17:00
- [x] python-coder — 2026-07-14 18:00
- [x] test-runner — 2026-07-14 18:20
- [ ] pr-reviewer
- [x] commit — 2026-07-14 18:35
- [ ] pull-request

## Comments

### 2026-07-14 18:00 — python-coder (status: ok)
feedback-id: fb_2026-07-14_d8e9d449
completion_manifest:
  change_target_required: true
  risk_surface_required: true
  null_empty_rejected: true
  estimated_complexity_validator_added: true
  validate_wired: true
  inverted_tests_fixed: true
  all_22_tests_green: true
  ruff_clean: true
Promoted change_target and risk_surface from optional to REQUIRED in ticket_frontmatter_guard.py (BO-610-4/BO-610-3-i): absent/null/empty-list now return error messages containing the field name and "Valid values:". Added ALLOWED_COMPLEXITIES = ("S", "M", "L"), _check_estimated_complexity() (absent/null → no error; "XL" → error with "Valid values:" wording), and wired it into validate() (BO-630-1-i). Fixed 4 inverted tests in test_ticket_frontmatter_guard.py (test_absent_change_target_passes/test_null_change_target_passes/test_absent_risk_surface_passes/test_null_risk_surface_passes → now assert errors ARE produced). All 22 tests green; ruff clean on both files; behavioral spot-check confirmed the guard correctly flags a real on-disk ticket missing change_target/risk_surface.

red_baseline_results:
  - test_name: TestRequiredAxesBO6104.test_absent_change_target_is_rejected (missing=change_target)
    result: green
  - test_name: TestRequiredAxesBO6104.test_absent_change_target_is_rejected (missing=risk_surface)
    result: green
  - test_name: TestRequiredAxesBO6104.test_both_axes_absent_surfaces_both_errors
    result: green
  - test_name: TestNullAndEmptyAxesBO6103i.test_null_or_empty_axis_is_rejected (case=change_target_null)
    result: green
  - test_name: TestNullAndEmptyAxesBO6103i.test_null_or_empty_axis_is_rejected (case=change_target_empty_list)
    result: green
  - test_name: TestNullAndEmptyAxesBO6103i.test_null_or_empty_axis_is_rejected (case=risk_surface_null)
    result: green
  - test_name: TestEstimatedComplexityBO6301i.test_ac_bo630_1i_absent_complexity_no_error
    result: green
  - test_name: TestEstimatedComplexityBO6301i.test_ac_bo630_1i_null_complexity_no_error
    result: green
  - test_name: TestEstimatedComplexityBO6301i.test_ac_bo630_1i_invalid_xl_complexity_is_rejected
    result: green

### 2026-07-14 18:35 — commit (status: ok)
feedback-id: fb_2026-07-14_7b5f59db
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate: subject "feat(guardrail): require change_target/risk_surface, add estimated_complexity validator (BO-610/BO-630)"; staged files: templates/hooks/ticket_frontmatter_guard.py, unit_tests/test_ticket_frontmatter_guard.py, tickets/00_inbox/epics/EPIC-BOPhantomDoneRemediation/03_bo600_frontmatter_guard_require.md. All 22 tests green; both files ruff-clean per python-coder sign-off.

### 2026-07-14 17:00 — test-writer (status: ok)
feedback-id: fb_2026-07-14_1aebf45f
completion_manifest:
  tests_written: true
  tests_red: true
  ac_coverage_complete: true

Added 5 new failing test methods (9 failing subtests) to unit_tests/test_ticket_frontmatter_guard.py covering BO-610-3-i, BO-610-4, BO-610-4-i, and BO-630-1-i. All new tests are confirmed RED (non-zero exit, 9 failures). The existing guard treats `change_target` and `risk_surface` as optional fields, so absent/null cases return no errors — the new tests assert the opposite (required-field behavior). The BO-630-1-i tests fail via `self.fail()` because `_check_estimated_complexity` does not exist yet.

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_ticket_frontmatter_guard.py | unit_tests/ | unittest | written (additions to existing file) |

### Verification Run
- Command: `python unit_tests/test_ticket_frontmatter_guard.py`
- Result: red (9 failures — expected; implementation not yet written)

### Notes
- `test_null_or_empty_axis_is_rejected` has 4 subtests; 3 fail (null change_target, empty-list change_target, null risk_surface). The 4th subtest (`risk_surface_empty_str`) passes immediately because the existing enum check already rejects empty string — this is noted in the test docstring.
- BO-630-1-i tests use `setUp`/`_require()` pattern to avoid module-level ImportError; they fail via `AssertionError` (valid red state).

red_baseline:
  - test_name: TestRequiredAxesBO6104.test_absent_change_target_is_rejected (missing=change_target)
    file: unit_tests/test_ticket_frontmatter_guard.py
    error: "AssertionError: 0 not greater than 0 : Absent change_target must produce a required-field error (BO-610-4). Got no errors — field is still treated as optional."
  - test_name: TestRequiredAxesBO6104.test_absent_change_target_is_rejected (missing=risk_surface)
    file: unit_tests/test_ticket_frontmatter_guard.py
    error: "AssertionError: 0 not greater than 0 : Absent risk_surface must produce a required-field error (BO-610-4). Got no errors — field is still treated as optional."
  - test_name: TestRequiredAxesBO6104.test_both_axes_absent_surfaces_both_errors
    file: unit_tests/test_ticket_frontmatter_guard.py
    error: "AssertionError: 0 not greater than 0 : change_target absent must produce an error (BO-610-4-i)."
  - test_name: TestNullAndEmptyAxesBO6103i.test_null_or_empty_axis_is_rejected (case=change_target_null)
    file: unit_tests/test_ticket_frontmatter_guard.py
    error: "AssertionError: 0 not greater than 0 : Case 'change_target_null': null/empty value must produce an error (BO-610-3-i). Got no errors — value is silently accepted."
  - test_name: TestNullAndEmptyAxesBO6103i.test_null_or_empty_axis_is_rejected (case=change_target_empty_list)
    file: unit_tests/test_ticket_frontmatter_guard.py
    error: "AssertionError: 0 not greater than 0 : Case 'change_target_empty_list': null/empty value must produce an error (BO-610-3-i). Got no errors — value is silently accepted."
  - test_name: TestNullAndEmptyAxesBO6103i.test_null_or_empty_axis_is_rejected (case=risk_surface_null)
    file: unit_tests/test_ticket_frontmatter_guard.py
    error: "AssertionError: 0 not greater than 0 : Case 'risk_surface_null': null/empty value must produce an error (BO-610-3-i). Got no errors — value is silently accepted."
  - test_name: TestEstimatedComplexityBO6301i.test_ac_bo630_1i_absent_complexity_no_error
    file: unit_tests/test_ticket_frontmatter_guard.py
    error: "AssertionError: _check_estimated_complexity is not yet implemented in ticket_frontmatter_guard (BO-630-1-i). python-coder must add this validator and wire it into validate()."
  - test_name: TestEstimatedComplexityBO6301i.test_ac_bo630_1i_null_complexity_no_error
    file: unit_tests/test_ticket_frontmatter_guard.py
    error: "AssertionError: _check_estimated_complexity is not yet implemented in ticket_frontmatter_guard (BO-630-1-i). python-coder must add this validator and wire it into validate()."
  - test_name: TestEstimatedComplexityBO6301i.test_ac_bo630_1i_invalid_xl_complexity_is_rejected
    file: unit_tests/test_ticket_frontmatter_guard.py
    error: "AssertionError: _check_estimated_complexity is not yet implemented in ticket_frontmatter_guard (BO-630-1-i). python-coder must add this validator and wire it into validate()."


### 2026-07-14 18:20 — test-runner (status: ok)
feedback-id: fb_2026-07-14_bc9f39da
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
All 22 tests pass (22 subtests) in unit_tests/test_ticket_frontmatter_guard.py. Ran as a single-file action (python -m pytest -v); suite confirms required-field enforcement for change_target/risk_surface (BO-610-3-i, BO-610-4, BO-610-4-i) and estimated_complexity validation (BO-630-1-i).