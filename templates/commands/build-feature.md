---
description: |
  User-facing entry point to the build system. Resolves an epic name, an epic
  folder path, or a single standalone-ticket file path under tickets/, gets the
  workspace from the one workspace maker, then drives each ready ticket's phases through the flattened
  per-phase driver (each needed phase dispatched as its own depth-1 agent under
  its template) — for epics via a planner + parallel batch loop, for single
  tickets directly. No ticket-supervisor agent is dispatched for phase execution.
---

**This command requires the Workflow tool. If the Workflow tool is not available
in your environment, this command will not work — do not attempt to run it
manually as an LLM conversation.**

Invoke the `build-feature` workflow script via the Workflow tool:

```
Workflow("build-feature", { target: $ARGUMENTS })
```

**Workspace.** This command cannot know which epic or ticket `$ARGUMENTS` names
until the workflow resolves it, so it runs no workspace maker of its own. The
workflow makes its one dispatch to the one workspace maker once the work identity
is known. No step here asks an agent to create, copy, set up, link or repair a
workspace.

If the Workflow tool is unavailable or the script returns an error, stop
immediately and report the failure. Do NOT improvise an LLM-mediated
alternative. The correct response to a missing Workflow tool is:

> ERROR: /build-feature requires the Workflow tool (Claude Code ≥ 2.1.154).
> The Workflow tool is not available in this environment.
> This command cannot proceed. Check your Claude Code version and environment.
