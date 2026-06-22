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
- knowledge-management
created: '2026-06-22'
depends_on:
- KM-KGS-100a-2
files_touched:
- scripts/knowledge_query.py
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
source_ac: KM-KGS-100a-2-i
status: todo
title: Non-criterion and unparseable files under the acs surface produce no spurious
  nodes
---

# Non-criterion and unparseable files under the acs surface produce no spurious nodes

## Actor / Goal

As the leafcutter-ai system, I want to implement AC `KM-KGS-100a-2-i` — Non-criterion and unparseable files under the acs surface produce no spurious nodes — so that the acceptance criterion is satisfied.

## Context

This ticket was generated from AC store entry `KM-KGS-100a-2-i`. Component: `knowledge-management`. Assigned agent: `python-coder`. Estimated complexity: `S`.

## Acceptance Criteria

```gherkin
Given the "acs" surface directory contains, besides valid criterion files,
  one file with no id field and one file whose frontmatter cannot be parsed
When the knowledge map is built
Then no node is created for the file lacking an id field
And no node is created for the unparseable file
And the build completes and still produces the nodes for every valid
  criterion file in the same directory
```

## Sign-offs

- [ ] python-coder
- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
