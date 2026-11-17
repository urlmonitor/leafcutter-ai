---
title: "Four end-to-end tests now prove one durable log root serves every workspace (INF-500d-4)"
date: "2026-10-14"
time: "11:30"
type: manual
components: 
  - infrastructure
summary: "The promise that a report written inside a temporary workspace is still readable after that workspace is gone is now backed by four end-to-end tests. Its acceptance criterion stays open until its newest part, the rule-copies parity check, is built."
description: "Adds unit_tests/portability/test_inf_500d_4_e2e.py (4 tests, each tagged covers INF-500d-4) and the shared helper unit_tests/portability/_inf_500d_4_e2e_helpers.py. The tests use real git init, worktree add and worktree remove, a deployed install per worktree, the real writers run from inside a worktree, and the real readers (aggregate.py, harvest_learnings.py --print-sink, extract_epic_facts.py) after the worktree is removed; build.py is not spawned. They pass against code already on main and are regression coverage, not a red-first change; declaring each worktree own log root instead of the inherited one turned all four red as a discrimination check. INF-500d-4.yaml gained covered_by and implemented_by entries. It was flipped to done, then returned to todo when merging main, because PR #1193 added the child INF-500d-4-ix, which is still todo. The L1 INF-500d is not touched."
commits: 
  - 4cba9f5c9
  - 26ddfd0c6
breaking: false
---

## Entry
