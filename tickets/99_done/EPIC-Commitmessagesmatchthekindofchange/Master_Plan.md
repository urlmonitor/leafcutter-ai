---
epic_name: EPIC-CommitMessagesMatchTheKindOfChange
created: 2026-06-08
status: done
components:
  - build_orchestration
source_ac: BO-1100
---
# EPIC-CommitMessagesMatchTheKindOfChange

## Goal

This epic implements AC BO-1100: Commit messages match the kind of change automatically -- no manual formatting decisions. It consists of 5 ticket(s) generated from the leaf ACs beneath BO-1100, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260608-BO-1100a.md](./01_TICKET-20260608-BO-1100a.md) | The right message style is chosen for you based on what changed | BO-1100a | BO-1100 |
| 02 | [02_TICKET-20260608-BO-1100b.md](./02_TICKET-20260608-BO-1100b.md) | Unrelated changes in the same commit are flagged before they land | BO-1100b | BO-1100 |
| 03 | [03_TICKET-20260608-BO-1100c.md](./03_TICKET-20260608-BO-1100c.md) | Message patterns are defined in one place you can read and edit | BO-1100c | BO-1100 |
| 04 | [04_TICKET-20260608-BO-1100d.md](./04_TICKET-20260608-BO-1100d.md) | Unfamiliar commit shapes are analysed and learned over time | BO-1100d | BO-1100c |
| 05 | [05_TICKET-20260608-BO-1100e.md](./05_TICKET-20260608-BO-1100e.md) | The specialist only reads relevant history, not thousands of commits | BO-1100e | BO-1100d |

## Dependencies

```
BO-1100a (no dependencies)
BO-1100b (no dependencies)
BO-1100c (no dependencies)
BO-1100d -> BO-1100c
BO-1100e -> BO-1100d
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05 |
| pr-reviewer | 01, 02, 03, 04, 05 |
| pull-request | 01, 02, 03, 04, 05 |
| test-runner | 01, 02, 03, 04, 05 |
| test-writer | 01, 02, 03, 04, 05 |

