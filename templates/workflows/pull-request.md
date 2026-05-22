---
description: Slash-command surface for the pull-request agent. Invoke the agent directly.
---

{% if platform == 'claude' %}
Invoke the `pull-request` agent with the user's full request: $ARGUMENTS
{% elif platform == 'antigravity' %}
Invoke the `pull-request` agent by running its script via the terminal tool:
```bash
python .agents/agents/pull-request/scripts/run.py --args="$ARGUMENTS"
```
{% endif %}
