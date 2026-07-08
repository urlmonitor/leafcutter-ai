---
title: "Package-surface ACs must carry a machine-checkable implementation spec"
status: todo
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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
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
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### python-coder
- [ ] Extend the AC store schema (`config/ac_store_schema.json`) to require the impl fields for package-surface ACs (conditional on assigned_agent python-coder + build_pipeline/build-orchestration component). Read the schema fully first.
- [ ] Extend the AC validator to reject an unresolvable reference-file path / registration entry missing required keys.
- [ ] Add the obligation statement to `templates/agents/it-po.md`.

## Risk & Safety

- Touches money? No.
- Touches data? Schema/validator change — affects AC authoring at commit time; additive and backward-compatible for non-package-surface ACs.
- Reversibility? Fully reversible via git.
