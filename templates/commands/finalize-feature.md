---
description: |
  Post-merge feature finalization: capture pre-merge test baseline on main,
  open PR if missing, merge origin/main into worktree, run post-merge tests
  (with triage baseline), merge PR to main only when tests pass, sync local
  main, close tickets/archive epic, remove worktree. Prompt gates on all
  destructive steps. HALT on test regression before PR merge.
---

**This command requires the Workflow tool. If the Workflow tool is not available
in your environment, this command will not work — do not attempt to run it
manually as an LLM conversation.**

Invoke the `finalize-feature` workflow script via the Workflow tool:

```
Workflow("finalize-feature", { branch: $ARGUMENTS })
```

If the Workflow tool is unavailable or the script returns an error, stop
immediately and report the failure. Do NOT improvise an LLM-mediated
alternative. The correct response to a missing Workflow tool is:

> ERROR: /finalize-feature requires the Workflow tool (Claude Code ≥ 2.1.154).
> The Workflow tool is not available in this environment.
> This command cannot proceed. Check your Claude Code version and environment.
