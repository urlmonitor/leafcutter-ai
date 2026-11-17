---
description: |
  User-facing entry point to the build system. Resolves an epic name, an epic
  folder path, or a single standalone-ticket file path under tickets/, gets
  the workspace from the workspace maker (scripts/worktree.py, docs/how-to/get-a-workspace.md), then drives each ready ticket's phases through the flattened
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

This entry cannot know the work identity before the workflow resolves the epic
or ticket from `$ARGUMENTS`, so it makes no workspace itself and passes no
`workspace` argument. The workflow runs the one workspace maker (`scripts/worktree.py`, see `docs/how-to/get-a-workspace.md`) once, with the
identity it resolved, and consumes the maker's answer unchanged. Do not create,
copy, set up or repair a workspace here by hand; if the workflow reports that
the workspace could not be made, stop and report that answer verbatim.

If the Workflow tool is unavailable or the script returns an error, stop
immediately and report the failure. Do NOT improvise an LLM-mediated
alternative. The correct response to a missing Workflow tool is:

> ERROR: /build-feature requires the Workflow tool (Claude Code ≥ 2.1.154).
> The Workflow tool is not available in this environment.
> This command cannot proceed. Check your Claude Code version and environment.
