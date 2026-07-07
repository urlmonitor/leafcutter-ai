---
description: |
  Triage, orchestrate, and gate AC authoring for a new feature request.
  Dispatches ac-triage (Haiku) to classify the request as strategic /
  behavioral / technical / covered, then routes through the correct
  authoring agents (PO v3, BA v3, IT PO v3) with user confirmation gates
  between stages. All output goes exclusively to the AC store — no ticket
  files are produced. Use when you want to plan a new feature end-to-end,
  from strategic goal down to implementable technical constraints.
---

**This command requires the Workflow tool. If the Workflow tool is not available
in your environment, this command will not work — do not attempt to run it
manually as an LLM conversation.**

Invoke the `plan-feature` workflow script via the Workflow tool:

```
Workflow("scripts/workflows/plan-feature.js", { userInput: $ARGUMENTS })
```

If the Workflow tool is unavailable or the script returns an error, stop
immediately and report the failure. Do NOT improvise an LLM-mediated
alternative. The correct response to a missing Workflow tool is:

> ERROR: /plan-feature requires the Workflow tool (Claude Code ≥ 2.1.154).
> The Workflow tool is not available in this environment.
> This command cannot proceed. Check your Claude Code version and environment.

All AC YAML files are written exclusively to `docs/acceptance-criteria/`.
No ticket files are created by this command.
