---
title: "The fast lane asks git where its worktree is, instead of trusting a path an agent typed"
date: "2026-09-07"
time: "14:05"
type: manual
components: 
  - build_orchestration
  - ac_driven_dev
  - build_pipeline
summary: "fast-lane-ship took the worktree location from an LLM phase agent, which twice reported a path it had composed rather than the one git created; the resolver then ran against a directory that did not exist and the lane halted."
description: "The worktree phase is an LLM agent asked to run create-fastlane-worktree and echo its JSON. It has twice returned a path it composed instead: 2026-08-11 on BO-2400f, and 2026-09-07 on UXP-700d, where it reported <repo_root>/worktrees/<slug> while git had placed the worktree at <workspace>/worktrees/<slug>. The resolver then invoked fast_lane.py under the non-existent path and the run halted at the resolve phase. The workflow already de-trusted this same agent for ac_store_path, with a comment recording the 2026-08-11 incident; worktree_path was left trusted and failed the same way. Recomputing the path in the workflow would have been the wrong fix and would have broken consumer installations: setup_ticket_worktree.py's _resolve_installed_layout() deliberately differs by layout, putting worktrees under the workspace PARENT in the dev layout and under the consumer project root when leafcutter is installed inside a consumer repo, so any single hardcoded <root>/worktrees/<slug> convention is correct in one layout and wrong in the other. git knows the true location in both, so the workflow now runs git worktree list --porcelain and requires the returned path to appear verbatim in that raw output -- a path absent from the output it was supposedly read from was invented, not quoted. An unconfirmed path halts with a message naming both the agent's claim and what git reported, rather than proceeding. Five structural tests were added; four fail against the unfixed workflow. The fifth is a forward guard asserting no <repo_root>/worktrees convention is reintroduced, and passes either way by design."
pr: None
adrs: []
commits: []
breaking: false
---

## Entry
