---
title: "A fast-lane re-run refuses its own clean, unpublished earlier worktree"
status: todo
components:
  - build_orchestration
created: 2026-10-10
last_updated: 2026-10-10
depends_on: []
priority: medium
roadmap_phase: phase_1
change_target: infrastructure
risk_surface: internal
requires_diagram: false
requires_adr: false
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# A fast-lane re-run refuses its own clean, unpublished earlier worktree

## Actor / Goal
In order for a person to simply re-run the fast lane after a halt, a workspace left by the lane's own earlier attempt that holds nothing must be reused instead of refused.

## Context
- **Seen 2026-10-10** (`/fast-lane-build DK-600a-3`, run `wf_16a00988-47d`): the previous run had halted and released its AC, leaving `worktrees/dk-600a-3` on `fast-lane/dk-600a-3`. The re-run returned `refused` / `workspace_occupied` with occupant `own_prior_attempt`, `uncommitted_changes: false`, not pushed, and the branch had zero commits beyond `origin/main`. The only way on was a manual `git worktree remove` plus `git branch -D`.
- ADR-039 makes the refusal deliberate and fail-closed; this ticket keeps that for every case where something could be lost.
- A halted run also leaves the worktree behind, and in this case generated `docs/agents/cards/*` drift was in it, which a strict "clean" check would count as changes.

## Scope
1. When the occupant is the lane's own prior attempt, has no uncommitted changes other than known generated build noise, is unpublished, and has no commits beyond its base, reuse it (or recreate it) instead of refusing.
2. Every other occupied case keeps the ADR-039 refusal.
3. Tests for: reuse of a clean own attempt, refusal with uncommitted work, refusal when published or ahead of base.

## Out of Scope
- Changing the refusal payload shape.

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
