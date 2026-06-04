---
title: Run build.py in worktrees after creation to populate .leafcutter/ build outputs complete
date: "2026-06-04"
time: "23:55"
type: ticket_completion
components: 
  - build_pipeline
summary: Automatic build.py invocation in worktree bootstrap ensures .leafcutter/ build outputs exist in fresh worktrees.
description: "Added automatic build.py invocation in _bootstrap() after poetry install so that .leafcutter/ build outputs (including .claude/workflows/) are present in freshly-created worktrees. Includes graceful degradation when build.py is absent or exits non-zero, plus ops knowledge item KI-3."
pr: 54
commits: 
  - ace235d
  - 03e332d
ticket: "TICKET-20260604-WorktreeBuildOutputs"
---

## Entry
