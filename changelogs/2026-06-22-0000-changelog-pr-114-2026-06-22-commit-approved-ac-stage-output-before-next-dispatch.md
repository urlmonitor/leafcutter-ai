---
title: "Changelog PR#114 — 2026-06-22 — Commit approved AC stage output before next dispatch"
date: "2026-06-22"
time: "00:00"
type: manual
components: 
  - skills_system
  - git_vcs_operations
  - testing_quality
  - ac_store
summary: "Released the plan-feature / create-ac workflow enhancement that commits each approved AC authoring stage to git before advancing, preventing data loss on crash and enforcing fail-closed pipeline behaviour across 10 tickets and 54 new behavioural tests."
description: "1 squash commit (1092a0c) from PR #114. Categories: Features (per-stage commit gate, partial-run recovery, fail-closed abort), Tests (54 vm.Script behavioural tests across 4 new test files), Maintenance (4 remediation tickets from post-build spot-check). Files: scripts/workflows/plan-feature.js, templates/workflows-js/plan-feature.js, templates/skills/create-ac/SKILL.md, 4 unit test files, ADR updates."
pr: 114
adrs: 
  - ADR-007
  - ADR-010
commits: 
  - 1092a0c
breaking: false
---

## Entry
