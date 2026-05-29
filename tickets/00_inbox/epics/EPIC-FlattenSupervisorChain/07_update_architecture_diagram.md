---
title: "Update agent_flow architecture diagram for flattened spawn topology"
status: todo
components:
  - build_pipeline
created: 2026-05-29
depends_on:
  - 03_update_agent_registry.md
  - 05_deprecate_epic_supervisor.md
priority: low
requires_diagram: true
requires_adr: false
files_touched:
  - docs/architecture/components/supervisor-spawn-topology.md
agents:
  architect-review: not_needed
  architecture-diagram-author: signed_off
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
roadmap_phase: phase_1
advances_current_outcome: false
---

# 07: Update agent_flow architecture diagram for flattened spawn topology

## Goal

In order to keep the architecture documentation accurate after the supervisor
chain is flattened, we need to create or update the `agent_flow` diagram that
shows the supervisor spawn topology, replacing the old three-level chain with
the new two-level flat chain.

## Context

After tickets 01–06 land:

- The old topology: `user → epic-supervisor → ticket-supervisor → phase agents`
- The new topology: `user → /build-feature → ticket-supervisor → phase agents`

A Mermaid `agent_flow` diagram at `docs/architecture/components/supervisor-spawn-topology.md`
should reflect this. If the file does not exist, create it.

Depends on ticket 03 (finalized registry topology) and ticket 05 (deprecated
epic-supervisor) being complete so the diagram reflects the final settled state.

## Architecture Plan

### Diagrams

- `agent_flow` diagram at `docs/architecture/components/supervisor-spawn-topology.md` (parent: `docs/architecture/components/`)

## Acceptance Criteria

```gherkin
Given docs/architecture/components/supervisor-spawn-topology.md is written
When the frontmatter is read
Then diagram_type is "agent_flow"
And status is "accepted"

Given the diagram body contains a Mermaid block
When the spawn arrows are inspected
Then /build-feature → ticket-supervisor (depth 0) is shown
And ticket-supervisor → phase agents (depth 1) is shown
And epic-supervisor appears only as DEPRECATED with no active spawn arrows to ticket-supervisor

Given the diagram is built by build.py
When the output is inspected
Then no validation errors are emitted for the diagram_type
```

## Sign-offs

- [x] architecture-diagram-author — 2026-05-29 12:00
- [x] pr-reviewer — 2026-05-29 12:01
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-29 12:00 — architecture-diagram-author (status: ok)
feedback-id: fb_2026-05-29_a4b06419
Created docs/architecture/components/supervisor-spawn-topology.md from scratch (directory did not exist). Wrote Mermaid flowchart TD agent_flow diagram showing the flattened two-tier spawn topology with ADR-006 reference. Frontmatter includes diagram_type: agent_flow, status: accepted, components: [build_pipeline], created: 2026-05-29. build-self.sh produced no doc-frontmatter validation errors.

### 2026-05-29 12:01 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_fd70e035
All acceptance criteria pass: diagram_type agent_flow and status accepted present in frontmatter; /build-feature → ticket-supervisor (depth 0) and ticket-supervisor → phase agents (depth 1) shown with solid arrows; epic-supervisor marked DEPRECATED with dashed legacy-only arrow (no active spawn path); ADR-006 referenced in overview and references section; build-self.sh clean. Approved for commit.

## Implementation Tasks

- [x] Check whether `docs/architecture/components/supervisor-spawn-topology.md` exists; if yes, read it; if no, create from scratch
- [x] Author a Mermaid `flowchart TD` diagram in an `agent_flow` format:
  ```
  user -->|/build-feature| build_feature[/build-feature workflow]
  build_feature -->|depth 0| ticket_supervisor[ticket-supervisor]
  ticket_supervisor -->|depth 1| phase_agents[phase agents\narchitect-review, python-coder, etc.]
  epic_supervisor["epic-supervisor (DEPRECATED)"] -.->|legacy only| ticket_supervisor
  ```
- [x] Write the file with valid doc frontmatter: `diagram_type: agent_flow`, `status: accepted`, `components: [build_pipeline]`, `created: 2026-05-29`
- [x] Reference ADR-006 in the doc body
- [x] Run `./build-self.sh` and confirm no doc-frontmatter validation errors

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Doc-only change, fully git-reversible.
- This ticket is informational only — no functional code changes.
