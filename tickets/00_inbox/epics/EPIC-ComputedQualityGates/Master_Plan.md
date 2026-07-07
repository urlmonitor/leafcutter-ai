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
       ↓
07_wire_computed_agents_map (plumbing + vocab reconciliation) ✅ landed PR #201
  ↓
08_ac_axes_schema_and_generator_emit (axes as AC fields + generator emits them)
  └→ 10_backfill_ac_axes_and_real_store_e2e (backfill store + e2e gate)
```

> Ticket 09 (it-po-v3 authors axes for *new* ACs) was **pulled out of this epic on
> 2026-07-07** into standalone `tickets/00_inbox/TICKET-20260707-ItPoV3AuthorsAxes.md`
> — it was blocked on the it-po-v3 source reaching `main`, so the epic finalized without
> it. Drive that standalone ticket once the unblock condition is met.

> Post-drive review (2026-07-01) found the epic phantom-done: ticket 07 landed the
> plumbing but the feature is inert on real ACs until 08 + 10 land (real AC records
> carry no axes). See tickets 08/09/10 and ADR-017.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_adr_computed_quality_gates.md](./01_adr_computed_quality_gates.md) | ADR: computed-quality-gates design (two-axis classification, guardrail-gates mapping, Python computation) | `[ ]` |
| 02 | [02_change_classification_frontmatter.md](./02_change_classification_frontmatter.md) | Add change_target + risk_surface frontmatter fields + guard validation | `[ ]` |
| 03 | [03_guardrail_mapping_table.md](./03_guardrail_mapping_table.md) | Machine-readable guardrail mapping table: (change_target, risk_surface) → agent gates | `[ ]` |
| 04 | [04_compute_agents_map.md](./04_compute_agents_map.md) | Compute + materialize agents map in Python; fix TDD bug (emit ## Test Requirements) | `[ ]` |
| 05 | [05_flow_change_gates.md](./05_flow_change_gates.md) | Flow-change gates: architect + docs before coder | `[ ]` |
| 06 | [06_test_constraints_and_complexity.md](./06_test_constraints_and_complexity.md) | Test constraints + complexity-driven model tier selection | `[ ]` |
| 07 | [07_wire_computed_agents_map.md](./07_wire_computed_agents_map.md) | Wire computed agents-map into the real generator; reconcile guard↔YAML vocabulary; consume flow_change_gates; deterministic ordering; end-to-end test (fixes phantom-done from post-drive review) | `[x]` done — PR #201 |
| 08 | [08_ac_axes_schema_and_generator_emit.md](./08_ac_axes_schema_and_generator_emit.md) | Add change_target/risk_surface to AC schema + validation; generator emits axes into tickets; fold review findings H-1/M-1/M-2/M-3 | `[ ]` |
| 09 | _pulled out → `tickets/00_inbox/TICKET-20260707-ItPoV3AuthorsAxes.md`_ | it-po-v3 authors the axes during enrichment — removed from epic 2026-07-07 (was blocked on it-po-v3 source) | _standalone_ |
| 10 | [10_backfill_ac_axes_and_real_store_e2e.md](./10_backfill_ac_axes_and_real_store_e2e.md) | Backfill existing AC store with axes (agent-classified, batch-reviewed) + real-store end-to-end computed-map test | `[x]` |
