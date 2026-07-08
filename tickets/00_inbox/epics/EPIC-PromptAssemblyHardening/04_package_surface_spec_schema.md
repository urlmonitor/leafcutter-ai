---
title: "Package-surface ACs must carry a machine-checkable implementation spec"
status: in_progress
components:
  - ac_store
  - product_ownership
created: 2026-07-08
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: schema
risk_surface: contract_boundary
test_constraints: unit_only
complexity: medium
ac_coverage: 0/4
files_touched:
  - config/ac_store_schema.json
  - scripts/ac_store/validate_ac.py
  - templates/agents/it-po.md
  - unit_tests/prompt_assembly/test_package_surface_spec.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 04: Package-surface ACs must carry a machine-checkable implementation spec

## Actor / Goal

In order that a package-surface AC can never reach a coder without a real, checkable
spec, the AC schema must require the implementation-requirement fields for such ACs,
a validator must reject a thin or fictional entry, and the IT-PO template must state
the obligation — so the spec is validated at authoring time, before dispatch.

## Context

For ACs that touch the package surface (assigned to `python-coder` in the
`build_pipeline` / `build-orchestration` components), the `it_requirements` MUST carry
the config-schema fragment, resolved reference-file path, N-location rule, required
skills, and post-write commands. Today none of this is enforced, so a fictional
registration reference (the `check_hook_parity` defect: a `script` field that does not
exist, an unresolvable path) passes silently. A slice of
[EPIC-PromptAssemblyHardening](./Master_Plan.md). Confirm the exact schema/validator
paths against the repo before editing (`config/ac_store_schema.json` was refreshed
2026-07-08).

## AC References

Implements L1 **BO-2000d** and its leaves: BO-2000d-1, BO-2000d-1-i, BO-2000d-2,
BO-2000d-3. Canonical source: the BO-2000 AC folder.

## Acceptance Criteria

- [ ] AC-1 (BO-2000d-1): the AC schema requires the implementation-requirement fields (config-schema fragment, reference-file path, N-location rule, required skills, post-write commands) for package-surface ACs.
- [ ] AC-2 (BO-2000d-1-i): a non-package-surface AC is unaffected (fields remain optional).
- [ ] AC-3 (BO-2000d-2): the validator rejects a thin/fictional package-surface spec — e.g. an unresolvable reference-file path or a registration entry missing required keys — at authoring time.
- [ ] AC-4 (BO-2000d-3): the `it-po` agent template states the obligation to populate these fields for package-surface ACs.

## Test Requirements

```yaml
tests:
  - name: test_schema_requires_impl_fields_for_package_surface_ac
    file: unit_tests/prompt_assembly/test_package_surface_spec.py
    covers: [BO-2000d-1, BO-2000d-1-i]
    asserts: "a package-surface AC missing the impl fields fails schema validation; a non-package-surface AC without them passes."
  - name: test_validator_rejects_fictional_reference
    file: unit_tests/prompt_assembly/test_package_surface_spec.py
    covers: [BO-2000d-2]
    asserts: "an unresolvable reference-file path (or a registration entry missing required keys) is rejected by the validator."
  - name: test_it_po_template_states_obligation
    file: unit_tests/prompt_assembly/test_package_surface_spec.py
    covers: [BO-2000d-3]
    asserts: "templates/agents/it-po.md text states the package-surface impl-field obligation."
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_package_surface_spec.py:test_schema_requires_impl_fields_for_package_surface_ac | Added if/then conditional to ac_store_schema.json requiring object it_requirements for package-surface ACs | |
| AC-2 | test_package_surface_spec.py:test_schema_requires_impl_fields_for_package_surface_ac | Same schema if/then: non-package-surface ACs unaffected (fields remain optional) | |
| AC-3 | test_package_surface_spec.py:test_validator_rejects_fictional_reference, test_validator_rejects_registration_entry_missing_required_keys | Created scripts/ac_store/validate_ac.py with validate_package_surface_spec() rejecting fictional paths and missing keys | |
| AC-4 | test_package_surface_spec.py:test_it_po_template_states_obligation | Added Package-surface AC obligation section to templates/agents/it-po.md §2.3 | |

## Sign-offs

- [x] test-writer — 2026-07-08 10:00
- [x] python-coder — 2026-07-08 10:30
- [x] test-runner — 2026-07-08 10:45
- [x] pr-reviewer — 2026-07-08 11:00
- [ ] commit
- [ ] pull-request

## Comments

### 2026-07-08 10:00 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_file_created: true
  tests_red_verified: true
  ac_coverage_table_filled: true
red_baseline:
  - test_name: test_schema_requires_impl_fields_for_package_surface_ac
    file: unit_tests/prompt_assembly/test_package_surface_spec.py
    error: "AssertionError: Expected schema to reject a package-surface AC with thin it_requirements, but no validation error was produced. The schema conditional enforcement is not yet implemented."
  - test_name: test_validator_rejects_fictional_reference
    file: unit_tests/prompt_assembly/test_package_surface_spec.py
    error: "ImportError: cannot import name 'validate_package_surface_spec' from 'scripts.ac_store.validate_ac'"
  - test_name: test_validator_rejects_registration_entry_missing_required_keys
    file: unit_tests/prompt_assembly/test_package_surface_spec.py
    error: "ImportError: cannot import name 'validate_package_surface_spec' from 'scripts.ac_store.validate_ac'"
  - test_name: test_it_po_template_states_obligation
    file: unit_tests/prompt_assembly/test_package_surface_spec.py
    error: "AssertionError: it-po.md must contain the term 'package-surface' as part of the obligation to populate impl fields. The obligation statement is not yet present."
Created unit_tests/prompt_assembly/test_package_surface_spec.py with 4 failing test stubs covering all 4 ACs; verified RED (4 FAILED without AC enforcement plugin). AC enforcement plugin converts to XFAIL correctly. Red baseline captured above for python-coder handoff.

### 2026-07-08 10:30 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  schema_conditional_added: true
  validate_ac_created: true
  it_po_obligation_added: true
  all_tests_green: true
  ruff_clean: true
Extended config/ac_store_schema.json with if/then conditional (AC-1, AC-2): package-surface ACs now require a structured it_requirements object with 5 required fields; non-package-surface ACs are unaffected. Created scripts/ac_store/validate_ac.py with validate_package_surface_spec() that rejects fictional reference_file_path and missing required keys (AC-3). Added Package-surface AC obligation section to templates/agents/it-po.md §2.3 with explicit reference to package-surface, it_requirements, and reference_file_path (AC-4). All 4 tests now PASSED; ruff clean.

### 2026-07-08 10:45 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  target_tests_green: true
  no_regressions: true
Ran unit_tests/prompt_assembly/ (19 tests, 19 passed, 0 failed) and unit_tests/ac_store/ (279 passed, 1 skipped, 0 failed). All 4 new ticket tests pass without enforcement plugin. No regressions from schema changes.

### 2026-07-08 11:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac1_covered: true
  ac2_covered: true
  ac3_covered: true
  ac4_covered: true
  backward_compatible: true
  error_handling_compliant: true
  ruff_clean: true
All 4 ACs are implemented and tested. Schema if/then conditional is backward-compatible. validate_ac.py uses specific exception types and proper error reporting. it-po.md obligation section is clear and actionable. No blockers — approved.

## Implementation Tasks

### python-coder
- [x] Extend the AC store schema (`config/ac_store_schema.json`) to require the impl fields for package-surface ACs (conditional on assigned_agent python-coder + build_pipeline/build-orchestration component). Read the schema fully first.
- [x] Extend the AC validator to reject an unresolvable reference-file path / registration entry missing required keys.
- [x] Add the obligation statement to `templates/agents/it-po.md`.

## Risk & Safety

- Touches money? No.
- Touches data? Schema/validator change — affects AC authoring at commit time; additive and backward-compatible for non-package-surface ACs.
- Reversibility? Fully reversible via git.
