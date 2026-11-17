---
title: "Changelog 1d316e0a0 — a new workspace's files and HEAD can no longer disagree"
date: "2026-10-25"
time: "19:10"
type: manual
components: 
  - worktree_manager
summary: "A new workspace's line of work now starts exactly where its files are, or the workspace maker refuses; an outside fetch during creation can no longer leave HEAD on one commit and the files on another."
description: "One commit (1d316e0a0, fix). ensure resolves the base to one SHA, builds the line with checkout --no-track -B <branch> <sha> and verifies HEAD == sha and a clean tree (else VERIFY_FAILED, step verify-checkout). A created workspace never runs the set-aside. base_is_fresh and base_matches_origin_main use the built-from SHA. The clone uses a temporary remote (leafcutter-src), so origin never names the main checkout. A resumed line whose local branch holds commits the hub lacks is refused WORK_AT_RISK. New lines no longer track origin/main. Ticket 11 of EPIC-WorkspaceMakerHardening (BO-4300a-1 IT3, BO-4300c-1)."
adrs: []
commits: 
  - 1d316e0a0
breaking: false
---

## Entry
