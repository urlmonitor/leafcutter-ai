---
epic_name: EPIC-CommitAcOutputPerStage
created: 2026-06-18
status: in_progress
components:
  - ac-driven-dev
source_ac: ACD-300g
---
# EPIC-CommitAcOutputPerStage

## Goal

This epic implements AC ACD-300g: Each stage's AC output is committed to git before the workflow advances to the next stage. It consists of 6 ticket(s) generated from the leaf ACs beneath ACD-300g, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260618-ACD-300g-1.md](./01_TICKET-20260618-ACD-300g-1.md) | Approved stage output is committed before the next agent is dispatched | ACD-300g-1 | ACD-300g |
| 02 | [02_TICKET-20260618-ACD-300g-1-i.md](./02_TICKET-20260618-ACD-300g-1-i.md) | Commit failure aborts the pipeline with an actionable error | ACD-300g-1-i | ACD-300g-1 |
| 03 | [03_TICKET-20260618-ACD-300g-2.md](./03_TICKET-20260618-ACD-300g-2.md) | The commit includes only AC files from the current stage | ACD-300g-2 | ACD-300g |
| 04 | [04_TICKET-20260618-ACD-300g-2-i.md](./04_TICKET-20260618-ACD-300g-2-i.md) | Partial-run recovery: uncommitted AC files from a prior crashed session are detected | ACD-300g-2-i | ACD-300g-2 |
| 05 | [05_TICKET-20260618-ACD-300g-3.md](./05_TICKET-20260618-ACD-300g-3.md) | The commit message identifies the workflow run, stage, and AC IDs produced | ACD-300g-3 | ACD-300g |
| 06 | [06_TICKET-20260618-ACD-300g-4.md](./06_TICKET-20260618-ACD-300g-4.md) | Cancel or abort does not commit -- draft files remain on disk uncommitted | ACD-300g-4 | ACD-300g |

## Dependencies

```
ACD-300g-1 (no dependencies)
ACD-300g-1-i -> ACD-300g-1
ACD-300g-2 (no dependencies)
ACD-300g-2-i -> ACD-300g-2
ACD-300g-3 (no dependencies)
ACD-300g-4 (no dependencies)
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05, 06 |
| pr-reviewer | 01, 02, 03, 04, 05, 06 |
| pull-request | 01, 02, 03, 04, 05, 06 |
| python-coder | 01, 02, 03, 04, 05, 06 |
| test-runner | 01, 02, 03, 04, 05, 06 |
| test-writer | 01, 02, 03, 04, 05, 06 |

