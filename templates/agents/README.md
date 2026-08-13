# leafcutter/templates/agents/

## What this directory contains

Single-file portable agent templates. Each `.md` file defines one agent: its YAML frontmatter
(description, model, tools) and the prompt body that is compiled into `.claude/agents/<name>.md`
by `leafcutter/scripts/build.py`.

Agent templates in this directory are **project-agnostic** — they contain no hardcoded project
paths, deploy commands, domain credentials, or project-specific table/module names.

## Layout asymmetry — flat templates, folder-shaped project context

Templates here are **flat single files** (`<agent-name>.md`). This is intentional and stable
across the current ~30 agent surface.

The project-side companion for each agent lives in a **folder-shaped** location:

```
.agents/agents/<agent-name>/PROJECT_CONTEXT.md
```

Example:

```
leafcutter/templates/agents/sql-coder.md   <- this directory (generic, flat)
.agents/agents/sql-coder/PROJECT_CONTEXT.md           <- project side (folder-shaped)
```

**Why the asymmetry?** Templates are shared across all projects and change infrequently.
Project context is per-project, changes independently, and is discovered at runtime — not
inlined at build time. The folder-shaped project side allows multiple companion files per
agent in the future (diagrams, test fixtures, etc.) without restructuring the template.

See [Convention: PROJECT_CONTEXT Injection](../../docs/conventions/PROJECT_CONTEXT-injection.md)
for the full rationale and rejected alternatives.

## The filename is `PROJECT_CONTEXT.md` (uppercase, canonical)

The companion filename is `PROJECT_CONTEXT.md` — uppercase, exactly as written. Lowercase
variants (`project_context.md`) are forbidden. This matches the canonical precedent established
for the skills surface (see `templates/skills/README.md`).

## How to discover whether a project has bound a context for an agent

Check for the presence of the companion file:

```bash
test -f .agents/agents/<agent-name>/PROJECT_CONTEXT.md && echo "context bound" || echo "template-only"
```

Or use the build pipeline helper:

```python
from portable_dev_workflow.scripts.build import find_project_contexts
contexts = find_project_contexts()  # returns [(agent_name, path), ...]
```

If the file is absent, the agent runs in template-only mode and emits a single debug line:

```
PROJECT_CONTEXT.md not found for <agent-name>; running template-only
```

## Adding a new agent template

1. Create `<agent-name>.md` following the frontmatter schema in `.claude/agents/README.md`.
2. Add a Pre-Flight step to the agent body:

   ```markdown
   ## Pre-Flight

   Read `.agents/agents/<agent-name>/PROJECT_CONTEXT.md` if it exists. Follow every pointer
   in that file before proceeding. If absent, log one debug line and continue with
   template-only behaviour.
   ```

3. Add an entry in `leafcutter/config/agent_registry.json`.
4. Run `python leafcutter/scripts/build.py` to materialise the template.
5. If the agent needs project-specific context, author
   `.agents/agents/<agent-name>/PROJECT_CONTEXT.md` following the how-to at
   `leafcutter/docs/how-to/inject-project-knowledge-into-agents.md`.

## Agent Index (Supervisor / Orchestration Tier)

Supervisor-tier agents that can be invoked by the user or by other supervisors.
The canonical full list is in `agent_registry.json` — this table covers agents
whose primary entry point is a user-facing slash command.

| Agent | Slash Command | Description | Template |
|-------|--------------|-------------|----------|
| `epic-supervisor` | `/build-feature <epic>` | Drives a whole epic ticket-by-ticket using the building-epics skill. | `epic-supervisor.md` |
| `create-ticket` | `/create-ticket` | Scaffolds a new ticket via business-analyst + refinement. | `create-ticket.md` |
| `create-epic` | `/create-epic` | Scaffolds a new epic with a Master_Plan and sub-tickets. | `create-epic.md` |
| `workflow-architect` | `/workflow-architect` | Meta-agent owning the leafcutter package surface. | `workflow-architect.md` |
## See Also

- [Convention: PROJECT_CONTEXT Injection](../../docs/conventions/PROJECT_CONTEXT-injection.md)
- [How-To: Inject project knowledge into agents](../../docs/how-to/inject-project-knowledge-into-agents.md)
- `.agents/agents/README.md` — project-side directory explainer
