---
title: "Full schema validation at commit time"
status: todo
components:
  - ac-store
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/commit_guardian/check_ac_schema.py
  - config/ac_store_schema.json
  - unit_tests/commit_guardian/test_check_ac_schema.py
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_coverage: 0/6
---

# 01: Full schema validation at commit time

## Actor / Goal

In order to prevent malformed AC files from entering the store, we need
a pre-commit hook that validates every staged AC YAML file against the
full schema so that downstream agents and tools can rely on field presence,
types, and constraints.

## Context

`check_ac_schema.py` already exists and validates basic field presence.
This ticket extends it to cover the full v3 schema: regex patterns on IDs,
enum constraints on status, conditional requirements (superseded_by must be
non-null when status is superseded_by), and rejection of unknown properties.

## AC References

- Implements ACS-100a-1 (required fields reject missing values)
- Implements ACS-100a-2 (ID field enforces PREFIX-NNN regex)
- Implements ACS-100a-3 (status field enum enforcement)
- Implements ACS-100a-4 (additional properties rejected)
- Implements ACS-100a-5 (superseded_by conditional constraint)
- Implements ACS-100a-6 (dangling depends_on/expects_from blocked)

## Acceptance Criteria

- [ ] AC-1: Staged AC file missing a required field is blocked with diagnostic naming the field
- [ ] AC-2: AC file with ID not matching `^[A-Z]{2,6}-[0-9]{3}` (or v3 hierarchical format) is blocked
- [ ] AC-3: AC file with status value outside {active, deprecated, superseded_by} is blocked
- [ ] AC-4: AC file with unexpected top-level keys is blocked with diagnostic listing the keys
- [ ] AC-5: AC file with status: superseded_by but null superseded_by field is blocked
- [ ] AC-6: AC file with depends_on referencing non-existent AC ID is blocked

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACS-100a-1 | | | |
| ACS-100a-2 | | | |
| ACS-100a-3 | | | |
| ACS-100a-4 | | | |
| ACS-100a-5 | | | |
| ACS-100a-6 | | | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/commit_guardian/test_check_ac_schema.py
    covers: [ACS-100a-1, ACS-100a-2, ACS-100a-3, ACS-100a-4, ACS-100a-5, ACS-100a-6]
    type: unit
    rationale: "Each AC maps to a distinct validation rule; unit tests exercise each in isolation"
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Extend ac_store_schema.json with v3 fields (level, req_status, work_status, etc.)
- [ ] Add regex pattern validation for id field
- [ ] Add conditional validation for superseded_by
- [ ] Add unknown-property rejection
- [ ] Implement dangling-reference check (depends_on, expects_from.ac_id)
- [ ] Write unit tests covering all 6 ACs
- [ ] Verify hook integrates with pre-commit pipeline

## Risk & Safety

- Touches money? No
- Touches data? No — validation only, never modifies AC files
- Reversibility? Hook can be disabled via commit_guardian.json config key
