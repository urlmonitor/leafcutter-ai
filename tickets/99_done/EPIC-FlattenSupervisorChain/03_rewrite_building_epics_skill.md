---
title: "Update building-epics SKILL.md for flat model"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 02_rewrite_ticket_supervisor.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
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

# 03: Update building-epics SKILL.md for flat model

## Goal

Rewrite the building-epics operational runbook to reflect the flattened supervisor architecture where the build-feature workflow (depth 0) coordinates epics and ticket-supervisors (depth 1) do all phase work inline.

## Context

`building-epics/SKILL.md` is the single operational runbook loaded by both epic-supervisor and ticket-supervisor. After the flattening:
- SS1 (epic-level algorithm) is now executed by the `build-feature.md` workflow at depth 0, not by a dispatched epic-supervisor agent
- SS2 (ticket-level algorithm) is executed inline by ticket-supervisor with NO Agent tool — phases are read-and-execute, not spawn-and-wait
- SS3.3 (brainstorm escalation) returns to main context instead of spawning brainstorm-lead
- SS5 (commit-phase lock) is unchanged

## Requirements

### SS1 updates (epic-level algorithm)
- Replace "epic-supervisor" with "the build-feature workflow (main context)" throughout
- The algorithmic steps (dependency graph, batch computation, halt conditions) remain identical
- Note that the workflow dispatches ticket-supervisors via Agent tool at depth 0 (they run at depth 1)

### SS2 updates (ticket-level algorithm)
- Replace step "SPAWN next_agent via Agent tool" with "READ next_agent's template via Read tool, then EXECUTE its instructions inline"
- Remove all references to Agent tool being used by ticket-supervisor
- Add note: "ticket-supervisor does NOT have access to the Agent tool (depth-1 constraint)"
- Routing table (ok/handoff/blocker/question) remains unchanged

### SS3 updates (failure adjudication)
- SS3.1 (trivial mechanical): "retry inline" instead of "respawn same agent"
- SS3.2 (cross-agent rework): "re-read sibling template, re-execute inline" instead of "flip sibling, respawn"
- SS3.3 (brainstorm escalation): ticket-supervisor returns `{status: "blocked", escalation_type: "brainstorm"}` to the main context. The main context dispatches brainstorm-lead at depth 1. Remove any reference to ticket-supervisor spawning brainstorm-lead
- SS3.4 (halt): unchanged

### New section: Phase Agent Inline Execution Protocol
Add a new section (SS9 or similar) describing:
1. How ticket-supervisor reads phase agent templates at runtime
2. The path resolution: `agent_registry.json` -> `template_path` field -> Read
3. What it means to "execute inline" (follow the template's instructions using Read/Edit/Write/Bash)
4. How signoff works when executing inline (same skill, same protocol)
5. Code search alternatives (git grep, grep -r, find via Bash instead of research-agent)

### Unchanged sections
- SS4 (retry caps) — numbers unchanged
- SS5 (commit-phase lock) — ticket-supervisor still owns it
- SS6 (user escalation payload) — schema unchanged

## Out of Scope

- Changing the signoff skill
- Changing retry cap numbers
- Changing the commit-phase lock mechanism

## Acceptance Criteria

1. No reference to "epic-supervisor" as an agent that gets dispatched (ok as historical reference)
2. No reference to ticket-supervisor using the Agent tool
3. SS2 describes read-and-execute pattern
4. SS3.3 describes brainstorm return-to-main-context pattern
5. New inline execution protocol section exists
6. Skill is internally consistent with rewritten ticket-supervisor (ticket 02)

## Sign-offs

- [ ] python-coder
- [ ] change-scope-reviewer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

_No comments yet._
