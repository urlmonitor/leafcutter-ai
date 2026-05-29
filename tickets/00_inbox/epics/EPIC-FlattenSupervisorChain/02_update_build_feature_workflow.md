---
title: "Update build-feature workflow for direct ticket-supervisor dispatch"
status: todo
components:
  - build_pipeline
created: 2026-05-29
depends_on:
  - 01_update_ticket_supervisor_template.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows/build-feature.md
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
roadmap_phase: phase_1
advances_current_outcome: true
---

# 02: Update build-feature workflow for direct ticket-supervisor dispatch

## Goal

In order to eliminate the epic-supervisor → ticket-supervisor nesting that
breaks Claude Code's depth limit, we need to update the `/build-feature`
workflow so that both the epic path and the single-ticket path dispatch
`ticket-supervisor` directly at depth 0, without going through
`epic-supervisor` as an intermediary.

## Context

The `/build-feature` workflow (`templates/workflows/build-feature.md`) currently
has two dispatch paths:

1. **Single-ticket path** (works today): `build-single-ticket` sub-skill →
   `ticket-supervisor` at depth 0. This path already works correctly.

2. **Epic path** (broken): `epic-supervisor` at depth 0 →
   `ticket-supervisor` at depth 1 → phase agents at depth 2 (blocked by
   Claude Code's hard limit).

This ticket rewrites the epic path in `build-feature.md` to bypass
`epic-supervisor` and dispatch `ticket-supervisor` directly for each ready
ticket batch — mirroring the single-ticket path's working topology.

Depends on ticket 01 (updated ticket-supervisor template) being merged first,
so the template the workflow references is already correct.

## Acceptance Criteria

```gherkin
Given templates/workflows/build-feature.md is updated
When the "Step B — Dispatch" section is inspected
Then it dispatches ticket-supervisor directly, not epic-supervisor

Given the epic path is invoked
When ticket-supervisor is spawned
Then it runs at depth 0 (not inside epic-supervisor)
And phase agents spawned by ticket-supervisor run at depth 1

Given the single-ticket path is inspected
When build-single-ticket sub-skill dispatch is reviewed
Then the single-ticket path is unchanged (it already works correctly)

Given build.py is run
When the built .claude/commands/build-feature.md is inspected
Then the epic path references ticket-supervisor as its direct dispatch target
```

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Read `templates/workflows/build-feature.md` in full to understand the current Step B block
- [ ] Remove or rewrite "Step B — Dispatch the epic-supervisor" to instead implement epic-level batching inline (read Master_Plan, compute ready tickets from `depends_on`, dispatch `ticket-supervisor` per ready ticket)
- [ ] Wire the dependency-graph batching logic (currently inside `epic-supervisor`) directly into the build-feature workflow or a new sub-skill — keep the batch loop: read tickets, check `depends_on`, spawn `ticket-supervisor` per ready ticket in parallel
- [ ] Preserve the worktree-setup step (Step A) unchanged — it is correct
- [ ] Preserve the lock-file protocol unchanged
- [ ] Remove the "Step B" reference to `epic-supervisor` and delete or redirect Step A's epic-supervisor cleanup path
- [ ] Update the "References" section: replace `epic-supervisor` reference with direct note that epic batching is now inline
- [ ] Run `./build-self.sh` and confirm built workflow does not reference `epic-supervisor` in the dispatch path

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Template change is git-reversible.
- Blast radius: the epic path of `/build-feature` is the primary user-facing
  workflow for multi-ticket epics. A regression here means no epics can be
  driven until reverted. Architect-review mandatory before merge.
- The single-ticket path MUST NOT be changed (it already works at depth 0).
