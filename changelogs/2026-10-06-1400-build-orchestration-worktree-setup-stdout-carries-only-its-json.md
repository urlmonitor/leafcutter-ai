---
title: "Build orchestration: worktree setup's stdout carries only its JSON reply"
date: "2026-10-06"
time: "14:00"
type: manual
components: 
  - build_orchestration
summary: "/plan-feature no longer halts with 'named no workspace directory' after creating the authoring worktree."
description: "setup_ticket_worktree.py create-ac-worktree answers with one JSON line on stdout, but the processes it starts during bootstrap (the pre-commit shim installer, git submodule update, the dependency install and build.py) inherited that stdout. Their progress lines came before the JSON, so /plan-feature could not parse the reply and halted every run with setup_failure_kind no_workspace_named, even though the worktree had been created. Those child processes now write to stderr. Fixed in both shipped copies (scripts/ and templates/scripts/, which have diverged); the touched calls were also condensed so the oversized files shrink. 1 commit (BO-1500a-1-ii)."
commits: 
  - 3f4504c1b21daa8c1fccb4c4449967dd1fdb9b3d
---

## Entry
