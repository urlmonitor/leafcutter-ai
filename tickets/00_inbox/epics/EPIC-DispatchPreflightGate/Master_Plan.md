---
epic_name: EPIC-DispatchPreflightGate
created: 2026-07-08
status: in_progress
components:
  - build_orchestration
source_ac: BO-1900
---
# EPIC-DispatchPreflightGate

## Goal

This epic implements AC BO-1900: Every ticket is proven fit to dispatch before an agent is spawned. It consists of 20 ticket(s) generated from the leaf ACs beneath BO-1900, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260708-BO-1900a-1.md](./01_TICKET-20260708-BO-1900a-1.md) | Preflight runs before spawn and holds back an unfit ticket with a reason | BO-1900a-1 | BO-1900a |
| 02 | [02_TICKET-20260708-BO-1900a-1-i.md](./02_TICKET-20260708-BO-1900a-1-i.md) | Preflight that errors internally fails closed and holds the ticket back | BO-1900a-1-i | BO-1900a-1 |
| 03 | [03_TICKET-20260708-BO-1900a-1-ii.md](./03_TICKET-20260708-BO-1900a-1-ii.md) | Held-back reason is surfaced to the operator, not only buried in logs | BO-1900a-1-ii | BO-1900a-1 |
| 04 | [04_TICKET-20260708-BO-1900a-2.md](./04_TICKET-20260708-BO-1900a-2.md) | A fit ticket passes preflight and dispatch proceeds unchanged | BO-1900a-2 | BO-1900a |
| 05 | [05_TICKET-20260708-BO-1900a-3.md](./05_TICKET-20260708-BO-1900a-3.md) | Sequence diagram documents the read -> preflight -> spawn flow | BO-1900a-3 | BO-1900a, BO-1900a-1 |
| 06 | [06_TICKET-20260708-BO-1900b-1.md](./06_TICKET-20260708-BO-1900b-1.md) | A premise that no longer reproduces at dispatch halts the run | BO-1900b-1 | BO-1900b, TKT-200e |
| 07 | [07_TICKET-20260708-BO-1900b-1-i.md](./07_TICKET-20260708-BO-1900b-1-i.md) | A premise with no attached reproduction command is treated as unfit | BO-1900b-1-i | BO-1900b-1 |
| 08 | [08_TICKET-20260708-BO-1900b-1-ii.md](./08_TICKET-20260708-BO-1900b-1-ii.md) | A reproduction command that errors or times out fails closed | BO-1900b-1-ii | BO-1900b-1 |
| 09 | [09_TICKET-20260708-BO-1900b-2.md](./09_TICKET-20260708-BO-1900b-2.md) | A premise that still reproduces at dispatch passes the freshness re-check | BO-1900b-2 | BO-1900b, TKT-200e |
| 10 | [10_TICKET-20260708-BO-1900b-3.md](./10_TICKET-20260708-BO-1900b-3.md) | Sequence diagram documents the dispatch-time premise re-check | BO-1900b-3 | BO-1900b, BO-1900b-1 |
| 11 | [11_TICKET-20260708-BO-1900c-1.md](./11_TICKET-20260708-BO-1900c-1.md) | A run-and-report task assigned to test-writer is caught as a mis-assignment | BO-1900c-1 | BO-1900c |
| 12 | [12_TICKET-20260708-BO-1900c-1-i.md](./12_TICKET-20260708-BO-1900c-1-i.md) | A task verb with no confidently-matching charter is held back, not passed | BO-1900c-1-i | BO-1900c-1 |
| 13 | [13_TICKET-20260708-BO-1900c-1-ii.md](./13_TICKET-20260708-BO-1900c-1-ii.md) | A registry entry with no charter description fails the check closed | BO-1900c-1-ii | BO-1900c-1 |
| 14 | [14_TICKET-20260708-BO-1900c-2.md](./14_TICKET-20260708-BO-1900c-2.md) | A correctly-assigned agent passes the charter check | BO-1900c-2 | BO-1900c |
| 15 | [15_TICKET-20260708-BO-1900c-3.md](./15_TICKET-20260708-BO-1900c-3.md) | Reference doc defines the charter-vs-task-verb matching rules | BO-1900c-3 | BO-1900c, BO-1900c-1 |
| 16 | [16_TICKET-20260708-BO-1900d-1.md](./16_TICKET-20260708-BO-1900d-1.md) | A payload of only allowlisted pointers is accepted | BO-1900d-1 | BO-1900d |
| 17 | [17_TICKET-20260708-BO-1900d-1-i.md](./17_TICKET-20260708-BO-1900d-1-i.md) | A payload missing a required pointer is held back | BO-1900d-1-i | BO-1900d-1 |
| 18 | [18_TICKET-20260708-BO-1900d-2.md](./18_TICKET-20260708-BO-1900d-2.md) | A payload carrying a free-composed prose prompt is rejected before spawn | BO-1900d-2 | BO-1900d |
| 19 | [19_TICKET-20260708-BO-1900d-2-i.md](./19_TICKET-20260708-BO-1900d-2-i.md) | A premise injected inside an allowlisted pointer value is rejected | BO-1900d-2-i | BO-1900d-2 |
| 20 | [20_TICKET-20260708-BO-1900d-3.md](./20_TICKET-20260708-BO-1900d-3.md) | Reference doc specifies the allowlisted dispatch-payload contract | BO-1900d-3 | BO-1900d, BO-1900d-1 |

## Dependencies

```
BO-1900a-1 (no dependencies)
BO-1900a-1-i -> BO-1900a-1
BO-1900a-1-ii -> BO-1900a-1
BO-1900a-2 (no dependencies)
BO-1900a-3 -> BO-1900a-1
BO-1900b-1 (no dependencies)
BO-1900b-1-i -> BO-1900b-1
BO-1900b-1-ii -> BO-1900b-1
BO-1900b-2 (no dependencies)
BO-1900b-3 -> BO-1900b-1
BO-1900c-1 (no dependencies)
BO-1900c-1-i -> BO-1900c-1
BO-1900c-1-ii -> BO-1900c-1
BO-1900c-2 (no dependencies)
BO-1900c-3 -> BO-1900c-1
BO-1900d-1 (no dependencies)
BO-1900d-1-i -> BO-1900d-1
BO-1900d-2 (no dependencies)
BO-1900d-2-i -> BO-1900d-2
BO-1900d-3 -> BO-1900d-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 05, 10 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 |
| python-coder | 06, 07, 08, 09, 11, 12, 13, 14 |
| reference-author | 15, 20 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 |
| workflow-architect | 01, 02, 03, 04, 16, 17, 18, 19 |

