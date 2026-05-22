---
description: "Internal slash-command surface for the epic-supervisor agent. Walks an epic ticket-by-ticket; the user-facing entry is /build-feature (built in ticket 09 of EPIC-AgentSupervisor)."
---

# /epic-supervisor — Internal Epic Driver

This workflow is the **internal** slash-command surface for the
`epic-supervisor` agent. The user-facing entry point is `/build-feature`
(shipped by ticket 09 of EPIC-AgentSupervisor); this workflow is the hook
that the pipeline uses today, before `/build-feature` exists.

Resolve `$ARGUMENTS` to an epic folder under `tickets/`:

- If `$ARGUMENTS` is an absolute path or a path under `tickets/`, pass it
  through verbatim as `epic_path`.
- Otherwise, treat `$ARGUMENTS` as an `epic_name` (e.g. `EPIC-Foo`); the
  agent will search `tickets/01_todo/` first, then
  `tickets/00_inbox/epics/`.

{% if platform == 'claude' %}
Invoke the `epic-supervisor` agent with the resolved input via the `Agent` tool.
{% elif platform == 'antigravity' %}
Invoke the `epic-supervisor` agent by running its script via the terminal tool:
```bash
python .agents/agents/epic-supervisor/scripts/run.py --args="<resolved_input>"
```
{% endif %}
The agent loads `.agents/skills/building-epics/SKILL.md` (or equivalent runbook) as its primary runbook and
walks the epic per spec §6.1.
