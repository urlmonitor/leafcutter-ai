---
title: "Changelog EPIC-BOPhantomDoneRemediation — 2026-07-15"
date: "2026-07-15"
time: "00:00"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
  - ac_store
  - ticket_creation_pipeline
  - ticket_lifecycle
  - testing_quality
summary: "Fixed five phantom-done guard defects: orphaned commit-classifier and precommit-probe helpers wired into the active flow, done-folder detection corrected from edit-based to move-based, ticket frontmatter validation tightened to require change_target and estimated_complexity, and reference-pattern globs resolved to concrete paths at ticket-generation time."
description: "1 squash commit (PR #281, 5 tickets: BO-1100, BO-1700, BO-600, BO-400, BO-2000). Categories: Fixed (4), Changed (1). BO-1100 wired commit classifier and mixed-set detection into the commit agent and converted commit_message_patterns.json to array schema. BO-1700 wired dead precommit-probe helpers into run_checks(), added fail-closed on incomplete guardian build, and fixed core.hooksPath awareness. BO-600 strengthened ticket_frontmatter_guard to reject null/empty change_target, risk_surface, and estimated_complexity. BO-400 fixed done-folder prohibition to track git status=M moves, not in-place edits, with 99_done LEAFCUTTER_FINALIZE_ARCHIVE carve-out. BO-2000 resolved reference_pattern globs to concrete paths in the ticket generator. 22 files changed, 2937 insertions."
pr: 281
commits: 
  - 50e28cc1
breaking: false
---

## Entry
