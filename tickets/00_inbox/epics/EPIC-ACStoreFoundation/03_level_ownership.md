---
title: "Flight-level ownership enforcement"
status: todo
components:
  - ac-store
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
  - unit_tests/commit_guardian/test_check_ac_ownership.py
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_coverage: 0/3
---

# 03: Flight-level ownership enforcement

## Actor / Goal

In order to maintain clear responsibility boundaries between PO, BA, and IT PO
agents, we need enforcement that L0/L1 ACs are only authored by PO-class agents
and that parent/child amendments are independent — so that no agent accidentally
overwrites another's domain.

## Context

The ownership model is defined in the PO v3 and BA v3 templates but not enforced
by tooling. This ticket adds validation rules that check origin_agent against
level (L0/L1 must come from PO-class agents) and verifies that amending a child
does not require touching the parent, and vice versa.

## AC References

- Implements ACS-100c-3 (L0/L1 authored by PO-class agents only)
- Implements ACS-100c-4 (child amendment doesn't modify parent)
- Implements ACS-100c-5 (parent amendment doesn't invalidate children)

## Acceptance Criteria

- [ ] AC-1: AC file with level L0 or L1 and origin_agent not in PO-class set emits a warning
- [ ] AC-2: Amending a child AC (adding amended_by entry) does not require any change to its parent
- [ ] AC-3: Amending a parent AC (updating criteria or title) does not change the validity of existing children

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACS-100c-3 | | | |
| ACS-100c-4 | | | |
| ACS-100c-5 | | | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/commit_guardian/test_check_ac_ownership.py
    covers: [ACS-100c-3, ACS-100c-4, ACS-100c-5]
    type: unit
    rationale: "Ownership rules and independence constraints are testable in isolation"
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Define PO-class agent set (product-owner-v3, BrainCandy, human variants)
- [ ] Add origin_agent vs level check (warning, not blocking — existing ACs predate rule)
- [ ] Write independence tests proving parent/child decoupling
- [ ] Verify existing store passes without false positives

## Risk & Safety

- Touches money? No
- Touches data? No
- Reversibility? Advisory mode by default
