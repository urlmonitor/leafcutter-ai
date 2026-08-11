---
title: EPIC-BuildAcResolvesALeafAcsConnectedBuildSet
epic_name: EPIC-BuildAcResolvesALeafAcsConnectedBuildSet
created: 2026-08-11
status: in_progress
components:
  - build_orchestration
source_ac: BO-2600a
depends_on: []
change_target: pipeline
risk_surface: internal
requires_diagram: false
requires_adr: false
---
# EPIC-BuildAcResolvesALeafAcsConnectedBuildSet

## Goal

This epic implements AC BO-2600a: build-ac resolves a leaf AC's connected build set and generates the whole set in dependency order. It consists of 5 ticket(s) generated from the leaf ACs beneath BO-2600a, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260811-BO-2600a-1.md](./01_TICKET-20260811-BO-2600a-1.md) | resolve_connected_build_set can exclude a node's structural parent from the depends_on walk | BO-2600a-1 | BO-2600a |
| 02 | [02_TICKET-20260811-BO-2600a-2.md](./02_TICKET-20260811-BO-2600a-2.md) | The select_connected CLI exposes --exclude-structural-parent | BO-2600a-2 | BO-2600a, BO-2600a-1 |
| 03 | [03_TICKET-20260811-BO-2600a-3.md](./03_TICKET-20260811-BO-2600a-3.md) | build-ac leaf path is unchanged when the connected build set is just the target AC | BO-2600a-3 | BO-2600a, BO-2600a-2 |
| 04 | [04_TICKET-20260811-BO-2600a-4.md](./04_TICKET-20260811-BO-2600a-4.md) | build-ac emits a dependency-ordered epic when the connected build set has more than one AC | BO-2600a-4 | BO-2600a, BO-2600a-2, BO-2600a-5 |
| 05 | [05_TICKET-20260811-BO-2600a-5.md](./05_TICKET-20260811-BO-2600a-5.md) | goal_to_epic can build an epic from an explicit connected-set id list, not just a single AC's subtree | BO-2600a-5 | BO-2600a |

## Dependencies

```
BO-2600a-1 (no dependencies)
BO-2600a-2 -> BO-2600a-1
BO-2600a-3 -> BO-2600a-2
BO-2600a-5 (no dependencies beyond parent)
BO-2600a-4 -> BO-2600a-2, BO-2600a-5
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 05 |
| ac-validator | 01, 02, 05 |
| architect-review | 01 |
| commit | 01, 02, 03, 04, 05 |
| documentation-expert | 01, 03, 04, 05 |
| documentation-verifier | 01, 03, 04, 05 |
| llm-expert | 03, 04 |
| pr-reviewer | 01, 03, 04, 05 |
| pull-request | 01, 02, 03, 04, 05 |
| python-coder | 01, 02, 05 |
| test-runner | 01, 02, 05 |
| test-writer | 01, 02, 05 |

