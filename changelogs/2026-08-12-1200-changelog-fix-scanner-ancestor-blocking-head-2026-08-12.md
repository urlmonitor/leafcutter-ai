---
title: "Changelog fix/scanner-ancestor-blocking..HEAD — 2026-08-12"
date: "2026-08-12"
time: "12:00"
type: manual
components: 
  - ac_store
  - ac_driven_dev
summary: "Fixed a bug in the AC store scanner that caused 56% of the live backlog to self-block, restoring the ready list from 20 to 437 actionable ACs for the /build-ac workflow."
description: "1 commit (6a1b792df). Bug Fixes: scan_ac_store.py _classify_ac now excludes transitive parent-hierarchy ancestors from blocking evaluation. Added _get_ancestor_ids() helper and a null-id guard. 4 behavioral tests added in unit_tests/ac_store/test_acd_400a_3.py. Covers AC ACD-400a-3."
commits: 
  - 6a1b792df
breaking: false
---

## Entry
