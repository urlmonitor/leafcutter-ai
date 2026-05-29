---
title: "Validate phase ordering preserved in rewritten ticket-supervisor"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 02_rewrite_ticket_supervisor.md
  - 03_rewrite_building_epics_skill.md
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/ticket-supervisor.md
  - templates/skills/building-epics/SKILL.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
user_facing_surface: null
---

# 06: Validate phase ordering preserved in rewritten ticket-supervisor

## Goal

Verify that the canonical phase ordering from agent_registry.json priorities is correctly encoded in the rewritten ticket-supervisor and building-epics SKILL.md. This is a validation/hardening ticket, not a feature ticket.

## Context

The phase ordering is a critical invariant:
```
adr-author (1) -> architecture-diagram-author (2) -> architect-review (4) ->
test-writer (5) -> python-coder (6) -> sql-coder (7) -> frontend-coder (8) ->
test-runner (9) -> pr-reviewer (10) -> commit (11) -> pull-request (12) ->
documentation-expert (14) -> status-checker (15) -> change-scope-reviewer (16)
```

In the old architecture, ticket-supervisor read this from agent_registry.json `priority` fields and dispatched agents in that order. In the new architecture, ticket-supervisor reads and executes templates in that same order — the priority ordering must be preserved exactly.

## Requirements

1. **Cross-reference check**: Read the `priority` field from every `is_ticket_phase: true` agent in `agent_registry.json`. Compare against the priority table in `ticket-supervisor.md`. They must match exactly.

2. **SKILL.md consistency**: Verify that `building-epics/SKILL.md` SS2 references the same ordering.

3. **Special ordering rules preserved**:
   - `adr-author` and `architecture-diagram-author` MUST complete before `python-coder` or `sql-coder`
   - `frontend-coder` dispatches after `sql-coder` and before `test-runner`
   - `commit` and `pull-request` acquire the commit-phase lock
   - Docs-only test-writer skip rule still works inline

4. **Fix any discrepancies** found during validation. If a priority value was accidentally changed or omitted during the rewrites in tickets 02-03, correct it.

## Out of Scope

- Adding new phases
- Changing phase ordering
- Changing priority numbers

## Acceptance Criteria

1. Phase ordering in ticket-supervisor.md matches agent_registry.json priority fields exactly
2. Phase ordering in building-epics SKILL.md is consistent
3. Special ordering constraints (ADR before code, frontend after SQL, lock around commit) are documented
4. Any discrepancies from tickets 02-03 are fixed

## Sign-offs

- [ ] python-coder
- [ ] change-scope-reviewer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

_No comments yet._
