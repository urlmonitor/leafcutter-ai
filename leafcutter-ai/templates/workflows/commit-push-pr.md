---
description: Orchestrates the full commit -> push -> PR chain via the commit and pull-request agents.
---

# commit-push-pr — Full Shipping Orchestrator

This workflow chains the `commit` agent (ticket 09) and the `pull-request` agent
(ticket 12) into a single user-facing flow.

## Chain

1. Invoke the `commit` agent with the user's full request: $ARGUMENTS
   - The commit agent stages changes, drafts a commit message, asks for
     confirmation, and runs `git commit` (auto-fixing pre-commit hook failures
     via precommit-autofix).
2. After the commit agent returns successfully, invoke the `pull-request` agent.
   - The pull-request agent drafts the PR title and body, asks for confirmation,
     then pushes and runs `gh pr create` (spawning `conflict-resolver` if
     a merge conflict is detected).
   - Note: the pull-request agent now includes a Merge-State Poll Gate after
     push (polling `mergeStateStatus` for up to 30 s) to prevent false-conflict
     failures caused by GitHub eventual-consistency lag. No changes are needed
     in this workflow file — the gate is implemented entirely in the agent prompt.

If the commit agent returns an error or the user cancels at the commit step,
stop -- do not proceed to the pull-request step.
