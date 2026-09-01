---
title: "Authorship tracking fields validation"
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
  - config/ac_store_schema.json
  - unit_tests/commit_guardian/test_check_ac_authorship.py
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
ac_coverage: 0/4
---

# 04: Authorship tracking fields validation

## Actor / Goal

In order to trace every AC back to its creator and track its amendment history,
we need the schema to enforce that origin_agent is present and amended_by
accumulates correctly — so that audit and retrospective tooling can reconstruct
the full provenance chain.

## Context

The fields exist in the schema but have no behavioral enforcement. This ticket
ensures origin_agent is always a non-empty string, created_by links to a valid
path (when present), and amended_by only grows (entries are never removed).

## AC References

- Implements ACS-100d-1 (origin_agent records creating agent identity)
- Implements ACS-100d-2 (created_by links to originating ticket path)
- Implements ACS-100d-3 (amended_by accumulates ticket paths)
- Implements ACS-100d-4 (origin_agent accepts any string, no closed enum)

## Acceptance Criteria

- [ ] AC-1: AC file with empty or missing origin_agent is blocked
- [ ] AC-2: AC file with created_by pointing to non-existent path emits advisory
- [ ] AC-3: AC file whose amended_by shrinks (entry removed vs previous commit) is blocked
- [ ] AC-4: origin_agent with any non-empty string value passes (no enum restriction)

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACS-100d-1 | | | |
| ACS-100d-2 | | | |
| ACS-100d-3 | | | |
| ACS-100d-4 | | | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/commit_guardian/test_check_ac_authorship.py
    covers: [ACS-100d-1, ACS-100d-2, ACS-100d-3, ACS-100d-4]
    type: unit
    rationale: "Field presence and accumulation rules each testable independently"
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Add origin_agent non-empty validation
- [ ] Add created_by path existence advisory check
- [ ] Add amended_by monotonic-growth check (compare against git HEAD version)
- [ ] Verify origin_agent has no enum constraint (open string)
- [ ] Write tests for each rule

## Risk & Safety

- Touches money? No
- Touches data? No
- Reversibility? Config key to disable
