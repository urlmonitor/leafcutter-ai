---
title: "EPIC: Computed Quality Gates"
type: epic
status: todo
components:
  - infrastructure
created: 2026-07-01
depends_on: []
priority: high
---

# EPIC: Computed Quality Gates

Make quality gates (TDD, reviewers, docs) a COMPUTED system invariant. The ticket-supervisor's agent map should be computed from what a change touches + the work agent's traits, instead of a one-field template. TDD becomes automatic for any code-producing agent.

## Dependency Graph

```
01_adr_computed_quality_gates
  ↓
02_change_classification_frontmatter
  ↓
03_guardrail_mapping_table
  ↓
04_compute_agents_map (+ fix TDD bug)
  ├→ 05_flow_change_gates
  └→ 06_test_constraints_and_complexity
```

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_adr_computed_quality_gates.md](./01_adr_computed_quality_gates.md) | ADR: computed-quality-gates design (two-axis classification, guardrail-gates mapping, Python computation) | `[ ]` |
| 02 | [02_change_classification_frontmatter.md](./02_change_classification_frontmatter.md) | Add change_target + risk_surface frontmatter fields + guard validation | `[ ]` |
| 03 | [03_guardrail_mapping_table.md](./03_guardrail_mapping_table.md) | Machine-readable guardrail mapping table: (change_target, risk_surface) → agent gates | `[ ]` |
| 04 | [04_compute_agents_map.md](./04_compute_agents_map.md) | Compute + materialize agents map in Python; fix TDD bug (emit ## Test Requirements) | `[ ]` |
| 05 | [05_flow_change_gates.md](./05_flow_change_gates.md) | Flow-change gates: architect + docs before coder | `[ ]` |
| 06 | [06_test_constraints_and_complexity.md](./06_test_constraints_and_complexity.md) | Test constraints + complexity-driven model tier selection | `[ ]` |
