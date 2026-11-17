---
title: "One workspace maker: every piece of separate work gets its workspace one dependable way (BO-4300)"
date: "2026-10-20"
time: "09:00"
type: manual
components: 
  - worktree_manager
  - build_orchestration
  - commit_guardian
  - build_pipeline
summary: "Every route that needs a separate workspace (build-feature, build-ticket, fast lane, plan-feature, quick-fix, finalize) now asks one workspace maker, scripts/worktree.py, and takes its answer word for word; the former ways of making, finding or clearing a workspace are retired."
description: "EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, 17 tickets. The maker (templates/scripts/worktree.py with worktree_*.py and workspace_root.py) makes each workspace as a clone with its own built install, proves it ready (stage canaries for pre-commit, commit-msg and post-merge fire before 'ready'), answers in one JSON shape, reuses or refuses an occupied location by name, clears a workspace only when no unsent work would be lost, and passes the project's durable log root to the workspace build (INF-500d-4-iii). Workflows dispatch their shell steps to the new shell-runner agent (ADR-070). Retired: scripts/ and templates/scripts/setup_ticket_worktree.py, worktree_repo_facts.py's facts/base/branch-standing lookups, git_recovery.py's worktree re-add fallback, and every hand-written workspace recipe in agents, skills, workflows, commands, CLAUDE.md and the how-tos; a repo-wide census test keeps them gone. build.py refuses an implicit build into the package repository itself (ADR-001 Amendment 1). New check registrations carry remedy declarations; check-workflow-meta checks only top-level workflows. Docs: docs/how-to/get-a-workspace.md, docs/reference/workspace-maker-answer.md, C3 diagrams c3-031 and c3-034. Migration: re-run the build so the deployed workflows, agents and the maker match; sessions need the shell-runner agent installed. Pending after merge: deleting the stale leafcutter-ai/.leafcutter/ install in a developer's main checkout (decision dec-02bc263515e9d362)."
commits: []
breaking: true
migration_steps: 
  - Re-run the build (python scripts/build.py, or with --target-dir <install>) so the deployed workflows, agents and the workspace maker match this release.
  - Start new Claude sessions after the build so the shell-runner agent is installed; workflows dispatch their shell steps to it.
  - Make workspaces only through the maker (scripts/worktree.py ensure); see docs/how-to/get-a-workspace.md. Scripts or notes that call setup_ticket_worktree.py or worktree_repo_facts.py facts/base must switch to the maker.
  - In the package repository, pass an explicit --target-dir to build.py; an implicit build into the package repository is now refused.
---

## Entry
