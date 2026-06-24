---
title: "Changelog EPIC-GoalToEpicLeafFilter — 2026-06-22"
date: "2026-06-22"
time: "14:41"
type: manual
components: 
  - ac_store
summary: "Released AC store leaf filtering and cycle-resilient store-wide scan, allowing callers to exclude done or superseded leaves from traversal results and preventing hard failures on cross-epic dependency cycles."
description: "1 commit (5b4d5c1, PR #136). Features: traverse_ac_tree() and _dfs_collect_leaves() now accept exclude_done and exclude_superseded keyword parameters (ACD-1200a-10); store-wide scan degrades dependency cycles to WARNING/exit-0 while intra-epic cycles still hard-fail via CyclicDependencyError (ACD-1200c-3). Tests: 14 new tests in test_leaf_filter.py and test_scan_ac_store_cycle.py."
pr: 136
commits: 
  - 5b4d5c1
---

## Entry
