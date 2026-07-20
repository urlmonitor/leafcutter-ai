---
title: "EPIC-InFlightVisibility"
epic_name: EPIC-InFlightVisibility
created: 2026-07-15
status: in_progress
components:
  - build_orchestration
source_ac: BO-1000
depends_on: []
---
# EPIC-InFlightVisibility

## Goal

This epic implements AC BO-1000: See automation working in real time — never wonder if it stalled. It consists of 16 ticket(s) generated from the leaf ACs beneath BO-1000, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260715-BO-1000a-1.md](./01_TICKET-20260715-BO-1000a-1.md) | Every non-error finalize step emits a start-of-step progress line on the success path | BO-1000a-1 | BO-1000a |
| 02 | [02_TICKET-20260715-BO-1000a-1-i.md](./02_TICKET-20260715-BO-1000a-1-i.md) | The in-flight step is identifiable from the start line even when its sub-agent errors | BO-1000a-1-i | BO-1000a-1 |
| 03 | [03_TICKET-20260715-BO-1000a-2.md](./03_TICKET-20260715-BO-1000a-2.md) | The step count N in the announcements is stable and correct across the run | BO-1000a-2 | BO-1000a |
| 04 | [04_TICKET-20260715-BO-1000a-2-i.md](./04_TICKET-20260715-BO-1000a-2-i.md) | The intermediate closure step and early pre-flight aborts do not break the X-of-N counting | BO-1000a-2-i | BO-1000a-2 |
| 05 | [05_TICKET-20260715-BO-1000a-3.md](./05_TICKET-20260715-BO-1000a-3.md) | A step skipped because its state is already satisfied still reports the skip and why | BO-1000a-3 | BO-1000a |
| 06 | [06_TICKET-20260715-BO-1000a-4.md](./06_TICKET-20260715-BO-1000a-4.md) | Sequence diagram of the start-of-step narration emission path | BO-1000a-4 | BO-1000a, BO-1000a-1 |
| 07 | [07_TICKET-20260715-BO-1000b-1.md](./07_TICKET-20260715-BO-1000b-1.md) | Each finalize step emits a one-line outcome result after its work, on the success path | BO-1000b-1 | BO-1000b |
| 08 | [08_TICKET-20260715-BO-1000b-1-i.md](./08_TICKET-20260715-BO-1000b-1-i.md) | A skipped step records a skipped outcome so the per-step record has no gaps | BO-1000b-1-i | BO-1000b-1 |
| 09 | [09_TICKET-20260715-BO-1000b-2.md](./09_TICKET-20260715-BO-1000b-2.md) | The end-of-run summary is composed from the recorded per-step outcomes | BO-1000b-2 | BO-1000b |
| 10 | [10_TICKET-20260715-BO-1000b-2-i.md](./10_TICKET-20260715-BO-1000b-2-i.md) | On HALT the recap reports which steps completed, which step halted, and why | BO-1000b-2-i | BO-1000b-2 |
| 11 | [11_TICKET-20260715-BO-1000b-3.md](./11_TICKET-20260715-BO-1000b-3.md) | Step outcomes and the recap carry concrete result data, never a content-free 'done' | BO-1000b-3 | BO-1000b |
| 12 | [12_TICKET-20260715-BO-1000c-1a.md](./12_TICKET-20260715-BO-1000c-1a.md) | Background finalize appends each progress line to a durable, pollable run-progress journal as it happens | BO-1000c-1a | BO-1000c, BO-1000a-1, BO-1000b-1 |
| 13 | [13_TICKET-20260715-BO-1000c-1b.md](./13_TICKET-20260715-BO-1000c-1b.md) | The /finalize-feature launcher polls the run-progress journal and relays it into the main conversation | BO-1000c-1b | BO-1000c, BO-1000c-1a |
| 14 | [14_TICKET-20260715-BO-1000c-2.md](./14_TICKET-20260715-BO-1000c-2.md) | Surfaced progress reflects the in-flight step, arriving over time rather than only at the end | BO-1000c-2 | BO-1000c, BO-1000c-1a, BO-1000c-1b |
| 15 | [15_TICKET-20260715-BO-1000c-2-i.md](./15_TICKET-20260715-BO-1000c-2-i.md) | On a mid-flight halt the last conversation line reflects the halting step, live | BO-1000c-2-i | BO-1000c-2 |
| 16 | [16_TICKET-20260715-BO-1000c-3.md](./16_TICKET-20260715-BO-1000c-3.md) | Sequence diagram of live progress delivery from background workflow to the conversation | BO-1000c-3 | BO-1000c, BO-1000c-1a, BO-1000c-1b |

## Dependencies

```
BO-1000a-1 (no dependencies)
BO-1000a-1-i -> BO-1000a-1
BO-1000a-2 (no dependencies)
BO-1000a-2-i -> BO-1000a-2
BO-1000a-3 (no dependencies)
BO-1000a-4 -> BO-1000a-1
BO-1000b-1 (no dependencies)
BO-1000b-1-i -> BO-1000b-1
BO-1000b-2 (no dependencies)
BO-1000b-2-i -> BO-1000b-2
BO-1000b-3 (no dependencies)
BO-1000c-1a -> BO-1000a-1, BO-1000b-1
BO-1000c-1b -> BO-1000c-1a
BO-1000c-2 -> BO-1000c-1a, BO-1000c-1b
BO-1000c-2-i -> BO-1000c-2
BO-1000c-3 -> BO-1000c-1a, BO-1000c-1b
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 06, 16 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| llm-expert | 13, 14, 15 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| python-coder | 01, 02, 03, 04, 05, 07, 08, 09, 10, 11, 12 |
| test-runner | 01, 02, 03, 04, 05, 07, 08, 09, 10, 11, 12 |
| test-writer | 01, 02, 03, 04, 05, 07, 08, 09, 10, 11, 12 |

