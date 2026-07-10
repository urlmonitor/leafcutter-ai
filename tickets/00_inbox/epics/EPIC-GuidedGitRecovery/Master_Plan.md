---
epic_name: EPIC-GuidedGitRecovery
created: 2026-07-06
status: done
components:
  - build_orchestration
source_ac: BO-1600d
---
# EPIC-GuidedGitRecovery

## Goal

This epic implements AC BO-1600d: If corruption is ever found, you get a safe, guided way back to a working repository. It consists of 10 ticket(s) generated from the leaf ACs beneath BO-1600d, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260706-BO-1600d-1.md](./01_TICKET-20260706-BO-1600d-1.md) | Recovery is human-invoked and confirmation-gated — it never runs inside the automatic drive loop | BO-1600d-1 | BO-1600d |
| 02 | [02_TICKET-20260706-BO-1600d-2.md](./02_TICKET-20260706-BO-1600d-2.md) | Recovery is non-destructive by default: it prints exactly what it will do and only acts on explicit confirmation | BO-1600d-2 | BO-1600d, BO-1600d-1 |
| 03 | [03_TICKET-20260706-BO-1600d-3.md](./03_TICKET-20260706-BO-1600d-3.md) | Recovery performs the real repair steps observed in the incident, in dependency order | BO-1600d-3 | BO-1600d, BO-1600d-1, BO-1600d-2 |
| 04 | [04_TICKET-20260706-BO-1600d-3-i.md](./04_TICKET-20260706-BO-1600d-3-i.md) | On git older than 2.36 (no fetch --refetch), recovery falls back or refuses rather than running an unsupported command | BO-1600d-3-i | BO-1600d-3 |
| 05 | [05_TICKET-20260706-BO-1600d-3-ii.md](./05_TICKET-20260706-BO-1600d-3-ii.md) | When origin genuinely lacks the missing objects, recovery reports it as unrecoverable and does not loop | BO-1600d-3-ii | BO-1600d-3 |
| 06 | [06_TICKET-20260706-BO-1600d-3-iii.md](./06_TICKET-20260706-BO-1600d-3-iii.md) | Recovery refuses to run on a shallow or bare clone | BO-1600d-3-iii | BO-1600d-3 |
| 07 | [07_TICKET-20260706-BO-1600d-3-iv.md](./07_TICKET-20260706-BO-1600d-3-iv.md) | Branch-ref reset targets the detected default/current branch, never a hardcoded main | BO-1600d-3-iv | BO-1600d-3 |
| 08 | [08_TICKET-20260706-BO-1600d-3-v.md](./08_TICKET-20260706-BO-1600d-3-v.md) | When a worktree's cache-tree is poisoned, recovery rebuilds via a fresh worktree | BO-1600d-3-v | BO-1600d-3 |
| 09 | [09_TICKET-20260706-BO-1600d-3-vi.md](./09_TICKET-20260706-BO-1600d-3-vi.md) | In a large object store, recovery removes only the detected corrupt objects, never every empty file | BO-1600d-3-vi | BO-1600d-3 |
| 10 | [10_TICKET-20260706-BO-1600d-4.md](./10_TICKET-20260706-BO-1600d-4.md) | Any project that installs leafcutter and runs build.py gets the recovery helper the same way | BO-1600d-4 | BO-1600d, BO-1600d-1, BO-1600d-3 |

## Dependencies

```
BO-1600d-1 (no dependencies)
BO-1600d-2 -> BO-1600d-1
BO-1600d-3 -> BO-1600d-1, BO-1600d-2
BO-1600d-3-i -> BO-1600d-3
BO-1600d-3-ii -> BO-1600d-3
BO-1600d-3-iii -> BO-1600d-3
BO-1600d-3-iv -> BO-1600d-3
BO-1600d-3-v -> BO-1600d-3
BO-1600d-3-vi -> BO-1600d-3
BO-1600d-4 -> BO-1600d-1, BO-1600d-3
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |

