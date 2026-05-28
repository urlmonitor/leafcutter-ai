---
title: "ADR + architecture diagram + runtime-flow doc update"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_rewrite_build_feature.md
  - 02_rewrite_ticket_supervisor.md
  - 03_rewrite_building_epics_skill.md
  - 04_update_agent_registry.md
priority: medium
requires_diagram: true
requires_adr: true
files_touched:
  - docs/agentic-runtime-flow.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  change-scope-reviewer: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: needed
  architecture-diagram-author: needed
user_facing_surface: null
---

# 07: ADR + architecture diagram + runtime-flow doc update

## Goal

Document the flattened supervisor architecture with an ADR, a C4 architecture diagram, and updated runtime-flow documentation.

## Context

The supervisor chain has been flattened (tickets 01-04). This ticket captures the architectural decision and updates all documentation to reflect the new topology.

## Requirements

### ADR
Write an ADR documenting:
- **Status**: Accepted
- **Context**: Claude Code's hard depth-1 nesting limit makes the 3-level chain (epic-supervisor -> ticket-supervisor -> phase-agents) impossible
- **Decision**: Absorb epic-supervisor into build-feature workflow (depth 0), make ticket-supervisor self-contained with no Agent tool (depth 1), phase agent templates become instruction manuals read via Read tool
- **Consequences**: 
  - Loss of dedicated agent boundaries per phase (acceptable — all were Sonnet anyway)
  - Ticket-supervisor context window grows per phase (mitigated by read-on-demand)
  - Brainstorm escalation requires round-trip to main context
  - Code search uses grep/find instead of research-agent MCP tools
- **Alternatives considered**:
  - Option B: Flatten epic-supervisor but keep ticket-supervisor dispatching phase agents (fails because phase agents at depth 2 can't spawn research-agent at depth 3)
  - Option C: Rewrite all phase agents as skills instead of agents (too large a change, breaks the template modularity)

### Architecture diagram (C4 agent_flow)
Create a diagram showing:
- build-feature workflow as the coordinator (depth 0)
- ticket-supervisors as self-contained workers (depth 1)
- Phase agent templates as instruction sources (dashed lines = "reads")
- brainstorm-lead dispatched by main context (depth 1)
- brainstorm-workers as leaf nodes (depth 2)

### docs/agentic-runtime-flow.md update
- Update sequence diagrams to show build-feature dispatching ticket-supervisors directly
- Remove epic-supervisor -> ticket-supervisor dispatch edge
- Remove ticket-supervisor -> phase-agent dispatch edges
- Add ticket-supervisor -> template Read edges
- Update spawn graph (mermaid)
- Update failure adjudication diagram for brainstorm return path

## Architecture Plan

```yaml
diagram_type: agent_flow
related_agents:
  - build-feature (workflow)
  - ticket-supervisor
  - brainstorm-lead
  - brainstorm-worker
  - epic-supervisor (deprecated)
flight_level: L2
```

## Out of Scope

- Changing any template or registry (done in tickets 01-04)
- Writing how-to guides (separate ticket if needed)

## Acceptance Criteria

1. ADR exists with Status, Context, Decision, Consequences, Alternatives sections
2. C4 agent_flow diagram shows the flat dispatch model
3. docs/agentic-runtime-flow.md sequence diagrams reflect the new architecture
4. No reference to epic-supervisor as an active dispatched agent in the updated docs

## Sign-offs

- [ ] adr-author
- [ ] architecture-diagram-author
- [ ] documentation-expert
- [ ] change-scope-reviewer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

_No comments yet._
