---
title: "Remove the dead finalize-feature agent fallback; slash command hard-errors"
status: in_progress
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
  documentation-expert: signed_off
  llm-expert: signed_off
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
| AC-1 | | Removed templates/agents/finalize-feature.md via git rm | |
| AC-2 | | Removed finalize-feature entry from agent_registry.json; updated spawned_by in 5 agents to reference finalize-feature.js | |
| AC-3 | | Updated templates/workflows/finalize-feature.md: removed fallback description and legacy agent cross-reference; added hard-error block with version requirement and ADR-006 note | |
| AC-4 | | Updated `docs/how-to/finalize-feature.md`: removed fallback reference, added hard-error description and upgrade requirement | |
| AC-5 | | Appended addendum to `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` recording finalize-feature removal and JS workflow as sole path | |

## Sign-offs

- [x] llm-expert — 2026-06-24 12:00
- [x] documentation-expert — 2026-06-24 14:30
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-24 12:00 — llm-expert (status: ok)
feedback-id: fb_2026-06-24_0f27c4cb
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true
AC-1: Deleted `templates/agents/finalize-feature.md` via `git rm` — the non-functional LLM agent is removed from the package. AC-2: Removed the `finalize-feature` registry entry from `config/agent_registry.json` and updated the `spawned_by` lists of `test-runner`, `pull-request`, `status-checker`, `worktree-agent`, and `test-failure-triage` to reference `finalize-feature.js` (the actual workflow that dispatches them). Also removed the stale index row from `templates/agents/README.md`. AC-3: Rewrote `templates/workflows/finalize-feature.md` — removed the fallback description and the `Legacy agent` cross-reference; added a hard-error block with explicit version requirement (>= 2.1.154) and ADR-006 citation. Known gap (out of llm-expert scope): `templates/workflows-js/finalize-feature.js` line 31 still references the legacy agent in a comment — this is a `.js` file outside `templates/agents/`/`templates/skills/` and was flagged for `documentation-expert` or a follow-up edit.

### 2026-06-24 14:30 — documentation-expert (status: ok)
feedback-id: fb_2026-06-24_db3da92a
completion_manifest:
  ac4_how_to_updated: true
  ac5_adr_addendum_written: true
  js_comment_fixed: true
AC-4: Updated `docs/how-to/finalize-feature.md` — rewrote the Version Notes section to remove the fallback reference, describe the hard-error behaviour on older installs, and make clear that upgrade to >= 2.1.154 is required. Also updated `last_updated` frontmatter to 2026-06-24. AC-5: Appended a new addendum section to `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` (under "finalize-feature agent removed — JS workflow is the sole depth-0 path") recording that `finalize-feature` joins `epic-supervisor` as a removed supervisor, that `finalize-feature.js` is the sole depth-0 path, and the rationale (depth-2 dispatches were silently dropped on every version). Also updated the ADR's `last_updated` frontmatter. JS comment fix: updated `templates/workflows-js/finalize-feature.js` line 31 to remove the stale reference to the removed agent and describe the no-fallback hard-error behaviour instead.

## Implementation Tasks
- [ ] Decide removal vs deprecation-window (default: removal); apply to template + registry.
- [ ] Rewrite the slash-command fallback branch to hard-error.
- [x] Update the how-to version notes.
- [x] Add the ADR-006 addendum.
- [ ] Confirm no other surface (build registries, parity tests) still requires the agent.

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High — template/registry/doc edits, revertible. Removing a
  non-functional agent has no behavioral downside.

## Out of Scope
- The JS workflow's own bugs (tickets 01, 04–09).
