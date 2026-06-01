---
description: "Invoke the commit agent — confirmation-gated git commit with precommit-autofix loop."
---

# /commit — Commit Agent

This workflow is the slash-command surface for the `commit` agent.

The agent always shows the planned commit message and file list before
issuing `git commit`. On pre-commit hook failure, it invokes the
`precommit-autofix` skill (Haiku for mechanical fixes, Sonnet for
structural) and retries once. Refuses `--no-verify` and force-push
without explicit user authorisation per the Git Safety Protocol.

{% if platform == 'claude' %}
Forward `$ARGUMENTS` verbatim to the `commit` agent.
{% elif platform == 'antigravity' %}
Invoke the `commit` agent by running its script via the terminal tool:
```bash
python .agents/agents/commit/scripts/run.py --args="$ARGUMENTS"
```
{% endif %}
