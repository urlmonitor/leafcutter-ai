---
title: "The BO-4300f-3-ii housekeeping test triggers automatic maintenance on git 2.56"
date: "2026-10-30"
time: "12:00"
type: manual
components:
  - build_orchestration
summary: "Main's CI went red when GitHub's runner moved to git 2.56: the housekeeping test's control repo no longer packed, because git's default auto-maintenance (geometric strategy since 2.54) ignores gc.auto and 2.56 raised its trigger to 6700 loose objects. The test now also lowers maintenance.geometric-repack.auto, so the control packs on every git version. The product's protection (maintenance.auto false) still holds on 2.56."
description: >-
  unit_tests/build_orchestration/test_bo_4300f_3_ii.py: the isolated global
  config adds [maintenance "geometric-repack"] auto = 5. Filed
  KI-BO-20261030-verify-trusts-gc-auto-alone: workspace readiness checks
  gc.auto 0 but not maintenance.auto false, the setting that actually blocks
  housekeeping on git 2.54+. Ticket TICKET-20261030-HousekeepingTestTriggersOnGit256.
breaking: false
---

## Entry
