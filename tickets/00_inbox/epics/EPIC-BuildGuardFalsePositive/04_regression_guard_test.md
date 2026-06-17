---
title: "Regression guard: real-package test that build exits 0 on clean unmodified source"
status: todo
components:
  - build_pipeline
created: 2026-06-17
depends_on:
  - 02_fix_class_a_manifest.md
  - 03_resolve_class_b_scripts.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
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

# 04: Regression Guard — Real-Package Test That Build Exits 0 on Clean Unmodified Source

## Goal

In order to prevent this class of defect from shipping again, we need a regression
test that exercises the REAL `_check_script_reference_guard()` against the REAL
package source (not a synthetic manifest), so that any future manifest-drift is
caught by CI before a release.

## Context

The defect shipped because all existing tests used synthetic manifests. The guard
ran against real templates but the deployable-scripts set was constructed in-test
rather than by calling `_get_source_deployable_scripts()`. A guard that passes
against a synthetic manifest but fails against the real package is no guard at all.

This ticket adds:
1. **Positive-control test**: `_check_script_reference_guard()` called with the
   real `package_root` exits 0 after tickets 02 and 03 are applied.
2. **Negative-control test**: a synthetic template referencing a nonexistent script
   still triggers exit code 1, confirming the guard still detects real gaps.
3. **Manifest-derivation test**: `_get_source_deployable_scripts()` returns a
   superset of the scripts deployed by `build_commit_guardian` and `build_feedback`,
   confirming the drift-proof derivation from ticket 02 holds.

Key files:
- `unit_tests/` — add new test file here
- `scripts/build.py` — `_check_script_reference_guard()`,
  `_get_source_deployable_scripts()` (functions under test)
- `scripts/build_propagation_audit.py` — `EXTERNAL_DEPENDENCY_ALLOWLIST`
- `templates/agents/`, `templates/skills/` — real templates the guard scans

## Acceptance Criteria

```gherkin
Scenario: regression test uses real guard and real package (AC BP-900-Fix-4)
  Given a test in unit_tests/ that exercises _check_script_reference_guard
  When it runs against the actual package source (not a synthetic manifest)
  Then it asserts exit code 0 on a clean build of the unmodified package
  And the test is NOT marked xfail or skipped
  origin_agent: BrainCandy

Scenario: negative-control preserved (AC-2)
  Given a test that injects a synthetic template referencing scripts/does_not_exist.py
  When _check_script_reference_guard() runs with that synthetic template in scope
  Then it exits 1
  And the JSONL output names scripts/does_not_exist.py as the broken reference
  origin_agent: BrainCandy

Scenario: manifest-derivation test catches future drift (AC-3)
  Given a test that calls _get_source_deployable_scripts() with the real package_root
  When a new .py file is added to scripts/commit_guardian/ in a future change
  Then the test for manifest completeness fails unless the manifest is updated
  And the failure message names the missing script
  origin_agent: BrainCandy

Scenario: test does not use synthetic manifest for positive-control (AC-4)
  Given the existing test suite for _check_script_reference_guard
  When any test asserts exit code 0
  Then that test MUST call _get_source_deployable_scripts() with the real package_root
  And NOT construct the deployable set manually in the test body
  origin_agent: BrainCandy
```

## Implementation Tasks

- [ ] Add `unit_tests/test_build_guard_real_package.py` (or extend an existing test
  module) with:
  - `test_guard_exits_0_on_clean_package` — calls `_check_script_reference_guard()`
    with real `package_root`; asserts return value 0
  - `test_guard_exits_1_on_broken_ref` — injects a synthetic template with a
    nonexistent script ref; asserts return value 1 and JSONL output naming it
  - `test_manifest_covers_commit_guardian_scripts` — calls
    `_get_source_deployable_scripts(real_package_root)` and asserts all
    `scripts/commit_guardian/*.py` files are present in the returned set
  - `test_manifest_covers_full_feedback_set` — asserts `aggregate.py` and
    `resolve_feedback.py` are in the returned set
- [ ] Run the full test suite and confirm all new tests are green (positive-control)
  and that the negative-control is red before the fix is applied (or document that
  tickets 02 and 03 must be merged first)
- [ ] Ensure no existing test constructs the deployable set synthetically for a
  positive-control assertion; refactor if found

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Tests are additive; removal is trivial if the approach changes.
- Dependency note: the positive-control test (`test_guard_exits_0_on_clean_package`)
  MUST be implemented after tickets 02 and 03 are merged, or it will be red. Mark it
  `xfail(strict=True)` during development on this branch and flip to a real assertion
  once the preceding tickets land.

## Comments

_(Append-only log — leave blank when authoring.)_
