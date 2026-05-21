---
description: "Invoke the worktree-agent — /worktree create <branch-or-ticket-path> or /worktree remove <branch-or-worktree-path>."
---

# /worktree — Worktree Lifecycle

This workflow is the slash-command surface for the `worktree-agent` (Haiku).

Two actions:
- `/worktree create <branch-or-ticket-path>` — delegates to the `feature` skill
  (creates a new worktree or reuses the existing epic worktree). Non-destructive,
  no confirmation required.
- `/worktree remove <branch-or-worktree-path>` — delegates to `close-worktree`
  with a confirmation gate (must type **"yes"** after the safety-check report).
  Refuses if uncommitted changes exist.

Forward `$ARGUMENTS` verbatim to the `worktree-agent`.
