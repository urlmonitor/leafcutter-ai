---
title: "Make ticket-supervisor self-contained (no Agent tool)"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: critical
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/ticket-supervisor.md
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

# 02: Make ticket-supervisor self-contained (no Agent tool)

## Goal

Rewrite `ticket-supervisor.md` so it performs ALL phase work inline without dispatching any sub-agents. Since it runs at depth 1, the Agent tool is unavailable — it must use only Read, Edit, Write, and Bash.

## Context

The current ticket-supervisor dispatches phase agents (python-coder, test-writer, pr-reviewer, commit, etc.) via the Agent tool. Under the depth-1 nesting limit, this is impossible. Instead, ticket-supervisor must:

1. Read the phase agent's template file to load its instructions
2. Execute those instructions inline (write code, run tests, commit, etc.)
3. Use the signoff skill to mark each phase complete
4. Route on the result (ok/handoff/blocker/question) per the existing protocol

This is the "instruction manual" pattern: phase agent templates remain as-is, but they are consumed by ticket-supervisor via Read rather than dispatched as independent agents.

## Requirements

### Frontmatter changes
- **Remove `Agent` from tools list**: `tools: Bash, Read, Edit, Write`
- **Update `spawned_by`**: `["user"]` (dispatched by main context, not epic-supervisor)
- **Update `spawn_allowlist`**: `[]` (empty — cannot dispatch anything)

### Phase execution model
Replace the "spawn agent and wait" loop with "read template and execute inline":

1. Read ticket's `agents:` map, compute pending list
2. Pick next agent per canonical priority order (unchanged)
3. **Read the phase agent's template** at path from agent_registry.json (`template_path` field)
4. **Execute the template's instructions inline** using Read/Edit/Write/Bash
5. **Use signoff skill** to mark phase completion (append comment, update frontmatter)
6. Re-read ticket, locate latest comment, route on status tag (ok/handoff/blocker/question)
7. Loop to step 2

### Code search (replacing research-agent)
- Use `git grep`, `grep -r`, `find` via Bash for cross-file lookups
- No MCP tools (Grep, Glob, jcodemunch, serena, context7) — these are not available at depth 1

### Test execution (replacing test-runner agent)
- Run test commands directly via Bash (pytest, etc.)
- Parse output inline for pass/fail determination

### Failure adjudication changes
- **SS3.1 (trivial mechanical)**: Retry the phase inline — re-read template, re-execute. Cap: 1 retry per phase per ticket
- **SS3.2 (cross-agent rework)**: Flip sibling to needed, re-read its template, re-execute inline. Cap: 1 per phase pair
- **SS3.3 (design question)**: CANNOT dispatch brainstorm-lead. Return to main context with `{status: "blocked", escalation_type: "brainstorm", design_question: "...", ...}`. The main context handles brainstorm dispatch
- **SS3.4 (halt)**: Same as before — return blocked payload to parent

### Preserve unchanged
- Commit-phase serialization lock (ticket-supervisor still owns it)
- Done-marking recipe (flip status + git mv)
- Staging discipline (explicit paths, never `git add .`)
- Sign-off protocol and comment schema
- Agent name validation against registry
- Disk-diff parity guard after each phase

## Out of Scope

- Modifying phase agent template contents (they remain as-is)
- Changing the signoff skill
- Changing which phases exist or their ordering
- Updating building-epics SKILL.md (ticket 03)

## Acceptance Criteria

1. `ticket-supervisor.md` does NOT list `Agent` in its `tools:` frontmatter
2. Template describes the "read and execute inline" pattern for each phase
3. Research is done via Bash (git grep, grep -r, find) not research-agent
4. Tests are run via Bash not test-runner agent
5. Brainstorm escalation returns `{escalation_type: "brainstorm"}` to parent
6. Commit-phase lock, staging discipline, done-marking recipe are preserved
7. Phase priority ordering is preserved (validated by ticket 06)

## Sign-offs

- [ ] python-coder
- [ ] change-scope-reviewer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

_No comments yet._
