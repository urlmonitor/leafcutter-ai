---
description: |
  User-facing entry point to the supervisor system. Resolves an epic name,
  an epic folder path, or a single standalone-ticket file path under tickets/,
  then dispatches ticket-supervisor directly (for epics) or the
  build-single-ticket sub-skill (for standalone tickets) to drive it to
  completion.
---

**This command requires the Workflow tool. If the Workflow tool is not available
in your environment, this command will not work — do not attempt to run it
manually as an LLM conversation.**

Invoke the `build-feature` workflow script via the Workflow tool:

```
Workflow("scripts/workflows/build-feature.js", { target: $ARGUMENTS })
```

If the Workflow tool is unavailable or the script returns an error, stop
immediately and report the failure. Do NOT improvise an LLM-mediated
alternative. The correct response to a missing Workflow tool is:

> ERROR: /build-feature requires the Workflow tool (Claude Code ≥ 2.1.154).
> The Workflow tool is not available in this environment.
> This command cannot proceed. Check your Claude Code version and environment.
