---
title: "Pre-commit hook: check-mermaid-complexity"
status: todo
components:
  - commit_guardian
created: 2026-05-26
last_updated: 2026-05-26
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - templates/commit-guardian/check_mermaid_complexity.py
  - templates/commit-guardian/commit_guardian.json
  - templates/commit-guardian/config.py
  - scripts/commit_guardian/check_mermaid_complexity.py
  - scripts/commit_guardian/commit_guardian.json
  - scripts/commit_guardian/config.py
agents:
  architect-review: not_needed
  python-coder: needed
  test-writer: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  sql-coder: not_needed
---

# 01: Pre-commit hook — check-mermaid-complexity

## Goal

Create a deterministic pre-commit hook that parses every mermaid block in staged
`.md` files, counts structural elements (nodes, edges, participants, subgraphs),
and warns or blocks when configurable thresholds are exceeded.

## Context

The existing pre-commit infrastructure has 27 hooks registered in
`commit_guardian.json`. This hook follows the same pattern: a Python script in
`templates/commit-guardian/`, registered in the hooks manifest, with config
constants in `config.py`. The `create-hook` skill documents the 7-step
scaffolding process.

There is no existing complexity measurement for Mermaid diagrams. The only
related threshold is the ">15 lifeline" escape hatch in write-c4-diagram §9,
which triggers a format switch (Mermaid → PlantUML), not a split. This hook
measures complexity to encourage splitting into multiple Mermaid diagrams.

## Acceptance Criteria

```gherkin
Given a staged .md file contains a mermaid flowchart block with >15 nodes
When git commit runs
Then the hook prints a warning naming the file, diagram type, and metric exceeded

Given a staged .md file contains a sequenceDiagram with >8 participants
When git commit runs
Then the hook prints a warning suggesting the diagram be split

Given a staged .md file contains a mermaid block with >4 subgraphs/boundaries
When git commit runs
Then the hook prints a warning about excessive context mixing

Given commit_guardian.json has mermaid_complexity.strict set to true
When any threshold is exceeded
Then the hook exits 1 (blocking the commit)

Given mermaid_complexity.strict is false (default)
When any threshold is exceeded
Then the hook exits 0 (warning only, commit proceeds)

Given the commit message contains [NO-COMPLEXITY-CHECK]
When any threshold is exceeded
Then the hook skips all checks and exits 0
```

## Implementation Details

### Diagram type detection

Identify diagram type from the first non-empty line after the mermaid fence:
- `flowchart` / `graph` → flowchart
- `C4Context` / `C4Container` / `C4Component` → C4
- `sequenceDiagram` → sequence
- `erDiagram` → ERD
- `stateDiagram-v2` / `stateDiagram` → state
- `classDiagram` → class

### Element counting (regex patterns)

**Flowchart/C4 nodes:**
- C4 macros: `Component(`, `Container(`, `ContainerDb(`, `System(`, `System_Ext(`, `Person(`, `Person_Ext(`
- Flowchart nodes: lines matching `^\s*\w+[\[\(\{>]` (node-id followed by shape delimiter)

**Flowchart/C4 edges:**
- Flowchart arrows: `-->`, `---`, `-.->`, `==>` (count lines containing these)
- C4 relationships: `Rel(`, `BiRel(`, `Rel_D(`, `Rel_U(`, `Rel_L(`, `Rel_R(`

**Sequence participants:** lines matching `^\s*participant\s`

**Sequence interactions:** lines containing `->>`, `-->>`, `--)`, `--)`

**ERD tables:** lines matching `^\s*\w+\s*\{` (entity name before opening brace)

**State states:** lines matching `^\s*\w+\s*:` or `^\s*state\s` or `\[\*\]`

**Class classes:** lines matching `^\s*class\s+\w+`

**Subgraphs/boundaries (all types):** `subgraph`, `System_Boundary(`, `Container_Boundary(`, `Boundary(`

### Thresholds (configurable via commit_guardian.json)

| Type | Metric | Config Key | Default |
|---|---|---|---|
| flowchart/C4 | nodes | `max_nodes` | 15 |
| flowchart/C4 | edges | `max_edges` | 20 |
| sequence | participants | `max_participants` | 8 |
| sequence | interactions | `max_interactions` | 25 |
| ERD | tables | `max_tables` | 12 |
| state | states | `max_states` | 10 |
| class | classes | `max_classes` | 10 |
| all | boundaries | `max_boundaries` | 4 |

### Output format

```
WARNING: docs/architecture/components/c3-005-auth-flow.md
  mermaid block 1 (sequenceDiagram): 12 participants (threshold: 8)
  Consider splitting this diagram into separate concerns.
```

## Sign-offs

- [ ] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Test Requirements

- Unit test: parse sample mermaid blocks of each type, verify element counts
- Unit test: verify warn-only mode exits 0 with warnings printed
- Unit test: verify strict mode exits 1 when threshold exceeded
- Unit test: verify bypass via [NO-COMPLEXITY-CHECK] in commit message
- Unit test: verify clean diagrams (below all thresholds) produce no output
