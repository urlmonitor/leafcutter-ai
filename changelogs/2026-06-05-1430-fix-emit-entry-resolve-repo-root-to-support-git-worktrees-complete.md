---
title: Fix emit_entry _resolve_repo_root() to support git worktrees complete
date: "2026-06-05"
time: "14:30"
type: ticket_completion
components: 
  - infrastructure
summary: Fixed _resolve_repo_root() worktree detection by using .exists() instead of .is_dir()
description: Changed _resolve_repo_root() from .is_dir() to .exists() so it correctly detects .git as a file in git worktrees. Fixes 8 test failures that occurred when emit_entry.py ran inside a worktree.
commits: 
  - cb02ac8
  - 0b11c47
  - 9189cbb
  - 3858baf
  - 95b8e50
ticket: "20260605-emit-entry-worktree-git-root"
---

## Entry
