---
epic_name: EPIC-LocalSignoffGates
created: 2026-06-24
status: in_progress
components:
  - build-orchestration
source_ac: BO-570
priority: medium
---
# EPIC-LocalSignoffGates

## Goal

Implements AC **BO-570** — "Render and lint defects are caught locally at sign-off, before the PR or CI." Adds two local verification gates to the phase-agent sign-off so render-time-only failures and lint violations are caught **before commit/PR/CI**, not after. Nine tickets generated from the leaf ACs beneath BO-570, in topological build order (runners before the gates that consume them).

## Context

This epic is a process fix for two real defect classes that escaped local sign-off and only failed at the PR/CI stage:

- An **`ssr:false` render bug** that only throws at route-render time — static and lint checks passed, local sign-off marked the ticket done, and the defect reached PR/CI.
- **Ruff lint failures** on new files where the worktree pre-commit gap meant repo-ruff never ran locally, so the violations surfaced for the first time in CI.

The design splits each gate across the owner boundary: a deterministic **runner** (python-coder) produces a three-state verdict (`success | failure | tooling-unavailable`), and a **sign-off gate** (llm-expert, in the coder-agent templates + `signoff` skill) consumes that verdict and blocks on it. Both gates are **blocking, never advisory**; "tooling unavailable in the worktree" is a distinct *inconclusive* outcome that can never silently pass.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260624-BO-570-1.md](./01_TICKET-20260624-BO-570-1.md) | Deterministic render-smoke runner helper for the frontend sign-off gate | BO-570-1 | BO-570 |
| 02 | [02_TICKET-20260624-BO-570-2.md](./02_TICKET-20260624-BO-570-2.md) | Frontend sign-off gate blocks on render failure using the render-smoke verdict | BO-570-2 | BO-570, BO-570-1 |
| 03 | [03_TICKET-20260624-BO-570-2-i.md](./03_TICKET-20260624-BO-570-2-i.md) | No frontend files changed -- dev-render smoke check is skipped, not failed | BO-570-2-i | BO-570-2 |
| 04 | [04_TICKET-20260624-BO-570-2-ii.md](./04_TICKET-20260624-BO-570-2-ii.md) | Render tooling unavailable in the worktree surfaces clearly and never silently passes | BO-570-2-ii | BO-570-2 |
| 05 | [05_TICKET-20260624-BO-570-3.md](./05_TICKET-20260624-BO-570-3.md) | Deterministic repo-ruff runner helper for the python sign-off gate | BO-570-3 | BO-570 |
| 06 | [06_TICKET-20260624-BO-570-4.md](./06_TICKET-20260624-BO-570-4.md) | Python sign-off gate blocks on lint failure using the repo-ruff verdict | BO-570-4 | BO-570, BO-570-3 |
| 07 | [07_TICKET-20260624-BO-570-2-iii.md](./07_TICKET-20260624-BO-570-2-iii.md) | A locally-passing render or ruff check records auditable evidence in the sign-off | BO-570-2-iii | BO-570-2, BO-570-4 |
| 08 | [08_TICKET-20260624-BO-570-4-i.md](./08_TICKET-20260624-BO-570-4-i.md) | No Python files changed -- repo-ruff check is skipped, not failed | BO-570-4-i | BO-570-4 |
| 09 | [09_TICKET-20260624-BO-570-4-ii.md](./09_TICKET-20260624-BO-570-4-ii.md) | Ruff tooling unavailable in the worktree surfaces clearly and never silently passes | BO-570-4-ii | BO-570-4 |

## Dependencies

```
BO-570-1 (no dependencies)
BO-570-2 -> BO-570-1
BO-570-2-i -> BO-570-2
BO-570-2-ii -> BO-570-2
BO-570-2-iii -> BO-570-2, BO-570-4
BO-570-3 (no dependencies)
BO-570-4 -> BO-570-3
BO-570-4-i -> BO-570-4
BO-570-4-ii -> BO-570-4
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| llm-expert | 02, 03, 04, 06, 07, 08, 09 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| python-coder | 01, 05 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09 |

## Parallelism

Two independent chains can run concurrently — there is no edge between the frontend and python stacks:

- **Frontend stack:** 01 (render runner) → 02 (gate) → {03, 04} edge cases
- **Python stack:** 05 (ruff runner) → 06 (gate) → {08, 09} edge cases
- **Join:** 07 (auditable-evidence L3) depends on both gates (02 and 06), so it runs last.

## Risk & Safety

- **Touches money?** No.
- **Touches data?** No — changes are to agent templates, the `signoff` skill, and two new deterministic helper scripts plus their tests. No schema or production data.
- **Reversibility?** Fully reversible — additive sign-off gates and helper scripts; revert the commits to remove. The gates fail safe (a blocked/inconclusive sign-off halts rather than ships).

