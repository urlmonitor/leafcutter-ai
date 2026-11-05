---
title: "Changelog 65725dfb0 — skill-reference gate proven from a deployed consumer layout (INF-700b-2-i)"
date: "2026-10-23"
time: "16:44"
type: manual
components: 
  - commit_guardian
  - skill_registry
summary: "Added tests proving that the commit-time skill-reference check works correctly in a project that has installed the package, and marked the related work items done."
description: "1 commit (test: 1). New unit_tests/commit_guardian/test_inf_700b_2_i.py (5 tests, 7 cases) copies the built hook into a private consumer repo and shows the gate refuses a package template naming a missing skill, passes a consistent tree, fails rather than passes when the skills directory, registry validator or manifest is missing, and scans the consumer own package copy even through a symlinked .leafcutter. INF-700b-2-i and parent INF-700b-2 are now done. No production code changed."
commits: 
  - 65725dfb0
breaking: false
---

## Entry
