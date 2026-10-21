---
title: "Finishing a feature branch now closes only the tickets that branch was built to deliver"
date: "2026-10-21"
time: "14:02"
type: manual
components: 
  - build_orchestration
  - git_vcs_operations
  - ticket_lifecycle
summary: "Finishing a feature branch no longer closes every open ticket in the project; it closes only the tickets that branch was built for and changed itself (KI-BO-20260930)."
description: "Fast-lane build of BO-400e-3 (branch fast-lane/bo-400e-3), 2 commits (a740aa5c6, 2482c1474). /finalize-feature Step 3.5 used to close every inbox ticket store-wide. It now closes only what the branch was built to deliver and itself changed: on a single-ticket branch, the ticket recorded at setup plus its source AC; on an epic branch, its own epic-folder tickets. It halts before merging when it cannot tell what to close, or when those records have uncommitted edits. It no longer runs reset --hard. setup_ticket_worktree.py now records which ticket a branch was built for."
breaking: false
---

## Entry
