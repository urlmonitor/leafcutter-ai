---
epic_name: EPIC-QuickFixWorkflow
created: 2026-06-08
status: in_progress
components:
  - build-pipeline
source_ac: BP-600
---
# EPIC-QuickFixWorkflow

## Goal

This epic implements AC BP-600: Fix known bugs in minutes, not hours — without losing quality discipline. It consists of 16 ticket(s) generated from the leaf ACs beneath BP-600, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260608-BP-600a-1.md](./01_TICKET-20260608-BP-600a-1.md) | Quick-fix workflow operates in current worktree without branch switching | BP-600a-1 | BP-600a |
| 02 | [02_TICKET-20260608-BP-600a-2.md](./02_TICKET-20260608-BP-600a-2.md) | Quick-fix workflow does not invoke worktree-agent or feature skill | BP-600a-2 | BP-600a, BP-600a-1 |
| 03 | [03_TICKET-20260608-BP-600a-3.md](./03_TICKET-20260608-BP-600a-3.md) | Quick-fix workflow rejects invocation when target file has uncommitted changes | BP-600a-3 | BP-600a, BP-600a-1 |
| 04 | [04_TICKET-20260608-BP-600b-1.md](./04_TICKET-20260608-BP-600b-1.md) | Quick-fix workflow creates an AC YAML file in the AC store | BP-600b-1 | BP-600b, BP-600a-1 |
| 05 | [05_TICKET-20260608-BP-600b-2.md](./05_TICKET-20260608-BP-600b-2.md) | Quick-fix AC uses the correct component prefix and sequential ID | BP-600b-2 | BP-600b, BP-600b-1 |
| 06 | [06_TICKET-20260608-BP-600b-3.md](./06_TICKET-20260608-BP-600b-3.md) | Quick-fix AC persists after the fix ticket lifecycle closes | BP-600b-3 | BP-600b, BP-600b-1 |
| 07 | [07_TICKET-20260608-BP-600c-1.md](./07_TICKET-20260608-BP-600c-1.md) | Quick-fix workflow dispatches test-writer to create a failing test before the fix | BP-600c-1 | BP-600c, BP-600b-1 |
| 08 | [08_TICKET-20260608-BP-600c-2.md](./08_TICKET-20260608-BP-600c-2.md) | Quick-fix workflow runs the new test and confirms it fails (red phase) | BP-600c-2 | BP-600c, BP-600c-1 |
| 09 | [09_TICKET-20260608-BP-600d-1.md](./09_TICKET-20260608-BP-600d-1.md) | Quick-fix workflow accepts a structured diagnosis as input | BP-600d-1 | BP-600d, BP-600a-1 |
| 10 | [10_TICKET-20260608-BP-600d-2.md](./10_TICKET-20260608-BP-600d-2.md) | Quick-fix workflow dispatches python-coder to apply the fix after red-phase test | BP-600d-2 | BP-600d, BP-600c-2 |
| 11 | [11_TICKET-20260608-BP-600c-3.md](./11_TICKET-20260608-BP-600c-3.md) | Quick-fix workflow runs the test after the fix and confirms it passes (green phase) | BP-600c-3 | BP-600c, BP-600c-2, BP-600d-2 |
| 12 | [12_TICKET-20260608-BP-600d-3.md](./12_TICKET-20260608-BP-600d-3.md) | Quick-fix workflow dispatches commit agent after green-phase verification | BP-600d-3 | BP-600d, BP-600c-3 |
| 13 | [13_TICKET-20260608-BP-600d-4.md](./13_TICKET-20260608-BP-600d-4.md) | Quick-fix workflow pushes to origin and closes the ticket lifecycle | BP-600d-4 | BP-600d, BP-600d-3 |
| 14 | [14_TICKET-20260608-BP-600e-1.md](./14_TICKET-20260608-BP-600e-1.md) | Quick-fix workflow warns when the fix modifies more than the target file | BP-600e-1 | BP-600e, BP-600d-2 |
| 15 | [15_TICKET-20260608-BP-600e-2.md](./15_TICKET-20260608-BP-600e-2.md) | Quick-fix workflow warns when red-phase test reveals a deeper root cause | BP-600e-2 | BP-600e, BP-600c-2 |
| 16 | [16_TICKET-20260608-BP-600e-3.md](./16_TICKET-20260608-BP-600e-3.md) | Quick-fix workflow preserves progress when escalating to full build pipeline | BP-600e-3 | BP-600e, BP-600e-1, BP-600e-2 |

## Dependencies

```
BP-600a-1 (no dependencies)
BP-600a-2 -> BP-600a-1
BP-600a-3 -> BP-600a-1
BP-600b-1 -> BP-600a-1
BP-600b-2 -> BP-600b-1
BP-600b-3 -> BP-600b-1
BP-600c-1 -> BP-600b-1
BP-600c-2 -> BP-600c-1
BP-600c-3 -> BP-600c-2, BP-600d-2
BP-600d-1 -> BP-600a-1
BP-600d-2 -> BP-600c-2
BP-600d-3 -> BP-600c-3
BP-600d-4 -> BP-600d-3
BP-600e-1 -> BP-600d-2
BP-600e-2 -> BP-600c-2
BP-600e-3 -> BP-600e-1, BP-600e-2
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| llm-expert | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |

