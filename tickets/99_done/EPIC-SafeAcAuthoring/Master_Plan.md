---
epic_name: EPIC-SafeAcAuthoring
created: 2026-06-24
status: in_progress
components:
  - build_orchestration
source_ac: BO-1500
---
# EPIC-SafeAcAuthoring

## Goal

This epic implements AC BO-1500: Authoring requirements never disturbs your work and always lands safely on main. It consists of 19 ticket(s) generated from the leaf ACs beneath BO-1500, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260624-BO-1500a-1.md](./01_TICKET-20260624-BO-1500a-1.md) | Authoring runs in a dedicated worktree on a new branch cut from origin/main | BO-1500a-1 | BO-1500a |
| 02 | [02_TICKET-20260624-BO-1500a-1-i.md](./02_TICKET-20260624-BO-1500a-1-i.md) | An existing authoring worktree/branch from a prior run is reused, not blindly recreated | BO-1500a-1-i | BO-1500a-1 |
| 03 | [03_TICKET-20260624-BO-1500a-2.md](./03_TICKET-20260624-BO-1500a-2.md) | The original checkout and any concurrent worktree are left untouched | BO-1500a-2 | BO-1500a, BO-1500a-1 |
| 04 | [04_TICKET-20260624-BO-1500a-3.md](./04_TICKET-20260624-BO-1500a-3.md) | Sequence diagram of the isolated-authoring worktree lifecycle | BO-1500a-3 | BO-1500a-1, BO-1500a-2 |
| 05 | [05_TICKET-20260624-BO-1500b-1.md](./05_TICKET-20260624-BO-1500b-1.md) | Each authoring stage commits its AC files before the next stage starts | BO-1500b-1 | BO-1500b, BO-1500a-1 |
| 06 | [06_TICKET-20260624-BO-1500b-1-i.md](./06_TICKET-20260624-BO-1500b-1-i.md) | The fresh authoring worktree is bootstrapped so pre-commit hooks do not silently skip | BO-1500b-1-i | BO-1500b-1 |
| 07 | [07_TICKET-20260624-BO-1500b-2.md](./07_TICKET-20260624-BO-1500b-2.md) | A crash mid-pipeline leaves completed stages committed and resumable | BO-1500b-2 | BO-1500b, BO-1500b-1 |
| 08 | [08_TICKET-20260624-BO-1500b-3.md](./08_TICKET-20260624-BO-1500b-3.md) | Partial-run recovery pre-flight still detects stranded AC files on the isolated branch | BO-1500b-3 | BO-1500b, BO-1500a-1 |
| 09 | [09_TICKET-20260624-BO-1500b-4.md](./09_TICKET-20260624-BO-1500b-4.md) | State diagram of the resumable per-stage authoring lifecycle | BO-1500b-4 | BO-1500b-1, BO-1500b-2 |
| 10 | [10_TICKET-20260624-BO-1500c-1.md](./10_TICKET-20260624-BO-1500c-1.md) | Final approval pushes the authoring branch and opens a PR to main automatically | BO-1500c-1 | BO-1500c, BO-1500a-1 |
| 11 | [11_TICKET-20260624-BO-1500c-1-i.md](./11_TICKET-20260624-BO-1500c-1-i.md) | Cancelling before final approval leaves draft ACs on the branch and opens no PR | BO-1500c-1-i | BO-1500c-1 |
| 12 | [12_TICKET-20260624-BO-1500c-2.md](./12_TICKET-20260624-BO-1500c-2.md) | The authoring PR passes the same CI gates as any other change | BO-1500c-2 | BO-1500c, BO-1500c-1 |
| 13 | [13_TICKET-20260624-BO-1500c-3.md](./13_TICKET-20260624-BO-1500c-3.md) | AC files are never committed directly onto main during authoring | BO-1500c-3 | BO-1500c, BO-1500c-1 |
| 14 | [14_TICKET-20260624-BO-1500c-4.md](./14_TICKET-20260624-BO-1500c-4.md) | How-to guide for delivering approved ACs via the reviewed PR path | BO-1500c-4 | BO-1500c-1 |
| 15 | [15_TICKET-20260624-BO-1500c-5.md](./15_TICKET-20260624-BO-1500c-5.md) | Sequence diagram of the approval-to-PR delivery flow | BO-1500c-5 | BO-1500c-1, BO-1500c-2 |
| 16 | [16_TICKET-20260624-BO-1500d-1.md](./16_TICKET-20260624-BO-1500d-1.md) | The PR number and URL are reported back to the user the moment the PR is opened | BO-1500d-1 | BO-1500d, BO-1500c-1 |
| 17 | [17_TICKET-20260624-BO-1500e-1.md](./17_TICKET-20260624-BO-1500e-1.md) | Authoring works when invoked while checked out on protected main (the common case) | BO-1500e-1 | BO-1500e, BO-1500a-1 |
| 18 | [18_TICKET-20260624-BO-1500e-2.md](./18_TICKET-20260624-BO-1500e-2.md) | Authoring works when run from a deployed/installed copy, not just the dev layout | BO-1500e-2 | BO-1500e, BO-1500a-1 |
| 19 | [19_TICKET-20260624-BO-1500e-3.md](./19_TICKET-20260624-BO-1500e-3.md) | PR creation tolerates the active gh account silently reverting to an EMU account | BO-1500e-3 | BO-1500e, BO-1500c-1 |

## Dependencies

```
BO-1500a-1 (no dependencies)
BO-1500a-1-i -> BO-1500a-1
BO-1500a-2 -> BO-1500a-1
BO-1500a-3 -> BO-1500a-1, BO-1500a-2
BO-1500b-1 -> BO-1500a-1
BO-1500b-1-i -> BO-1500b-1
BO-1500b-2 -> BO-1500b-1
BO-1500b-3 -> BO-1500a-1
BO-1500b-4 -> BO-1500b-1, BO-1500b-2
BO-1500c-1 -> BO-1500a-1
BO-1500c-1-i -> BO-1500c-1
BO-1500c-2 -> BO-1500c-1
BO-1500c-3 -> BO-1500c-1
BO-1500c-4 -> BO-1500c-1
BO-1500c-5 -> BO-1500c-1, BO-1500c-2
BO-1500d-1 -> BO-1500c-1
BO-1500e-1 -> BO-1500a-1
BO-1500e-2 -> BO-1500a-1
BO-1500e-3 -> BO-1500c-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 04, 09, 15 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 |
| documentation-expert | 14 |
| llm-expert | 08 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 |
| python-coder | 01, 02, 03, 05, 06, 07, 10, 11, 12, 13, 16, 17, 18, 19 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 |

