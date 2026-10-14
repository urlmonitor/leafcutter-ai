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

Run these steps in order. Each Bash call is one simple command.

**Step 1 — Permission pre-flight.** Run the pre-flight and keep its stdout JSON
object (see `.claude/skills/plan-feature/SKILL.md` §WSP):

```bash
python3 <project-root>/scripts/worktree/check_workspace_setup_permission.py --agent-id worktree-agent
```

**Step 2 — Get the workspace.** Run the one workspace maker. `<slug>` is a short
kebab-case name for the request, and `<project-root>` is the absolute path of the
main checkout:

```bash
python3 <project-root>/.leafcutter/scripts/worktree.py ensure --kind ac --slug <slug> --repo-root <project-root>
```

On a non-zero exit, stop and report stdout and stderr word for word. Do not call
the workflow.

**Step 3 — Invoke the workflow** via the Workflow tool, passing the pre-flight's
answer and the maker's answer on word for word:

```
Workflow("plan-feature", { userInput: $ARGUMENTS, workspace_setup_permission: <step 1 answer>, workspace: <step 2 answer> })
```

If the Workflow tool is unavailable or the script returns an error, stop
immediately and report the failure. Do NOT improvise an LLM-mediated
alternative. The correct response to a missing Workflow tool is:

> ERROR: /plan-feature requires the Workflow tool (Claude Code ≥ 2.1.154).
> The Workflow tool is not available in this environment.
> This command cannot proceed. Check your Claude Code version and environment.

All AC YAML files are written exclusively to `docs/acceptance-criteria/`.
No ticket files are created by this command.
