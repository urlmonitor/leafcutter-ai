---
epic_name: EPIC-FeedbackPortability
created: 2026-06-08
status: in_progress
components:
  - infrastructure
source_ac: INF-100c
---
# EPIC-FeedbackPortability

## Goal

This epic implements AC INF-100c: Feedback submission resolves its config and validates writers correctly in deployed projects. It consists of 6 tickets generated from the leaf ACs beneath INF-100c, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [TICKET-20260608-INF-100c-1.md](./TICKET-20260608-INF-100c-1.md) | Config resolution uses the script's own location as anchor | INF-100c-1 | — |
| 02 | [TICKET-20260608-INF-100c-3.md](./TICKET-20260608-INF-100c-3.md) | All phase agents are recognized as valid writers | INF-100c-3 | — |
| 03 | [01_TICKET-20260608-INF-100c-1-i.md](./01_TICKET-20260608-INF-100c-1-i.md) | Config resolution in a worktree of a deployed project | INF-100c-1-i | INF-100c-1 |
| 04 | [02_TICKET-20260608-INF-100c-2.md](./02_TICKET-20260608-INF-100c-2.md) | Config resolution works from the source repo location | INF-100c-2 | INF-100c-1 |
| 05 | [04_TICKET-20260608-INF-100c-4.md](./04_TICKET-20260608-INF-100c-4.md) | Feedback submission error message identifies the missing config path | INF-100c-4 | INF-100c-1 |
| 06 | [03_TICKET-20260608-INF-100c-3-i.md](./03_TICKET-20260608-INF-100c-3-i.md) | Unknown agent is still rejected with a clear error | INF-100c-3-i | INF-100c-3 |

## Dependencies

```
INF-100c-1 → INF-100c-1-i, INF-100c-2, INF-100c-4
INF-100c-3 → INF-100c-3-i
```

Batch 1 (parallel): INF-100c-1, INF-100c-3
Batch 2 (after batch 1): INF-100c-1-i, INF-100c-2, INF-100c-4, INF-100c-3-i

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| python-coder | 01, 02, 03, 04, 05, 06 |
| test-writer | 01, 02, 03, 04, 05, 06 |
| test-runner | 01, 02, 03, 04, 05, 06 |
| pr-reviewer | 01, 02, 03, 04, 05, 06 |
| commit | 01, 02, 03, 04, 05, 06 |
| pull-request | 01, 02, 03, 04, 05, 06 |
