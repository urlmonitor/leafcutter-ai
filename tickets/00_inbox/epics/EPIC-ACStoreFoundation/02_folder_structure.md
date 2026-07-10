---
title: "Feature folder naming and ID hierarchy enforcement"
status: todo
components:
  - ac_store
created: 2026-06-05
depends_on:
  - 01_schema_validation.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/commit_guardian/check_ac_schema.py
  - unit_tests/commit_guardian/test_check_ac_folder_structure.py
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_coverage: 0/5
---

# 02: Feature folder naming and ID hierarchy enforcement

## Actor / Goal

In order to navigate the AC store by convention alone, we need folder and ID
naming rules enforced at commit time so that any agent or human can locate
an AC's parent, children, and siblings from its ID without scanning the store.

## Context

The naming convention exists in ac-schema.md but is not enforced. This ticket
adds validation rules to the pre-commit hook that verify folder names match
the PREFIX-NNN-slug pattern and that AC IDs within a folder follow the
hierarchical convention (L0 = PREFIX-NNN, L1 = PREFIX-NNNx, L2 = PREFIX-NNNx-N).

Depends on ticket 01 (schema validation) because ID format validation is a
prerequisite.

## AC References

- Implements ACS-100b-1 (folder naming convention)
- Implements ACS-100b-2 (L0 file uses folder's base ID)
- Implements ACS-100b-3 (L1 ID = L0 + lowercase letter)
- Implements ACS-100b-4 (L2 ID = L1 + hyphen-number)
- Implements ACS-100b-5 (parent-child tree reconstructable from IDs)

## Acceptance Criteria

- [ ] AC-1: Feature folder not matching PREFIX-NNN-kebab-slug is flagged
- [ ] AC-2: L0 file whose ID does not match the folder's PREFIX-NNN is blocked
- [ ] AC-3: L1 file whose ID is not parent-L0-ID + lowercase letter is blocked
- [ ] AC-4: L2 file whose ID is not parent-L1-ID + hyphen + number is blocked
- [ ] AC-5: Given a set of AC files, the tree can be reconstructed purely from ID parsing

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACS-100b-1 | | | |
| ACS-100b-2 | | | |
| ACS-100b-3 | | | |
| ACS-100b-4 | | | |
| ACS-100b-5 | | | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/commit_guardian/test_check_ac_folder_structure.py
    covers: [ACS-100b-1, ACS-100b-2, ACS-100b-3, ACS-100b-4, ACS-100b-5]
    type: unit
    rationale: "Convention enforcement — each rule is independently testable"
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Add folder-name pattern check to the AC validator
- [ ] Add L0/L1/L2 ID-to-folder consistency check
- [ ] Implement tree reconstruction utility function from IDs
- [ ] Write unit tests for each naming rule
- [ ] Verify existing AC store passes (no false positives)

## Risk & Safety

- Touches money? No
- Touches data? No — validation only
- Reversibility? Config key to disable
