---
title: "Fix user-surface-smoker feedback submission failing silently in worktrees complete"
date: "2026-06-03"
time: "22:30"
type: ticket_completion
components: 
  - build_pipeline
summary: "Fix silent feedback submission failure in worktrees by adding user-surface-smoker to allowed_writers"
description: "Added user-surface-smoker to allowed_writers in feedback_categories.yaml so smoke-test feedback submissions reach the JSONL sink instead of silently failing with exit code 1."
pr: 38
commits: 
  - 58aec42
  - b86c701
  - 67225b1
  - 0151a19
ticket: "TICKET-20260603-SmokerFeedbackSinkWorktree"
---

## Entry
