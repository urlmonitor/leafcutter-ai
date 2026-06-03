---
title: "EPIC-MoveOnMainOnly: prevent ticket status corruption during worktree merges"
date: "2026-06-03"
time: 0000
type: feature
components: 
  - build_pipeline
summary: "Implement move-on-main-only pattern for ticket lifecycle folders"
description: "Ticket files no longer move between lifecycle folders on feature branches. Folder reconciliation happens on main after merge via finalize-feature.js Step 5b. Two new hooks: check_ticket_no_branch_move.py (pre-commit, blocks git mv of tickets on branches) and check_ticket_state_integrity.py (post-merge, warns about duplicates/misplacement). Also cleaned up 2 known duplicate tickets from 00_inbox."
pr: "#36"
tickets: 
  - EPIC-MoveOnMainOnly
breaking: false
scope: build_pipeline
---

## Entry
