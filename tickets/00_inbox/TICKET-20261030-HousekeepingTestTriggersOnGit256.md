---
title: "The BO-4300f-3-ii housekeeping test triggers automatic maintenance on git 2.56"
status: done
components:
  - build_orchestration
created: 2026-10-30
last_updated: 2026-10-30
depends_on: []
priority: high
roadmap_phase: phase_1
change_target: code
risk_surface: internal
requires_diagram: false
requires_adr: false
tags:
  - ci-red-on-main
  - git-2.56
---

# The BO-4300f-3-ii housekeeping test triggers automatic maintenance on git 2.56

## Actor / Goal
In order for main's CI to be green again, the control half of
`test_automatic_housekeeping_does_not_run_while_legacy_workspaces_remain` must trigger git's automatic
maintenance on every supported git version, so that the test still proves the cut-over blocks it.

## Context
- **Found:** 2026-10-29. Main's CI went red at d62440669. Every PR that runs the test fails, including #1347.
  - The GitHub runner moved from git 2.55.0 to 2.56.0 between 2026-10-26 and 10-29.
  - Locally, on git 2.52, the test passes.
- **Cause** (research 2026-10-30, with git RelNotes and sources):
  - Since git 2.54, porcelain auto-maintenance (`git commit`, `merge` and the rest) uses the
    `geometric` strategy by default. It no longer runs `gc --auto`, so the test's `gc.auto = 5`
    is not read.
  - The geometric-repack trigger `maintenance.geometric-repack.auto` defaulted to 100 in 2.54/2.55.
    git 2.56 raised it to 6700 to match `gc --auto`.
  - The test's 20 loose objects in `objects/17` estimate to 5120 objects. That is above the 2.55
    threshold (256), so the test packed there by coincidence, and below the 2.56 threshold (6912).
    So the control never packs, and the test fails with "proof is vacuous".
- **Product unaffected:** on 2.56, repo-local `maintenance.auto false` still stops every
  porcelain-triggered maintenance run before any task starts. All callers go through
  `prepare_auto_maintenance()`. A separate gap in `verify`, which checks only `gc.auto`, is filed as
  KI-BO-20261030-verify-trusts-gc-auto-alone.

## Acceptance Criteria
- [x] AC-1: The test's isolated global git config also sets `maintenance.geometric-repack.auto = 5`.
  The control project then packs on git versions whose default strategy is `gc` (governed by `gc.auto`)
  and on those whose default is `geometric` (governed by the geometric-repack threshold).
- [x] AC-2: The cut-over half still exercises git's real default strategy against the repo-local
  `maintenance.auto false` / `gc.auto 0`, with no other test or production change.
- [x] AC-3: The module docstring states which setting drives the trigger on which git versions.

## Implementation Tasks
- [x] Add `geometric-repack.auto = 5` to the `[maintenance]` section that `HousekeepingCase.setUp` writes.
- [x] Update the module docstring and add a DECISION HISTORY entry.
- [x] Run the test locally (git 2.52); CI (git 2.56) is the real proof.

## Risk & Safety
- Touches money? No.
- Touches data? No; test-only change.
- Reversibility: full.
