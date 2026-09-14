---
title: "EPIC: Work is only ever marked finished through the one door that checks it"
type: epic
epic_name: EPIC-WorkIsOnlyEverMarkedFinishedThroughThe
status: in_progress
components:
  - build_orchestration
  - supervisor_system
source_ac: BO-400e
created: 2026-09-14
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: false
change_target:
  - pipeline
  - prompt
  - docs
risk_surface: contract_boundary
---
# EPIC-WorkIsOnlyEverMarkedFinishedThroughThe

## Goal

This epic implements AC BO-400e: Work is only ever marked finished through the one door that checks it. It consists of 5 ticket(s) generated from the leaf ACs beneath BO-400e, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260914-BO-400e-1.md](./01_TICKET-20260914-BO-400e-1.md) | The steps a close is checked against are the ones the ticket's own record demands, and the caller cannot change that list | BO-400e-1 | — |
| 02 | [02_TICKET-20260914-BO-400e-2.md](./02_TICKET-20260914-BO-400e-2.md) | A demanded step nobody accounted for still blocks the finished state, and the block is not lifted by softening what counts | BO-400e-2 | 01_TICKET-20260914-BO-400e-1.md |
| 03 | [03_TICKET-20260914-BO-400e-3.md](./03_TICKET-20260914-BO-400e-3.md) | One door: the finished state is only ever written by the mechanism that checks it, and the blanket override is not the way through | BO-400e-3 | 01_TICKET-20260914-BO-400e-1.md, 02_TICKET-20260914-BO-400e-2.md |
| 04 | [04_TICKET-20260914-BO-400e-4.md](./04_TICKET-20260914-BO-400e-4.md) | Several tickets in the identical state, carried by one run, all get the same answer -- and it is the strict one | BO-400e-4 | 01_TICKET-20260914-BO-400e-1.md, 02_TICKET-20260914-BO-400e-2.md, 03_TICKET-20260914-BO-400e-3.md |
| 05 | [05_TICKET-20260914-BO-400e-5.md](./05_TICKET-20260914-BO-400e-5.md) | A sequence diagram shows every route to the finished state, and that exactly one of them passes the guard | BO-400e-5 | 01_TICKET-20260914-BO-400e-1.md, 02_TICKET-20260914-BO-400e-2.md, 03_TICKET-20260914-BO-400e-3.md, 04_TICKET-20260914-BO-400e-4.md |

## Dependencies

```
BO-400e-1 (no dependencies)
BO-400e-2 -> BO-400e-1
BO-400e-3 -> BO-400e-1, BO-400e-2
BO-400e-4 -> BO-400e-1, BO-400e-2, BO-400e-3
BO-400e-5 -> BO-400e-1, BO-400e-2, BO-400e-3, BO-400e-4
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 03, 04 |
| ac-validator | 01, 02, 03, 04 |
| architect-review | 01, 02, 03, 04 |
| architecture-diagram-author | 05 |
| commit | 01, 02, 03, 04, 05 |
| documentation-expert | 01, 02, 03, 04, 05 |
| documentation-verifier | 01, 02, 03, 04, 05 |
| llm-expert | 03 |
| pr-reviewer | 01, 02, 03, 04 |
| python-coder | 01, 02, 03, 04 |
| test-runner | 01, 02, 03, 04 |
| test-writer | 01, 02, 03, 04 |
| user-surface-smoker | 03 |

