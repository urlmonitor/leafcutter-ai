---
title: "Update build-single-ticket skill for brainstorm escalation"
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
  - templates/skills/build-single-ticket/SKILL.md
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

# 05: Update build-single-ticket skill for brainstorm escalation

## Goal

Update the `build-single-ticket` skill to handle the brainstorm escalation return path from ticket-supervisor. Since ticket-supervisor can no longer dispatch brainstorm-lead (no Agent tool at depth 1), the build-single-ticket skill (running at depth 0) must handle it.

## Context

`build-single-ticket/SKILL.md` is the standalone-ticket analogue of the epic flow. It dispatches ticket-supervisor at depth 1 via Agent tool. In the old architecture, ticket-supervisor could dispatch brainstorm-lead when hitting a design-class blocker. Now it returns a structured `{status: "blocked", escalation_type: "brainstorm"}` payload instead.

The build-single-ticket skill runs at depth 0, so it CAN dispatch brainstorm-lead at depth 1.

## Requirements

1. **Remove `via: /build-feature (build-single-ticket)` marker** — ticket-supervisor no longer validates caller identity (it accepts dispatch from any depth-0 context)

2. **Add brainstorm escalation loop** after dispatching ticket-supervisor:
   - If ticket-supervisor returns `{status: "blocked", escalation_type: "brainstorm", design_question: "..."}`:
     1. Dispatch `brainstorm-lead` at depth 1 with the design question
     2. Collect the recommendation
     3. Re-invoke ticket-supervisor with `{ticket_path: ..., brainstorm_recommendation: "..."}`
   - Cap: 1 brainstorm escalation per ticket (same as existing cap)
   - If ticket-supervisor returns `{status: "blocked"}` WITHOUT `escalation_type: "brainstorm"`, surface the payload to the user as before

3. **Update references** to ticket-supervisor's capabilities — remove any mention of it dispatching sub-agents

## Out of Scope

- Changing the worktree setup logic
- Changing the inbox-to-todo promotion logic
- Modifying ticket-supervisor itself (ticket 02)

## Acceptance Criteria

1. No `via:` marker in ticket-supervisor dispatch
2. Brainstorm escalation loop handles `{escalation_type: "brainstorm"}` payloads
3. Non-brainstorm blocked payloads are still surfaced to user unchanged
4. Cap of 1 brainstorm escalation per ticket is enforced

## Sign-offs

- [ ] python-coder
- [ ] change-scope-reviewer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

_No comments yet._
