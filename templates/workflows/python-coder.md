---
description: "Invoke the python-coder agent for standards-enforcing Python implementation."
---

# /python-coder — Python Implementation

This workflow is the slash-command surface for the `python-coder` agent.

The agent pulls in `docs/conventions/`, runs `doc-enforcer` and
`complexity-reduction` before declaring done, and delegates cross-file
context to `research-agent` (no Grep/Glob/MCP search tools).

Forward `$ARGUMENTS` verbatim to the `python-coder` agent.
