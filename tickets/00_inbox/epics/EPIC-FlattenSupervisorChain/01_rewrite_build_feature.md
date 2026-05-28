---
title: "Absorb epic-supervisor logic into build-feature workflow"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: critical
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows/build-feature.md
  - templates/agents/epic-supervisor.md
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

# 01: Absorb epic-supervisor logic into build-feature workflow

## Goal

Move all epic-level orchestration from `epic-supervisor.md` (which runs at depth 1 and therefore cannot dispatch ticket-supervisors) into `build-feature.md` (which runs at depth 0 in the main conversation context and CAN dispatch ticket-supervisors at depth 1).

## Context

The current `build-feature.md` workflow dispatches `epic-supervisor` as a depth-1 Agent. But epic-supervisor then tries to dispatch ticket-supervisors — which would be depth 2, violating Claude Code's hard limit. The fix is to have `build-feature.md` itself perform the epic-level orchestration inline.

The epic-supervisor template at `templates/agents/epic-supervisor.md` contains ~620 lines of orchestration logic including:
- 7 pre-flight checks (worktree preflight, Master_Plan completeness, orphan sweep, feedback sink)
- Six-step epic loop (read tickets, dependency graph, batch computation, parallel dispatch, barrier, halt-or-loop)
- Cross-ticket pattern detection (CFCS emit)
- File-touch parallelism gate and halt conditions
- Post-completion chain (retro, changelog, folder move, PR merge, worktree cleanup)

All of this must be absorbed into `build-feature.md`, replacing the current Step B ("Dispatch epic-supervisor").

## Requirements

1. **Keep Step A unchanged** — worktree setup, reachability check, cherry-pick recovery
2. **Replace Step B** with inline epic coordination that includes:
   - All 7 pre-flight checks from `epic-supervisor.md` (verbatim logic, adapted for workflow context)
   - The six-step epic loop from `building-epics` SS1.1
   - Cross-ticket pattern detection between steps 5 and 6
   - File-touch parallelism gate definition
   - Halt conditions from SS1.3
   - Full post-completion chain (retro decision, changelog via emit_entry.py, epic folder move, PR merge with mergeability gate, all-tickets-done gate, worktree cleanup)
3. **Add brainstorm escalation handler**: when a ticket-supervisor returns `{status: "blocked", escalation_type: "brainstorm"}`, the workflow (at depth 0) dispatches `brainstorm-lead` at depth 1, collects the recommendation, and re-invokes the ticket-supervisor with the answer
4. **Deprecate epic-supervisor.md**: Add a deprecation header to the template file explaining that its logic has been absorbed into `build-feature.md`. Do NOT delete the file — keep it as an audit trail with a clear pointer to the ADR (ticket 07)
5. **Preserve platform conditionals**: Keep the existing `{% if platform == 'claude' %}` / `{% elif platform == 'antigravity' %}` pattern

## Out of Scope

- Rewriting ticket-supervisor (ticket 02)
- Updating building-epics SKILL.md (ticket 03)
- Updating agent_registry.json (ticket 04)

## Acceptance Criteria

1. `build-feature.md` contains inline epic coordination logic (no Agent dispatch to epic-supervisor)
2. All 7 pre-flight checks from epic-supervisor are present in the rewritten workflow
3. Post-completion chain is complete (retro, changelog, folder move, PR merge, worktree cleanup)
4. Brainstorm escalation handler dispatches brainstorm-lead at depth 1
5. `epic-supervisor.md` has a deprecation header but is not deleted
6. Single-ticket workflow (build-single-ticket path) is unaffected by this change

## Sign-offs

- [ ] python-coder
- [ ] change-scope-reviewer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

_No comments yet._
