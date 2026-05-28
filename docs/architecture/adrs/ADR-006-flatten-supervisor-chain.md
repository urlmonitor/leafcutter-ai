---
title: "ADR-006: Flatten Supervisor Chain to Depth-1 Nesting Limit"
status: accepted
date: 2026-05-28
---

# ADR-006: Flatten Supervisor Chain to Depth-1 Nesting Limit

## Status

Accepted (2026-05-28)

## Context

Claude Code enforces a hard depth-1 nesting limit on sub-agent dispatch: an agent spawned via the Agent tool (depth 1) cannot itself spawn further agents. The previous leafcutter supervisor architecture used a 3-level chain:

```
build-feature (depth 0) → epic-supervisor (depth 1) → ticket-supervisor (depth 2) → phase-agents (depth 3)
```

This chain was impossible to execute. epic-supervisor at depth 1 could not dispatch ticket-supervisors. ticket-supervisors could not dispatch phase agents. The architecture was designed before the nesting limit was discovered and never actually ran as designed.

## Decision

Restructure the supervisor hierarchy to operate within the depth-1 constraint:

1. **Absorb epic-supervisor into build-feature workflow**: The build-feature.md workflow (which runs at depth 0 in the main conversation context) now performs all epic-level orchestration inline: dependency graph computation, batch formation, the six-step epic loop, cross-ticket pattern detection, and the post-completion chain.

2. **Make ticket-supervisor self-contained**: ticket-supervisor runs at depth 1 and has NO access to the Agent tool. It performs all phase work inline by reading phase agent templates (via the Read tool) and executing their instructions directly using Read/Edit/Write/Bash. Phase agent templates become "instruction manuals" rather than independently dispatched agents.

3. **Brainstorm escalation returns to main context**: When ticket-supervisor encounters a design-class blocker, it returns a structured `{escalation_type: "brainstorm"}` payload to the main context (depth 0), which dispatches brainstorm-lead at depth 1.

4. **Code search uses Bash**: ticket-supervisor uses `git grep`, `grep -r`, and `find` via Bash instead of dispatching research-agent (which required MCP tools not available at depth 1).

The new architecture:

```
build-feature workflow (depth 0, main context)
  ├── ticket-supervisor × N (depth 1, self-contained)
  │   └── Reads phase templates, executes inline
  ├── brainstorm-lead (depth 1, on escalation)
  │   └── brainstorm-workers (depth 2, leaf)
  └── utility agents: retrospective-agent, worktree-agent (depth 1)
```

## Consequences

- **Loss of agent boundary isolation per phase**: All phase work runs in ticket-supervisor's context window. Previously each phase agent had its own clean context. Mitigated by read-on-demand — templates are loaded only when needed.
- **Ticket-supervisor context window grows**: As each phase executes, the context accumulates. For large tickets with many phases, this may approach limits. Mitigated by the fact that most tickets only have 3-4 active phases.
- **Brainstorm escalation adds a round-trip**: Previously ticket-supervisor dispatched brainstorm-lead directly. Now it must return to the main context and be re-invoked with the recommendation.
- **Code search is less structured**: `git grep` and `find` replace research-agent's MCP tools (jcodemunch, serena, context7). The trade-off is acceptable for the scope of work ticket-supervisors handle.
- **Simpler mental model**: The flat architecture is easier to reason about — one coordinator, many workers, no intermediate orchestrator.
- **Epic-supervisor preserved as audit trail**: The template file is marked deprecated with pointers to this ADR, preserving the design history.

## Alternatives Considered

### Option B: Flatten epic-supervisor but keep ticket-supervisor dispatching phase agents

- Would have ticket-supervisors at depth 1 dispatching phase agents at depth 2
- Fails because phase agents (e.g. python-coder) dispatch research-agent, which would be depth 3
- Even ignoring research-agent, depth 2 is the leaf — phase agents couldn't use Agent tool for any purpose

### Option C: Rewrite all phase agents as skills instead of agents

- Skills are loaded via the Skill tool, not the Agent tool, potentially bypassing the depth limit
- Would require rewriting 19+ phase agent templates as skill files
- Breaks the template modularity that makes the package portable
- Skills have different lifecycle semantics (loaded once, not dispatched per task)
- Rejected as too large a change with unclear benefits
