---
description: "Invoke the commit workflow — confirmation-gated git commit with precommit-autofix loop; a refusal that names a specialist is handed to that specialist."
---

# /commit — Commit Agent

This workflow is the slash-command surface for the `commit` agent.

The agent always shows the planned commit message and file list before
issuing `git commit`. On pre-commit hook failure, it invokes the
`precommit-autofix` skill (Haiku for mechanical fixes, Sonnet for
structural) and retries once. A refusal whose hook names a specialist is
handed off to that specialist rather than fixed here. Refuses `--no-verify` and force-push
without explicit user authorisation per the Git Safety Protocol.

{% if platform == 'claude' %}
Invoke the `commit` workflow via the Workflow tool:

```
Workflow("commit", { arguments: $ARGUMENTS })
```

The workflow dispatches the `commit` agent. When a pre-commit hook refuses and
its remedy declaration names a specialist (e.g. `check-complexity` →
`restructuring-specialist`), the agent returns `status: handoff`; the workflow
engages that specialist once, then re-offers the same commit.

If the Workflow tool is unavailable, forward `$ARGUMENTS` verbatim to the
`commit` agent instead. If the agent returns `status: handoff`, show the user
the refusal, the named specialist, and the named skill; do NOT improvise a fix.
{% elif platform == 'antigravity' %}
Invoke the `commit` agent by running its script via the terminal tool:
```bash
python .agents/agents/commit/scripts/run.py --args="$ARGUMENTS"
```
{% endif %}
