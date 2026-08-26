---
description: |
  Slash-command surface for documentation-expert.
  Invoked by /documentation; the documentation-expert agent owns this workflow.
---

<!-- Canonical slash-command body for /documentation.
     This file is loaded by documentation-expert when invoked via /documentation.
     Do not modify this file to add system-prompt logic -- put that in
     .claude/agents/documentation-expert.md instead. -->

{% if platform == 'claude' %}
Pass the user's request to the `documentation-expert` agent.
{% elif platform == 'antigravity' %}
Invoke the `documentation-expert` agent by running its script via the terminal tool:
```bash
python .agents/agents/documentation-expert/scripts/run.py --args="$ARGUMENTS"
```
{% endif %}
The agent will:

1. Read `config/doc_types.json` to anchor on the Diataxis genre mapping — the
   `description`, `writer_agent` and `default_path` for each genre. Path
   placeholders resolve against `config/paths.json`.
2. Classify the request by Diataxis intent (do / decide-record / design / look up / understand).
3. Dispatch to the matching specialist sub-agent(s) sequentially.
4. Return a unified payload listing every doc file produced.

If the user has not yet provided a subject or description for the documentation,
ask: "What would you like to document? Please describe the subject and what kind
of doc you need (how-to, ADR, architecture, reference, or explanation)."
