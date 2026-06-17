---
title: "EPIC: AcPipelineConsolidation Mop-Up"
type: epic
status: done
components:
  - ticket_creation_pipeline
  - commit_guardian
  - skills_system
  - documentation_system
created: 2026-06-11
depends_on: []
source_ac: ACD-1100
priority: high
---

# EPIC: AcPipelineConsolidation Mop-Up

## Goal

Fix all residual issues found by the post-merge audit of EPIC-AcPipelineConsolidation (v2.0.0). Four categories of mop-up work: runtime-breaking workflow dispatch references to removed agents, 14 consolidation-residue test failures, ~85 stale agent name references across docs, and 7 orphaned agent card files plus 2 template cross-references.

Source AC: ACD-1100 (the consolidation epic parent). All four tickets are independent mop-up; none change the v2.0.0 architecture — they correct leftovers from incomplete implementation.

## Tickets

| # | File | Title | Priority | Depends On |
|---|------|-------|----------|------------|
| 01 | [01_workflow-dispatch-fixes.md](./01_workflow-dispatch-fixes.md) | Fix runtime-breaking workflow dispatch references to removed agents | critical | — |
| 02 | [02_test-path-corrections.md](./02_test-path-corrections.md) | Fix 14 consolidation-residue test failures (path and schema mismatches) | high | — |
| 03 | [03_docs-stale-agent-names.md](./03_docs-stale-agent-names.md) | Remove stale v3 agent names, test-planner refs, and /create-ac mentions from docs | medium | — |
| 04 | [04_orphaned-cards-template-refs.md](./04_orphaned-cards-template-refs.md) | Delete orphaned agent card files and fix template stale cross-references | medium | 03_docs-stale-agent-names.md |

## Dependencies

```
01 (no dependencies) — can run in parallel with 02 and 03
02 (no dependencies) — can run in parallel with 01 and 03
03 (no dependencies) — can run in parallel with 01 and 02
04 → depends on 03 (avoid grep-verification conflict during card deletions)
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| python-coder | 01, 02, 04 |
| test-writer | 02 |
| test-runner | 01, 02 |
| documentation-expert | 03, 04 |
| pr-reviewer | 01, 02, 03, 04 |
| commit | 01, 02, 03, 04 |
| pull-request | 01, 02, 03, 04 |
