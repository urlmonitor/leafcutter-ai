---
title: "Remove the dead finalize-feature agent fallback; slash command hard-errors"
status: todo
components:
  - supervisor_system
  - agent_registry
created: 2026-06-24
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
files_touched:
  - templates/agents/finalize-feature.md
  - config/agent_registry.json
  - templates/workflows/finalize-feature.md
  - docs/how-to/finalize-feature.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  llm-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Remove the dead finalize-feature agent fallback; slash command hard-errors

## Actor / Goal

In order to stop `/finalize-feature` from silently routing to a fallback that
cannot work, we need to retire the `finalize-feature` LLM agent and make the
slash command emit a clear, actionable error when the JS-workflow path is
unavailable — so a stale install fails loudly instead of pretending to finalize.

## Context

The `finalize-feature` agent is `tier: supervisor` and dispatches `pull-request`,
`status-checker`, `worktree-agent`, `test-runner`, `test-failure-triage`. Invoked
via the Agent tool it runs at depth 1, so its dispatches are depth 2 — silently
dropped by Claude Code's hard depth-1 limit (ADR-006). The limit has no version
gate, so the "fallback for older versions" never worked on any version, and it
fails *silently* (loop reports success; PR never merges, tickets never close).

The ADR-006 migration that deprecated `epic-supervisor` (template
`[DEPRECATED — see ADR-006]` tag + registry `deprecated: true` / `legacy_only: true`)
was never applied to `finalize-feature`. It is still registered active and still
advertised as a live fallback by the slash command and how-to.

This is documentation/template/registry work — no Python. `llm-expert` owns the
agent-template and slash-command edits; `documentation-expert` updates the how-to
and ADR addendum.

## Acceptance Criteria

- [ ] AC-1: `templates/agents/finalize-feature.md` is removed (preferred) OR marked
  with the `[DEPRECATED — see ADR-006]` title tag AND the registry flags below — the
  team chooses removal vs deprecation-window in review. Default to removal since the
  agent is non-functional, not merely superseded.
- [ ] AC-2: `config/agent_registry.json` no longer presents `finalize-feature` as an
  active user-invocable supervisor (entry removed, or `deprecated: true` +
  `legacy_only: true` if the deprecation-window path is chosen).
- [ ] AC-3: The slash-command surface (`templates/workflows/finalize-feature.md`) no
  longer advertises the agent fallback; on an install lacking Workflow-tool support
  it prints an explicit, actionable error (e.g. "requires Claude Code >= 2.1.154;
  the legacy agent fallback was removed because the depth-1 limit makes it
  non-functional — please upgrade") instead of dispatching the agent.
- [ ] AC-4: `docs/how-to/finalize-feature.md` version notes are updated to match.
- [ ] AC-5: An ADR-006 addendum records that finalize-feature joins epic-supervisor as
  a flattened/removed supervisor and that the JS workflow is the sole depth-0 path.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Comments

## Implementation Tasks
- [ ] Decide removal vs deprecation-window (default: removal); apply to template + registry.
- [ ] Rewrite the slash-command fallback branch to hard-error.
- [ ] Update the how-to version notes.
- [ ] Add the ADR-006 addendum.
- [ ] Confirm no other surface (build registries, parity tests) still requires the agent.

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High — template/registry/doc edits, revertible. Removing a
  non-functional agent has no behavioral downside.

## Out of Scope
- The JS workflow's own bugs (tickets 01, 04–09).
