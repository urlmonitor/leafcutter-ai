---
epic_name: EPIC-ExceptionHandlingGuardEnforcesTheError
created: 2026-06-17
status: in_progress
components:
  - guardrail-engine
source_ac: GE-108
---
# EPIC-ExceptionHandlingGuardEnforcesTheError

## Goal

This epic implements AC GE-108: Exception-handling guard enforces the error-handling policy faithfully and accurately. It consists of 3 ticket(s) generated from the leaf ACs beneath GE-108, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260617-GE-108a.md](./01_TICKET-20260617-GE-108a.md) | Exception-handling guard treats subprocess calls as a mandatory I/O boundary | GE-108a | GE-108 |
| 02 | [02_TICKET-20260617-GE-108b.md](./02_TICKET-20260617-GE-108b.md) | Blind-catch handler is cleared only by genuine WARNING-or-higher logging | GE-108b | GE-108 |
| 03 | [03_TICKET-20260617-GE-108c.md](./03_TICKET-20260617-GE-108c.md) | Tuple exception types are rendered in full in the violation message | GE-108c | GE-108 |

## Dependencies

```
GE-108a (no dependencies)
GE-108b (no dependencies)
GE-108c (no dependencies)
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03 |
| pr-reviewer | 01, 02, 03 |
| pull-request | 01, 02, 03 |
| python-coder | 01, 02, 03 |
| test-runner | 01, 02, 03 |
| test-writer | 01, 02, 03 |

