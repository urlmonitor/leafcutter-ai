---
epic_name: EPIC-CommitAcOutputPerStage
created: 2026-06-18
status: in_progress
components:
  - ac_driven_dev
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
| 07 | [07_TICKET-20260622-Fix_Commit_Delegation_And_Failclosed.md](./07_TICKET-20260622-Fix_Commit_Delegation_And_Failclosed.md) | Fix commitStageOutput: hook-safe commit path + fail closed on unparseable output | ACD-300g-1 | 01, 02 |
| 08 | [08_TICKET-20260622-Fix_Staging_Discovery_And_Match.md](./08_TICKET-20260622-Fix_Staging_Discovery_And_Match.md) | Fix stage staging: discover untracked AC files + exact AC-ID match | ACD-300g-2 | 03 |
| 09 | [09_TICKET-20260622-Implement_Partial_Run_Recovery_In_Workflow.md](./09_TICKET-20260622-Implement_Partial_Run_Recovery_In_Workflow.md) | Implement partial-run recovery scan in plan-feature.js (not just SKILL.md) | ACD-300g-2-i | 04, 07 |
| 10 | [10_TICKET-20260622-Fix_Final_Gate_Edit_And_Commit_Message.md](./10_TICKET-20260622-Fix_Final_Gate_Edit_And_Commit_Message.md) | Fix final-gate edit-fallthrough + run id in commit message + canonical labels | ACD-300g-4 | 05, 06 |

> **Remediation batch (07-10), added 2026-06-22.** Post-build spot-check (3 angle-testing agents)
> found the original 6 tickets shipped green but the feature does not work as-built: the per-stage
> commit collides with the commit-delegation hook, ticket 04's partial-run recovery was written as
> SKILL.md prose instead of executable code (phantom-done), the staging defeats ACD-300g-2 under
> realistic inputs, and the final gate auto-approves on repeated edit. Tickets 07-10 fix these
> against the real integration point (scripts/workflows/plan-feature.js).

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

