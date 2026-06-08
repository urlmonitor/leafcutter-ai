---
title: "Worktree Manager — Git Worktree Lifecycle"
description: "Git worktree lifecycle management component that creates, tracks, and tears down isolated branch environments for parallel epic and ticket development."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - worktree_manager
---

# Worktree Manager

## Overview

The Worktree Manager provides isolated branch environments for epic and ticket development using git worktrees. Each epic gets its own worktree so parallel tickets can proceed without cross-branch contamination.

## Responsibilities

- Create and register git worktrees for new epics
- Sweep orphan processes left behind after worktree teardown
- Provide the commit serialization lock (`epic-commit-lock`) used by ticket-supervisor

## Entry Points

- `scripts/worktree/sweep_processes.py` — orphan process cleanup
- `scripts/setup_ticket_worktree.py` — worktree provisioning script

## Safety Constraints

Per building-epics §1.4, worktrees MUST NOT be closed until all sub-tickets are done. The All-Tickets-Done gate (§1.4.1) enforces this by counting open tickets before allowing `worktree-agent` to run.
