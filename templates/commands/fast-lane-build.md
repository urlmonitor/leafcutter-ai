---
description: |
  Point the fast lane at ANY one acceptance-criterion id and get a PR back —
  no other input. Opens a fresh isolated worktree off the latest origin/main,
  resolves that AC's connected build set (its subtree plus any unmet dependency
  prerequisites, in dependency order, readiness-agnostic), builds the set through
  the lean two-agent test-writer → coder loop gated by verify_red_baseline and
  verify_green_and_coverage, then auto-commits and opens the pull request.
  A thin shim over the fast-lane-ship workflow, mirroring build-feature.
---

**This command requires the Workflow tool. If the Workflow tool is not available
in your environment, this command will not work — do not attempt to run it
manually as an LLM conversation.**

Invoke the `fast-lane-ship` workflow script via the Workflow tool, passing the
single AC-id argument:

```
Workflow("fast-lane-ship", { ac: $ARGUMENTS })
```

`$ARGUMENTS` is one acceptance-criterion id (e.g. `BO-2400f`). That one argument
is the only required input: pointing at the AC is the go-ahead, so a not-yet-approved
AC is still built. The workflow is auto-discovered by `build.py` (it globs
`templates/workflows-js/*.js`), so no manual registry entry is required.

If the Workflow tool is unavailable or the script returns an error, stop
immediately and report the failure. Do NOT improvise an LLM-mediated
alternative. The correct response to a missing Workflow tool is:

> ERROR: /fast-lane-build requires the Workflow tool (Claude Code ≥ 2.1.154).
> The Workflow tool is not available in this environment.
> This command cannot proceed. Check your Claude Code version and environment.
