---
title: "Update agent_registry.json spawn topology for flat model"
status: todo
components:
  - config_loader
created: 2026-05-28
depends_on:
  - 01_rewrite_build_feature.md
  - 02_rewrite_ticket_supervisor.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - config/agent_registry.json
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

# 04: Update agent_registry.json spawn topology for flat model

## Goal

Update `config/agent_registry.json` so that `spawn_allowlist`, `spawned_by`, and related fields reflect the flattened supervisor architecture where ticket-supervisors are dispatched by the main context and do all phase work inline.

## Context

The registry is the single source of truth for agent relationships. After the flattening:
- epic-supervisor is deprecated (its logic lives in `build-feature.md`)
- ticket-supervisor is dispatched by the main context (user), not by epic-supervisor
- ticket-supervisor cannot spawn anything (no Agent tool at depth 1)
- Phase agents are no longer spawned — their templates are read and executed inline by ticket-supervisor
- brainstorm-lead is dispatched by the main context, not by ticket-supervisor

## Requirements

### epic-supervisor entry
Add deprecation fields:
```json
{
  "id": "epic-supervisor",
  "deprecated": true,
  "deprecated_reason": "Logic absorbed into build-feature workflow per ADR-NNN (depth-1 nesting constraint). Template preserved as audit trail.",
  ...existing fields preserved for reference...
}
```

### ticket-supervisor entry
```json
{
  "spawned_by": ["user"],
  "spawn_allowlist": []
}
```
Remove `__ticket_phase_agents__` from `spawn_allowlist`.

### All phase agents with `"ticket-supervisor"` in spawned_by
For each agent where `spawned_by` includes `"ticket-supervisor"`:
- Remove `"ticket-supervisor"` from `spawned_by`
- Add `"inline_execution_by": ["ticket-supervisor"]` to signal the template is read and executed inline rather than dispatched as a sub-agent

Affected agents (from current registry): architect-review, python-coder, test-writer, test-runner, documentation-expert, pr-reviewer, commit, pull-request, sql-coder, frontend-coder, status-checker, change-scope-reviewer, user-surface-smoker, adr-author, architecture-diagram-author, explanation-author, how-to-author, reference-author.

### brainstorm-lead entry
```json
{
  "spawned_by": ["user"]
}
```
Change from `["ticket-supervisor"]` to `["user"]` (dispatched by main context at depth 0).

### Schema update
If `agent_registry.schema.json` exists, add `deprecated`, `deprecated_reason`, and `inline_execution_by` as optional fields.

## Out of Scope

- Changing agent tier classifications
- Changing model assignments
- Changing selection_criteria or trigger_conditions
- Adding or removing agents

## Acceptance Criteria

1. epic-supervisor entry has `"deprecated": true`
2. ticket-supervisor entry has `spawned_by: ["user"]` and `spawn_allowlist: []`
3. No phase agent lists `"ticket-supervisor"` in `spawned_by`
4. All phase agents that were spawned by ticket-supervisor have `"inline_execution_by": ["ticket-supervisor"]`
5. brainstorm-lead has `spawned_by: ["user"]`
6. `python scripts/build.py --validate` passes (if validation exists)
7. Schema file updated if it exists

## Sign-offs

- [ ] python-coder
- [ ] change-scope-reviewer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

_No comments yet._
