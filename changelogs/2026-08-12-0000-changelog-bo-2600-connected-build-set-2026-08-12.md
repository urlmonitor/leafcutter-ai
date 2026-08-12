---
title: "Changelog BO-2600 — Connected Build Set — 2026-08-12"
date: "2026-08-12"
time: "00:00"
type: manual
components: 
  - build_orchestration
  - ac_driven_dev
  - ac_store
summary: "Released the connected-build-set feature: /build-ac now resolves a leaf AC's full dependency graph and generates a dependency-ordered epic instead of a single ticket when multiple ACs are connected."
description: "17 commits across feature/bo-2600-connected-build-set. Features: fast_lane.resolve_connected_build_set gained exclude_structural_parent parameter to skip derive_parent_id nodes in the depends_on walk (BO-2600a-1); --exclude-structural-parent CLI flag added to select_connected (BO-2600a-2); goal_to_epic gained build_epic_from_ids + --ids CLI for dependency-ordered epic assembly from an exact connected-set id list (BO-2600a-5); build-ac Step 2b now resolves the connected set — size=1 falls back to single-ticket path for backward compat (BO-2600a-3), size>1 routes to goal_to_epic --ids (BO-2600a-4). 33 files changed, 4586 insertions, 1860 deletions. Includes 4 new unit test suites (test_bo_2600a_1/2/4/5) and updated how-to docs for fast-lane-build and goal-to-epic."
commits: 
  - 9bf41049c
  - 814d9d840
  - 8c52b7c0d
  - 59c10bc06
  - 655b8f2d0
  - d7bd0686b
  - 64e31adb0
  - 3b20a0097
  - ff09b18fa
  - bf748a9fc
  - 0ffbfe0f9
  - 4c4336ca3
  - 4dd87a557
  - bbbc9116c
  - ba47d31ed
  - d1cc6911e
  - 50c1d7778
breaking: false
---

## Entry
