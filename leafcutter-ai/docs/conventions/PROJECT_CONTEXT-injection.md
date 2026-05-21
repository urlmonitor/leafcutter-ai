---
title: "Convention: PROJECT_CONTEXT Injection for Portable Agents"
type: convention
status: active
created: 2026-05-15
last_updated: 2026-05-15
components:
  - infrastructure
related_docs:
  - docs/architecture/adrs/ADR-025-portable-agent-project-context-layout.md
  - leafcutter/templates/agents/README.md
  - .agents/agents/README.md
---

# Convention: PROJECT_CONTEXT Injection for Portable Agents

> Cross-reference: [ADR-025](../../docs/architecture/adrs/ADR-025-portable-agent-project-context-layout.md)
> captures the full rationale and rejected alternatives for all decisions documented here.
> This convention file is the operational reference; ADR-025 is the architectural record.

Portable agents in `leafcutter/templates/agents/` are project-agnostic by design.
They contain no hardcoded project paths, deploy commands, or domain knowledge. Project-specific
context is supplied at runtime via a `PROJECT_CONTEXT.md` companion file that each agent reads
at startup. This document pins the five locked decisions that govern this pattern.

## Layout

**Option C layout** (locked, per ADR-025 §Decision 1): templates are flat single files;
project context is folder-shaped on the project side.

```
leafcutter/
  templates/
    agents/
      sql-coder.md                    <- generic template (flat single file)
      sql-query.md
      sql-test-writer.md
      ...

<project-root>/
  .agents/
    agents/
      sql-coder/
        PROJECT_CONTEXT.md            <- project-specific companion (per-agent folder)
      sql-query/
        PROJECT_CONTEXT.md
      sql-test-writer/
        PROJECT_CONTEXT.md
      ...
```

Key properties:
- Templates stay single flat files — no structural change to the ~30 existing templates.
- Project-side context lives under `.agents/agents/<agent-name>/` (a dedicated folder per agent).
- Folders are created on first use; never pre-created empty.
- Option A (templates also become folders) is the deferred convergence target and is mechanically
  scriptable from Option C when multi-artifact-per-agent becomes the norm. See ADR-025.
- Option B (lowercase `project_context.md` in a flat companion folder) is **explicitly ruled out**
  and must not be re-proposed. See ADR-025.

## Filename

The canonical filename is `PROJECT_CONTEXT.md` — uppercase, exactly as written.

- Lowercase variants (`project_context.md`) are **forbidden** in any path created under this convention.
- The uppercase canonical form matches the precedent established in
  `leafcutter/templates/skills/README.md` for the skills surface.
- Any existing lowercase reference is a stale artifact from before ADR-025 was locked and
  must be rewritten when encountered.

## Discovery

Discovery is **runtime, agent-side** (locked, per ADR-025 §Decision 3).

Each agent reads its own `.agents/agents/<name>/PROJECT_CONTEXT.md` at startup as a Pre-Flight step.
The typical Pre-Flight instruction in an agent template reads:

> **Pre-Flight Step: Load PROJECT_CONTEXT**
> Read `.agents/agents/<agent-name>/PROJECT_CONTEXT.md` if it exists. Follow every pointer
> in that file (READMEs, how-tos, conventions) before proceeding. If the file is absent,
> log one debug line and continue with template-only behaviour (see "Missing-context fallback").

The build pipeline (`leafcutter/scripts/build.py`) does **NOT** inline
`PROJECT_CONTEXT.md` content into the compiled `.claude/agents/<name>.md` body. Rationale:
- `PROJECT_CONTEXT.md` changes are hot-reloadable without a full rebuild.
- The compiled agent body remains small, reviewable, and stable.
- Build-time inlining would couple the project's context churn to the template release cycle.

`build.py` exposes `find_project_contexts()` and `get_project_context_metadata()` (see
`leafcutter/scripts/build.py`) for reporting and validation purposes. These helpers
walk `.agents/agents/` and return presence information only — they never alter the compiled output.

## Missing-Context Fallback

When an agent's `PROJECT_CONTEXT.md` is absent (locked, per ADR-025 §Decision 4):

1. The agent **silently skips** the project-context load step.
2. The agent writes **exactly one line** to the debug log:

   ```
   PROJECT_CONTEXT.md not found for <agent-name>; running template-only
   ```

3. The agent **continues** with template-only behaviour — all generic capabilities remain active.

This makes portable agents work in projects that have NOT yet authored a `PROJECT_CONTEXT.md`
file for that agent. The missing-context case is treated as the "new project bootstrap" path,
not an error condition.

The `get_project_context_metadata()` helper in `build.py` emits this debug log to stderr during
compilation reporting (reporting only — it does not affect the compiled agent body).

## Registry Contract

The registry contract is **implicit by file presence** (locked, per ADR-025 §Decision 5).

`leafcutter/config/agent_registry.json` does **NOT** gain a new
`expects_project_context` field. The build pipeline and runtime agents probe for
`.agents/agents/<name>/PROJECT_CONTEXT.md` directly using filesystem existence checks.

Adding the `PROJECT_CONTEXT.md` file is the only signal needed to bind a project context to an
agent. Removing the file reverts the agent to template-only behaviour without any registry change.

## Asymmetry

Because the template side stays flat (single files) while the project side is folder-shaped, both
directories carry an explicit explainer:

- `leafcutter/templates/agents/README.md` — "Templates are flat single files. The
  project-side companion lives at `.agents/agents/<name>/PROJECT_CONTEXT.md` (folder-shaped).
  See ADR-025 for rationale."
- `.agents/agents/README.md` — same explainer from the project-side perspective, plus a pointer
  to `leafcutter/templates/agents/` and ADR-025.

Both README files are maintained by ticket 01 and ticket 02 of EPIC-PortableSQLAgents. See those
tickets for the detailed authoring tasks.

## See Also

- [ADR-025: Portable Agent PROJECT_CONTEXT Layout](../../docs/architecture/adrs/ADR-025-portable-agent-project-context-layout.md) — full rationale and rejected alternatives
- [How-To: Inject project knowledge into agents](../how-to/inject-project-knowledge-into-agents.md) — step-by-step adoption guide
- `leafcutter/templates/agents/README.md` — template directory explainer
- `.agents/agents/README.md` — project-side directory explainer
- `leafcutter/scripts/build.py` — `find_project_contexts()` and `get_project_context_metadata()` helpers
