---
title: "How to inject project knowledge into a portable agent"
type: how-to
status: active
created: 2026-05-15
last_updated: 2026-05-15
components:
  - infrastructure
related_docs:
  - docs/architecture/adrs/ADR-025-portable-agent-project-context-layout.md
  - leafcutter/docs/conventions/PROJECT_CONTEXT-injection.md
  - leafcutter/templates/agents/README.md
  - .agents/agents/README.md
---

# How to inject project knowledge into a portable agent

This guide walks you through adopting an existing portable agent (from
`leafcutter/templates/agents/`) for a specific project by authoring
a `PROJECT_CONTEXT.md` companion file. After following this procedure, the
agent will load your project's conventions, deploy commands, and relevant
documentation links at startup — without any changes to the portable template
itself.

**Prerequisites**

- The agent template exists in `leafcutter/templates/agents/<agent-name>.md`.
- The leafcutter package is installed in your project (`build.py` has run at least once).
- You know which project-specific conventions the agent needs (folder layout, deploy commands, relevant docs).

---

## Procedure

### Step 1 — Locate the template

Find the agent template you want to adopt:

```
leafcutter/templates/agents/<agent-name>.md
```

Read the template body to understand what project-specific knowledge the agent expects. Look for
placeholder phrases like "read your project's conventions" or "see PROJECT_CONTEXT.md". The
Pre-Flight section typically says:

> Read `.agents/agents/<agent-name>/PROJECT_CONTEXT.md` if it exists. If absent, log one debug
> line and continue with template-only behaviour.

This is the injection hook. Your `PROJECT_CONTEXT.md` file is what the agent will read here.

### Step 2 — Create the per-agent project folder

Create the folder for this agent's companion file under `.agents/agents/`:

```bash
mkdir -p .agents/agents/<agent-name>
```

Folders are created on first use; they are never pre-created empty. If the folder already exists,
skip this step.

### Step 3 — Author `PROJECT_CONTEXT.md`

Create `.agents/agents/<agent-name>/PROJECT_CONTEXT.md`. The filename is **uppercase and canonical** —
`PROJECT_CONTEXT.md` exactly. Lowercase variants (`project_context.md`) are forbidden.

The file is free-form Markdown. Use it to answer the questions the agent will have when it starts:

- Where does this type of code/file live in this project?
- What command deploys/reloads changes locally?
- What command runs the tests?
- Which READMEs and how-to docs should the agent read for context?
- Are there authorization requirements (e.g. "never deploy to production without explicit user approval")?

**Template:**

```markdown
# PROJECT_CONTEXT: <agent-name> (<project-name>)

## Where code lives
- <type>: `<folder-path>/`
- ...

## Key references
- [<doc title>](<relative path to doc>)
- [<how-to title>](<relative path to how-to>)

## Local deploy / test
- Deploy: `<command>`
- Test: `<command>`

## Authorization requirements
<Any authorization gates that must not be bypassed>
```

**Real-world example** (bybit-trader `sql-coder`):

```markdown
# PROJECT_CONTEXT: sql-coder (bybit-trader)

## Where SQL lives
- Procedures: `sql_functions/procedures/`
- Functions: `sql_functions/functions/`
- Views: `sql_functions/views/`
- Triggers: `sql_functions/triggers/`

## Key references
- [Database Domain](../../docs/database-domain.md)
- [How to deploy SQL locally](../../docs/how-to/deploy-sql-locally.md)
- [How to run SQL tests locally](../../docs/how-to/run-sql-tests-locally.md)
- [How to deploy SQL to production](../../docs/how-to/deploy-sql-to-production.md)

## Local deploy
`poetry run python -c "from database_manager import DatabaseManager; DatabaseManager().create_procedures()"`

## Authorization requirement
Never deploy SQL to `brain.vierhenze.de` without explicit user authorization in this session.
```

### Step 4 — Verify discovery via the agent's Pre-Flight read

The agent discovers your `PROJECT_CONTEXT.md` at runtime — no rebuild is required. To verify:

1. Invoke the agent on a simple task.
2. The agent's first action should be to read `.agents/agents/<agent-name>/PROJECT_CONTEXT.md`.
3. If the file is found, the agent will follow the pointers inside (READMEs, how-tos) before
   starting work.
4. If the file is NOT found (e.g. wrong filename case), the agent emits exactly one debug line:

   ```
   PROJECT_CONTEXT.md not found for <agent-name>; running template-only
   ```

   If you see this log after creating the file, double-check the filename is `PROJECT_CONTEXT.md`
   (uppercase) and the folder name exactly matches the agent's ID (kebab-case).

### Step 5 — Confirm agent behavior matches project conventions

Run a trivial task with the agent and verify:

- The agent reads the references you provided (opens the linked READMEs/how-tos as Pre-Flight).
- The agent uses the correct folder paths from your `PROJECT_CONTEXT.md` (not hardcoded paths from the template).
- The agent applies your authorization requirements (e.g. asks before deploying).

If the agent ignores the pointers, check that the Pre-Flight section of the compiled
`.claude/agents/<agent-name>.md` includes the PROJECT_CONTEXT load instruction. If it doesn't,
the template may not have been updated yet to support the injection pattern — check the template
version and consider filing a ticket to add the Pre-Flight step.

---

## Sample `PROJECT_CONTEXT.md` content

Below is the pattern used by the bybit-trader project for its SQL agents.
Use this as your reference model when authoring context files for other agents.

```markdown
# PROJECT_CONTEXT: <agent-name> (<your-project>)

## Project layout
<List the key folders the agent will write to or read from, with relative paths>

## Deploy commands
<List the exact commands to deploy changes locally, with language tags>

## Test commands
<List the exact commands to run the tests for this agent's domain>

## Key documentation
- [<doc name>](<relative path>) — <one-line description of what it covers>
- [<how-to name>](<relative path>) — <one-line description>

## Authorization requirements (if any)
<Any hard gates — e.g. "always ask user before deploying to production">
```

---

## See Also

- [ADR-025: Portable Agent PROJECT_CONTEXT Layout](../../docs/architecture/adrs/ADR-025-portable-agent-project-context-layout.md) — architectural rationale and rejected alternatives
- [Convention: PROJECT_CONTEXT Injection](../conventions/PROJECT_CONTEXT-injection.md) — canonical convention reference
- `leafcutter/templates/agents/README.md` — template directory, asymmetry explainer
- `.agents/agents/README.md` — project-side directory explainer
- `leafcutter/scripts/project_context_discovery.py` — `find_project_contexts()` helper used by build.py
