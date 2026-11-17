---
description: "Invoke the worktree-agent — the create action takes a branch or ticket path, the remove action takes a branch or workspace path. Both go through the workspace maker (scripts/worktree.py, docs/how-to/get-a-workspace.md)."
---

# /worktree — Workspace Lifecycle

This workflow is the slash-command surface for the `worktree-agent` (Haiku). The
agent never makes, finds or clears a workspace itself: it asks the workspace maker
(`scripts/worktree.py`; see `docs/how-to/get-a-workspace.md`).

Two actions of `/worktree` (both go through the workspace maker, `scripts/worktree.py`; see `docs/how-to/get-a-workspace.md`):
- the **create** action (`/worktree create <branch-or-ticket-path>`) asks the
  workspace maker's `ensure` verb for the workspace (a new one, or the ready one
  for the same work). Non-destructive, no confirmation required.
- the **remove** action (`/worktree` followed by `remove` and a branch or workspace
  path) delegates to `close-worktree`, which asks the maker's `remove` verb to clear
  the workspace, with a confirmation gate (must type **"yes"** after the
  safety-check report). Refuses if uncommitted changes exist.

{% if platform == 'claude' %}
Forward `$ARGUMENTS` verbatim to the `worktree-agent`.
{% elif platform == 'antigravity' %}
Invoke the `worktree-agent` by running its script via the terminal tool:
```bash
python .agents/agents/worktree-agent/scripts/run.py --args="$ARGUMENTS"
```
{% endif %}
