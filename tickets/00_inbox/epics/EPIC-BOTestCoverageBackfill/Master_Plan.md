---
title: "EPIC: BO test-coverage backfill — make done honest with named green tests"
type: epic
status: todo
components:
  - build_orchestration
  - guardrail_engine
created: 2026-07-14
depends_on: []
requires_diagram: false
requires_adr: false
---

# EPIC: BO Test-Coverage Backfill

## Goal

Give every BO AC that is implemented-but-untested (or whose test doesn't name it,
or whose test is red on a deploy-layout path bug) a real, green, AC-naming test,
so `work_status: done` is always backed by verifiable coverage. 73 ACs across 6
epics. Per the 2026-07-14 rule: no AC is `done` without a linked green test.

## Context

See [reports/BO-AC-implementation-audit-2026-07-14.md](../../../../reports/BO-AC-implementation-audit-2026-07-14.md).
These are distinct from EPIC-BOPhantomDoneRemediation (which fixes wrong/orphaned
*code*); here the *code* is fine but the *test link* is missing or invalid.

## Tickets

| # | File | Epic | ACs | Depends On | Status |
|---|------|------|-----|------------|--------|
| 01 | [01_bo1700_test_coverage.md](./01_bo1700_test_coverage.md) | BO-1700 | 24 link-or-author + 5 author | — | `[ ]` |
| 02 | [02_bo210_test_coverage.md](./02_bo210_test_coverage.md) | BO-210 | 0 link-or-author + 12 author | — | `[ ]` |
| 03 | [03_bo500_test_coverage.md](./03_bo500_test_coverage.md) | BO-500 | 7 link-or-author + 7 author | — | `[ ]` |
| 04 | [04_bo400_test_coverage.md](./04_bo400_test_coverage.md) | BO-400 | 9 link-or-author + 0 author | — | `[ ]` |
| 05 | [05_bo1100_test_coverage.md](./05_bo1100_test_coverage.md) | BO-1100 | 6 link-or-author + 1 author | — | `[ ]` |
| 06 | [06_bo600_test_coverage.md](./06_bo600_test_coverage.md) | BO-600 | 0 link-or-author + 2 author | — | `[ ]` |
