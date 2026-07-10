---
advances_current_outcome: true
agents:
  commit: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  pull-request: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
components:
- knowledge_management
created: '2026-06-22'
depends_on:
- KM-KGS-100d-2
files_touched:
- scripts/knowledge_query.py
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
source_ac: KM-KGS-100d-2-i
status: todo
title: A relationship pointing at a missing target is dropped, not rendered as a dead
  end
---

# A relationship pointing at a missing target is dropped, not rendered as a dead end

## Actor / Goal

As the leafcutter-ai system, I want to implement AC `KM-KGS-100d-2-i` — A relationship pointing at a missing target is dropped, not rendered as a dead end — so that the acceptance criterion is satisfied.

## Context

This ticket was generated from AC store entry `KM-KGS-100d-2-i`. Component: `knowledge-management`. Assigned agent: `python-coder`. Estimated complexity: `S`.

## Acceptance Criteria

```gherkin
Given an acceptance criterion KM-EX-020 whose depends_on names KM-EX-999, an id
  that has no corresponding node in the map
When the knowledge map's edges are validated
Then the candidate edge from KM-EX-020 to KM-EX-999 is not present in the validated
  edge set
And the map still contains every edge of KM-EX-020 whose target does resolve to a
  real node
And the build does not fail solely because one relationship named a missing target
```

## Sign-offs

- [ ] python-coder
- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
