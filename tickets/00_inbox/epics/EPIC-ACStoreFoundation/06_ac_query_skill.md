---
title: "AC query skill for pipeline agents"
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
  - templates/skills/ac-query/SKILL.md
  - templates/skills/ac-query/scripts/ac_query.py
  - unit_tests/skills/test_ac_query.py
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
ac_coverage: 0/5
---

# 06: AC query skill for pipeline agents

## Actor / Goal

In order to let pipeline agents find relevant ACs without scanning the entire
store manually, we need a query skill that supports filtering by level, parent
chain traversal, ticket lookup, compound filters, and children lookup — so that
agents like the BA v3, IT PO v3, and ticket-supervisor can operate on specific
subsets of the AC store efficiently.

## Context

Currently agents read AC files by globbing directories. This ticket creates a
proper query interface (Python script + skill wrapper) that the AC-driven
development pipeline will depend on heavily.

## AC References

- Implements ACS-100f-1 (query by flight level)
- Implements ACS-100f-2 (parent chain traversal up to L0)
- Implements ACS-100f-3 (related ticket lookup)
- Implements ACS-100f-4 (compound filter with AND)
- Implements ACS-100f-5 (children lookup by depends_on)

## Acceptance Criteria

- [ ] AC-1: Query with level=L2 returns only ACs where level field is L2
- [ ] AC-2: Parent-chain query on an L2 returns [L1-parent, L0-grandparent] in order
- [ ] AC-3: Ticket lookup for a path returns all ACs with that path in created_by or amended_by
- [ ] AC-4: Compound filter (level=L2 AND component=ac-store) returns intersection
- [ ] AC-5: Children query on an L1 returns all ACs whose depends_on includes that L1's ID

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACS-100f-1 | | | |
| ACS-100f-2 | | | |
| ACS-100f-3 | | | |
| ACS-100f-4 | | | |
| ACS-100f-5 | | | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/skills/test_ac_query.py
    covers: [ACS-100f-1, ACS-100f-2, ACS-100f-3, ACS-100f-4, ACS-100f-5]
    type: unit
    rationale: "Each query operation is independently testable with fixture AC files"
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Create templates/skills/ac-query/ directory structure
- [ ] Implement ac_query.py with filter, traverse, and lookup functions
- [ ] Write SKILL.md with trigger description and usage examples
- [ ] Register in skill_registry.json
- [ ] Write unit tests using temporary AC fixtures
- [ ] Verify build deploys the skill

## Risk & Safety

- Touches money? No
- Touches data? Read-only queries against AC YAML files
- Reversibility? Skill can be unregistered without data impact
