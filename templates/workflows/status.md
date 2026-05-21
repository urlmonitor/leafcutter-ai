---
description: "Invoke the status-checker agent — investigates ticket state, can close/move tickets and make small ticket-only fixes."
---

# /status — Status Checker

This workflow is the slash-command surface for the `status-checker` agent.

The agent reads the ticket, checks git history for matching commits, calls
`prod-puller` for prod-scope tickets, and (only on explicit user request)
closes the ticket by updating frontmatter status to `done` and moving the
file to a `done/` subfolder. Code edits are out of scope — defer to
`python-coder` / `sql-coder`.

Forward `$ARGUMENTS` verbatim to the `status-checker` agent.
