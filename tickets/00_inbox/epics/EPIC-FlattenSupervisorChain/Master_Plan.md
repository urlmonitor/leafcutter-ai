---
title: "EPIC: Flatten Supervisor Chain"
type: epic
status: todo
components:
  - build_pipeline
created: 2026-05-29
depends_on: []
priority: high
---

# EPIC: Flatten Supervisor Chain

Eliminate the epic-supervisor → ticket-supervisor → phase-agent nesting that
exceeds Claude Code's hard depth-1 Agent-tool limit. The fix moves
`ticket-supervisor` to depth 0 (dispatched directly by `/build-feature`) so
phase agents run at depth 1, which is within the allowed budget.

`epic-supervisor` is retained but deprecated: existing worktrees that reference
it still function; all new invocations go through `/build-feature` → `ticket-supervisor`
directly.

Previous attempt (PR #22, EPIC-FlattenSupervisorChain) was reverted because it
incorrectly made `ticket-supervisor` an inline executor that read templates instead of
spawning agents. This epic corrects the design: `ticket-supervisor` keeps its Agent
dispatch role, just moves up one nesting level.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_update_ticket_supervisor_template.md](./01_update_ticket_supervisor_template.md) | Update ticket-supervisor template: spawn_allowlist, tools, spawned_by, remove epic-supervisor dependency | `[ ]` |
| 02 | [02_update_build_feature_workflow.md](./02_update_build_feature_workflow.md) | Update build-feature workflow to dispatch ticket-supervisor directly at depth 0 | `[ ]` |
| 03 | [03_update_agent_registry.md](./03_update_agent_registry.md) | Update agent_registry.json spawn topology: ticket-supervisor spawned_by user, epic-supervisor deprecated | `[ ]` |
| 04 | [04_update_building_epics_skill.md](./04_update_building_epics_skill.md) | Update building-epics SKILL.md §1 to document new flat dispatch model | `[ ]` |
| 05 | [05_deprecate_epic_supervisor.md](./05_deprecate_epic_supervisor.md) | Mark epic-supervisor template as deprecated with migration note | `[ ]` |
| 06 | [06_write_adr.md](./06_write_adr.md) | Write ADR-006 documenting the flatten-supervisor-chain decision and rationale | `[ ]` |
| 07 | [07_update_architecture_diagram.md](./07_update_architecture_diagram.md) | Update agent_flow architecture diagram for new spawn topology | `[ ]` |

## Dependency Graph

```
06 (ADR — documents the decision, must exist before code changes reference it)
└── 01 (ticket-supervisor template — depends on ADR rationale)
    ├── 02 (build-feature workflow — depends on updated ticket-supervisor)
    ├── 03 (agent_registry — depends on 01 to know correct spawn_allowlist)
    └── 04 (building-epics skill — depends on 01 for accurate dispatch description)
        └── 05 (epic-supervisor deprecation — depends on 04 to reference new skill)
07 (architecture diagram — depends on 03 for finalized topology, parallel with 05)
```

Execution order: 06 → 01 → {02, 03, 04} in parallel → 05 → 07

## Notes

- `epic-supervisor` is NOT deleted in this epic — only deprecated. Removal is a
  separate future ticket once all adopters have migrated.
- The `build-feature` workflow currently has two paths: epic-path (→ epic-supervisor)
  and single-ticket path (→ build-single-ticket → ticket-supervisor). The single-ticket
  path already dispatches ticket-supervisor at depth 0. Ticket 02 ensures the epic
  path does the same.
- Claude Code hard-limit reference: depth-1 nesting cap is documented in
  user memory `agent_nesting_limit.md`.
