---
epic_name: EPIC-IsolatedParallelDelivery
created: 2026-07-07
status: in_progress
components:
  - build_orchestration
source_ac: BO-1800
---
# EPIC-IsolatedParallelDelivery

## Goal

This epic implements AC BO-1800: Build many features in parallel, safely, like a real team. It consists of 28 ticket(s) generated from the leaf ACs beneath BO-1800, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260707-BO-1800a-1.md](./01_TICKET-20260707-BO-1800a-1.md) | Each drive runs in an independent copy with its own object store, isolated from every other drive | BO-1800a-1 | BO-1800a |
| 02 | [02_TICKET-20260707-BO-1800a-1-i.md](./02_TICKET-20260707-BO-1800a-1-i.md) | A drive killed mid-commit cannot corrupt any other drive's object store | BO-1800a-1-i | BO-1800a-1 |
| 03 | [03_TICKET-20260707-BO-1800a-1-ii.md](./03_TICKET-20260707-BO-1800a-1-ii.md) | A drive requested on a non-native filesystem is refused before it can start | BO-1800a-1-ii | BO-1800a-1 |
| 04 | [04_TICKET-20260707-BO-1800a-2.md](./04_TICKET-20260707-BO-1800a-2.md) | Drive copies are created by the fastest safe strategy available, in a fixed preference order | BO-1800a-2 | BO-1800a |
| 05 | [05_TICKET-20260707-BO-1800a-2-i.md](./05_TICKET-20260707-BO-1800a-2-i.md) | Reflink unsupported falls back cleanly to the next creation strategy | BO-1800a-2-i | BO-1800a-2 |
| 06 | [06_TICKET-20260707-BO-1800a-3.md](./06_TICKET-20260707-BO-1800a-3.md) | Removing a drive deletes both its working copy and its feature branch | BO-1800a-3 | BO-1800a |
| 07 | [07_TICKET-20260707-BO-1800a-4.md](./07_TICKET-20260707-BO-1800a-4.md) | Component diagram of the per-drive isolated-clone topology | BO-1800a-4 | BO-1800a, BO-1800a-1, BO-1800a-2 |
| 08 | [08_TICKET-20260707-BO-1800a-5.md](./08_TICKET-20260707-BO-1800a-5.md) | Sequence diagram of the drive create-run-remove lifecycle in an isolated clone | BO-1800a-5 | BO-1800a, BO-1800a-1, BO-1800a-2, BO-1800a-3 |
| 09 | [09_TICKET-20260707-BO-1800b-1.md](./09_TICKET-20260707-BO-1800b-1.md) | The hub's main accepts changes only through a pull request; direct push, force-push, and branch deletion are rejected server-side | BO-1800b-1 | BO-1800b |
| 10 | [10_TICKET-20260707-BO-1800b-1-i.md](./10_TICKET-20260707-BO-1800b-1-i.md) | An agent's direct push to main is rejected at the hub | BO-1800b-1-i | BO-1800b-1 |
| 11 | [11_TICKET-20260707-BO-1800b-2.md](./11_TICKET-20260707-BO-1800b-2.md) | Merges to main are performed by the merge queue only after required checks pass | BO-1800b-2 | BO-1800b |
| 12 | [12_TICKET-20260707-BO-1800b-3.md](./12_TICKET-20260707-BO-1800b-3.md) | No privileged bypass exists, and agents authenticate as a least-privilege identity with no direct-push right | BO-1800b-3 | BO-1800b, BO-1800b-1 |
| 13 | [13_TICKET-20260707-BO-1800b-3-i.md](./13_TICKET-20260707-BO-1800b-3-i.md) | An admin merge attempt on main is rejected outside the gate | BO-1800b-3-i | BO-1800b-3 |
| 14 | [14_TICKET-20260707-BO-1800b-4.md](./14_TICKET-20260707-BO-1800b-4.md) | Sequence diagram of the gated PR-to-merge-queue landing flow | BO-1800b-4 | BO-1800b, BO-1800b-1, BO-1800b-2, BO-1800b-3 |
| 15 | [15_TICKET-20260707-BO-1800b-5.md](./15_TICKET-20260707-BO-1800b-5.md) | Reference doc for the hub main-branch protection and merge-queue configuration | BO-1800b-5 | BO-1800b, BO-1800b-1, BO-1800b-2, BO-1800b-3 |
| 16 | [16_TICKET-20260707-BO-1800c-1.md](./16_TICKET-20260707-BO-1800c-1.md) | The number of agents collaborating on a single feature is capped | BO-1800c-1 | BO-1800c |
| 17 | [17_TICKET-20260707-BO-1800c-1-i.md](./17_TICKET-20260707-BO-1800c-1-i.md) | An inherently sequential task is not force-parallelized | BO-1800c-1-i | BO-1800c-1 |
| 18 | [18_TICKET-20260707-BO-1800c-2.md](./18_TICKET-20260707-BO-1800c-2.md) | The number of independent features in flight is not capped by a fixed limit | BO-1800c-2 | BO-1800c, BO-1800a-1 |
| 19 | [19_TICKET-20260707-BO-1800c-3.md](./19_TICKET-20260707-BO-1800c-3.md) | Scheduling is host-resource-aware and sheds idle drives under memory pressure | BO-1800c-3 | BO-1800c, BO-1800c-2 |
| 20 | [20_TICKET-20260707-BO-1800c-4.md](./20_TICKET-20260707-BO-1800c-4.md) | Reference doc for the two parallelism axes and the resource-aware scheduler | BO-1800c-4 | BO-1800c, BO-1800c-1, BO-1800c-2, BO-1800c-3 |
| 21 | [21_TICKET-20260707-BO-1800d-1.md](./21_TICKET-20260707-BO-1800d-1.md) | Automatic garbage collection and maintenance are disabled inside a drive clone during a drive | BO-1800d-1 | BO-1800d, BO-1800a-1 |
| 22 | [22_TICKET-20260707-BO-1800d-1-i.md](./22_TICKET-20260707-BO-1800d-1-i.md) | No background auto-gc fires mid-drive even after the loose-object threshold is passed | BO-1800d-1-i | BO-1800d-1 |
| 23 | [23_TICKET-20260707-BO-1800d-2.md](./23_TICKET-20260707-BO-1800d-2.md) | Garbage collection runs only single-writer, between drives | BO-1800d-2 | BO-1800d |
| 24 | [24_TICKET-20260707-BO-1800e-1.md](./24_TICKET-20260707-BO-1800e-1.md) | No drive step commits to a local main; a clone's main is a read-only tracking branch | BO-1800e-1 | BO-1800e, BO-1800a-1 |
| 25 | [25_TICKET-20260707-BO-1800e-1-i.md](./25_TICKET-20260707-BO-1800e-1-i.md) | An attempt to commit onto local main during a drive is prevented or flagged | BO-1800e-1-i | BO-1800e-1 |
| 26 | [26_TICKET-20260707-BO-1800e-2.md](./26_TICKET-20260707-BO-1800e-2.md) | Scaffold and finalize bookkeeping lands via a branch and pull request, never a direct local-main commit | BO-1800e-2 | BO-1800e, BO-1800b-2 |
| 27 | [27_TICKET-20260707-BO-1800e-3.md](./27_TICKET-20260707-BO-1800e-3.md) | A developer's local main sync is fetch plus fast-forward-only (read-only) | BO-1800e-3 | BO-1800e |
| 28 | [28_TICKET-20260707-BO-1800e-4.md](./28_TICKET-20260707-BO-1800e-4.md) | Reference doc for the no-shared-local-main model and read-only main sync | BO-1800e-4 | BO-1800e, BO-1800e-1, BO-1800e-2, BO-1800e-3 |

## Dependencies

```
BO-1800a-1 (no dependencies)
BO-1800a-1-i -> BO-1800a-1
BO-1800a-1-ii -> BO-1800a-1
BO-1800a-2 (no dependencies)
BO-1800a-2-i -> BO-1800a-2
BO-1800a-3 (no dependencies)
BO-1800a-4 -> BO-1800a-1, BO-1800a-2
BO-1800a-5 -> BO-1800a-1, BO-1800a-2, BO-1800a-3
BO-1800b-1 (no dependencies)
BO-1800b-1-i -> BO-1800b-1
BO-1800b-2 (no dependencies)
BO-1800b-3 -> BO-1800b-1
BO-1800b-3-i -> BO-1800b-3
BO-1800b-4 -> BO-1800b-1, BO-1800b-2, BO-1800b-3
BO-1800b-5 -> BO-1800b-1, BO-1800b-2, BO-1800b-3
BO-1800c-1 (no dependencies)
BO-1800c-1-i -> BO-1800c-1
BO-1800c-2 -> BO-1800a-1
BO-1800c-3 -> BO-1800c-2
BO-1800c-4 -> BO-1800c-1, BO-1800c-2, BO-1800c-3
BO-1800d-1 -> BO-1800a-1
BO-1800d-1-i -> BO-1800d-1
BO-1800d-2 (no dependencies)
BO-1800e-1 -> BO-1800a-1
BO-1800e-1-i -> BO-1800e-1
BO-1800e-2 -> BO-1800b-2
BO-1800e-3 (no dependencies)
BO-1800e-4 -> BO-1800e-1, BO-1800e-2, BO-1800e-3
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 07, 08, 14 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28 |
| documentation-expert | 09, 10, 11, 12, 13, 15, 20, 28 |
| llm-expert | 16, 17 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28 |
| python-coder | 01, 02, 03, 04, 05, 06, 18, 19, 21, 22, 23, 24, 25, 26, 27 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28 |

