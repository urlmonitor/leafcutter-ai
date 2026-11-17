---
title: "goal_to_epic: an out-of-epic dependency is reported, not silently treated as satisfied"
status: todo
components:
  - ac_store
created: 2026-10-05
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - ac-store
  - epic-generation
  - dependencies
last_updated: 2026-10-05
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# goal_to_epic: an out-of-epic dependency is reported, not silently treated as satisfied

## Actor / Goal
In order that an epic is never built before the work it depends on, we need `goal_to_epic.py` to
report every leaf whose `depends_on` points outside the epic and is not yet done. Its dry run should
also show the build order, so that a wrong epic cut is caught before any ticket runs.

## Context
- **Found 2026-10-05**, by the independent review of kernel run run-0e9524762c1b4f85 (how to build
  DK-400 and DK-500).
  - Both trees have dependency cycles between their L1s: DK-400 `a→c→a`, `c↔d`, `d↔e`; DK-500
    `a→c→b→a`, and in code-only tickets `b→e→d→c→b` through DK-500b-4 → DK-500e-2.
  - So a per-L1 epic built in the wrong order would dispatch tickets whose prerequisites do not exist.
- **Cause:**
  - `scripts/ac_store/epic_dependencies.py:125-170` (`resolve_leaf_dependencies`) drops edges to
    ACs outside the selected set.
  - `:255-275`: Kahn's sort treats a missing node as satisfied.
  - `/build-feature`'s eligibility gate (`templates/workflows-js/build-feature.js:3299-3410`) then
    reads only each ticket's own, in-epic `depends_on`.
  - `epic_pipeline.py:108-118`: the dry run prints ticket ids only, with no order and no cycle
    report.
- **Workaround in use:** the build plan (dec-9925ebf1895222f4) cuts dependency-checked slices by
  hand with `goal_to_epic.py --ids`, checked against the store's `depends_on`.

## Scope (no acceptance criteria yet)
- For `--ac` and `--ids`, list every out-of-epic `depends_on` target with its `work_status`.
  - Fail by default when a target is not `done`.
  - Offer a flag to proceed, which records the gap in the epic's Master_Plan.
- `--dry-run` prints the topological build order and any cycle, with the AC ids on it.
- Tests:
  - an out-of-epic, not-done dependency is reported and fails;
  - a `done` one passes;
  - a cycle is named;
  - the dry run shows the order.

## Out of Scope
- Changing how `/build-feature` schedules within an epic.

## Comments

## Implementation Tasks
### test-writer
- [ ] Tests for out-of-epic dependency reporting, cycle naming and dry-run order.
### python-coder
- [ ] Report out-of-epic dependencies, fail on not-done ones, print order and cycles in the dry run.

## Risk & Safety
- Touches money? No.
- Touches data? No; epic generation only.
- Reversibility? Fully reversible.
