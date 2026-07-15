---
title: "Fix component/hook schema-drift tests (minimum_schema, tier field, build_phases)"
status: todo
components:
  - commit_guardian
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
agents:
  test-writer: not_needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Fix component/hook schema-drift tests

## Actor / Goal

As a maintainer, I want the component-schema and hook-manifest drift tests to
match the current data, so this cluster stops failing.

## Context

Residual subset of Cluster 6 (2026-07-15 gap analysis). On CI (`origin/main` run
`29403216629`) these fail and are NOT covered by `c990bb89` or either audit epic:

- `unit_tests/commit_guardian/test_check_components_minimum_schema.py` (1):
  `test_all_current_entries_pass_minimum_schema` —
  `AssertionError: Lists differ: ["Component 'ac_driven_dev': 'primary_code…'"] != []`.
  A real `components.json` entry fails the minimum-schema the test enforces.
- `unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py` (1):
  `test_hooks_manifest_tier_field` —
  `Lists differ: ["id='check-predone-scope' tier=None", "id='check-hook-parity' tier=None"] != []`.
  Hook manifest entries are missing the required `tier` field.
- `tests/test_build_phases.py` (2): two failures in the build-phases suite (capture
  exact names on a fresh run; likely output-path / phase-behaviour drift).

Distinguish, per failure: is the DATA wrong (fix `components.json` /
hooks_manifest) or is the TEST stale (relax/update the assertion)? For
`ac_driven_dev` and the missing `tier` fields, the data is the likely culprit —
verify against the minimum-schema and the hooks-manifest schema before changing
either side.

## Acceptance Criteria

```gherkin
Given a fresh origin/main checkout
When the component minimum-schema, hook-manifest tier, and build_phases tests run
Then each passes — either the underlying data (components.json / hooks_manifest)
  is corrected to satisfy the schema, or the test is updated to the current
  intended contract, decided per failure
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_check_components_minimum_schema.py | | |
| AC-2 | test_transform_hooks_and_autofix_emission.py | | |
| AC-3 | test_build_phases.py | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] `test_check_components_minimum_schema`: inspect the `ac_driven_dev` entry vs
      the minimum-schema; fix the entry (or the schema/test) so all current
      entries pass.
- [ ] `test_transform_hooks_and_autofix_emission`: add the missing `tier` field to
      `check-predone-scope` and `check-hook-parity` in the hooks manifest source
      (or update the assertion if `tier` is intentionally optional).
- [ ] `test_build_phases`: capture the two exact failures on a fresh run and fix
      the underlying drift.
- [ ] Run all three modules green.

## Risk & Safety

- Touches money? No.
- Touches data? Edits `components.json` / hooks manifest config — validate against
  their schemas; changes are config-level and reversible.
- Reversibility? Fully reversible.
