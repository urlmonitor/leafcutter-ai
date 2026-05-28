---
title: "EPIC: Flatten Supervisor Chain"
type: epic
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-28
depends_on: []
priority: critical
---

# EPIC: Flatten Supervisor Chain

Restructure the leafcutter supervisor hierarchy so that no agent dispatches sub-agents beyond depth 1 — the hard architectural limit enforced by Claude Code. The main conversation context absorbs epic-supervisor's orchestration role, ticket-supervisors become self-contained depth-1 workers that execute phase work inline (no Agent tool), and phase agent templates become "instruction manuals" loaded via Read.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Absorb epic-supervisor into build-feature.md | Must run at depth 0; workflow is already depth 0 |
| ticket-supervisor has NO Agent tool | Depth-1 sub-agents cannot use Agent — hard constraint |
| Phase templates become instruction manuals | ticket-supervisor reads them via Read and executes inline |
| Research via grep/find not research-agent | research-agent can't be spawned from depth 1 |
| Tests run via Bash directly | test-runner can't be spawned from depth 1 |
| Brainstorm escalation returns to main context | brainstorm-lead needs Agent (to spawn workers), must be depth 1 from depth 0 |
| Keep epic-supervisor.md with deprecation marker | Audit trail |

## Target Architecture

```
/build-feature (depth 0, main context)
  +-- Pre-flight checks (absorbed from epic-supervisor)
  +-- Dependency graph + batch computation
  +-- Dispatch N ticket-supervisors in parallel (depth 1)
  |     \-- Each does ALL phase work inline (code, test, commit, PR)
  |         No Agent tool -- uses Read/Edit/Write/Bash directly
  |         Phase agent templates loaded via Read as instruction manuals
  +-- Brainstorm escalation (dispatch brainstorm-lead at depth 1 when needed)
  |     \-- brainstorm-lead (depth 1) -> brainstorm-workers (depth 2, leaf)
  \-- Post-completion chain (retro, changelog, PR merge, worktree cleanup)
```

## Sub-Tickets

| # | File | Description | Depends On | Status |
|---|------|-------------|------------|--------|
| 01 | [01_rewrite_build_feature.md](./01_rewrite_build_feature.md) | Absorb epic-supervisor logic into build-feature workflow | — | `[ ]` |
| 02 | [02_rewrite_ticket_supervisor.md](./02_rewrite_ticket_supervisor.md) | Make ticket-supervisor self-contained (no Agent tool) | — | `[ ]` |
| 03 | [03_rewrite_building_epics_skill.md](./03_rewrite_building_epics_skill.md) | Update building-epics SKILL.md for flat model | 02 | `[ ]` |
| 04 | [04_update_agent_registry.md](./04_update_agent_registry.md) | Update agent_registry.json spawn topology | 01, 02 | `[ ]` |
| 05 | [05_update_build_single_ticket.md](./05_update_build_single_ticket.md) | Update build-single-ticket skill for brainstorm escalation | 02 | `[ ]` |
| 06 | [06_validate_phase_ordering.md](./06_validate_phase_ordering.md) | Validate phase ordering preserved in rewritten ticket-supervisor | 02, 03 | `[ ]` |
| 07 | [07_adr_diagram_docs.md](./07_adr_diagram_docs.md) | ADR + architecture diagram + runtime-flow doc update | 01, 02, 03, 04 | `[ ]` |

## Dependency Graph

```
01 (build-feature rewrite)
02 (ticket-supervisor rewrite)
  \-- parallel with 01 (different files)
03 (building-epics SKILL) -- depends on 02
04 (agent_registry) -- depends on 01, 02
05 (build-single-ticket) -- depends on 02
06 (validate phase ordering) -- depends on 02, 03
07 (ADR + diagrams + docs) -- depends on 01, 02, 03, 04
```

Tickets 01 and 02 are parallel (disjoint files_touched). Tickets 03, 04, 05 form the second wave. Ticket 06 validates. Ticket 07 documents.

## Acceptance Criteria

1. `/build-feature` on a 2-ticket epic completes end-to-end without depth errors
2. ticket-supervisor.md does not list `Agent` in its tools frontmatter
3. No agent dispatched at depth 1 attempts to use the Agent tool
4. agent_registry.json passes schema validation with updated spawn topology
5. ADR exists documenting the constraint and architectural decision
6. Architecture diagram reflects flat dispatch model
7. building-epics SKILL.md is consistent with the new chain
8. build-single-ticket handles brainstorm escalation return path
