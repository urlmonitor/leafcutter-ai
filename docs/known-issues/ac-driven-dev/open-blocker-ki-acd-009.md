---
title: "KI-ACD-009 — `/plan-feature` halts before any authoring agent and blames a registry field that is correct"
description: "KI-ACD-009 — `/plan-feature` halts before any authoring agent and blames a registry field that is correct"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-009 — `/plan-feature` halts before any authoring agent and blames a registry field that is correct

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `templates/workflows-js/plan-feature.js:1745-1790` — the `resolve-workspace-setup-permission` step and the `permitsShell` fail-closed branch

**Symptom.** Every run halts with:

> Workspace-setup step 'worktree-setup' is configured to dispatch to agent
> 'worktree-agent', whose registered charter does not permit running repository/shell
> commands. … Fix the workspace_setup_agent configuration or
> `config/agent_registry.json`'s `permits_shell` field for that agent.

**The message is false.** `worktree-agent` has `permits_shell: true`
(`config/agent_registry.json:1368`). Following the remedy leads an operator to a field
that is already correct, and there is nothing there to fix.

**Root cause — a lookup failure rendered as a permissions verdict.** The step reads the
registry by dispatching a `status-checker` agent to `cat` it, then:

```js
const match = entries.find((e) => e && e.id === workspaceSetupAgentId);
permitsShell = !!(match && match.permits_shell === true);
```

`permitsShell` is `false` for *four different reasons* — agent dispatch failed, output
unparseable, file unreadable, or the id genuinely absent — and only the last is a
permissions problem. All four print the permissions message. Failing closed is right;
asserting a specific false cause is not.

**Two independent causes were both present in the observed run**, which is why this is a
blocker rather than a flake:

1. **The path does not exist.** The deployed workflow reads
   `.leafcutter/config/agent_registry.json` (relative). Verified 2026-08-19: that file
   exists at the **workspace root** (`<workspace>/.leafcutter/config/`) but **not** in a
   worktree's `.leafcutter/`. So the `cat` fails for any run whose cwd is a worktree —
   deterministically, not intermittently. Same self-hosting-layout class as KI-ACD-004,
   different resolution site.
2. **The dispatch itself errored.** The run recorded
   `[resolve-workspace-setup-permission] failed: API Error: Connection lost
   mid-response`, so `permissionResult` was `null` and the parse could not have
   succeeded regardless.

Either alone produces the halt. Because a transient API error is indistinguishable in
the output from a real mis-assignment, a reader cannot tell a retryable failure from a
configuration one.

**Evidence.** Run `wf_359683cc-51a`, 2026-08-19, from
`worktrees/safety-security`. 3 agents dispatched, 2 completed, 1 errored; halted before
triage and before any authoring agent, so zero ACs were produced.

```
$ ls <worktree>/.leafcutter/config/agent_registry.json
ls: cannot access ...: No such file or directory
$ find <workspace> -name agent_registry.json -not -path '*/worktrees/*'
<workspace>/leafcutter-ai/config/agent_registry.json
<workspace>/.leafcutter/config/agent_registry.json
```

**Fix direction.** Three separable changes:

- **Distinguish the four outcomes.** Report `could not read the registry at <path>`,
  `could not parse it`, `agent <id> not found in it`, and `agent <id> has
  permits_shell: false` as different messages. Keep failing closed — the objection is to
  the diagnosis, not the caution. This is the same "green means checked" distinction
  `GE-120` draws, inverted: a check that could not run must not report a specific verdict
  about what it did not see.
- **Resolve the registry path, do not hardcode a relative one.** Use the same root
  resolution the guardian hooks use, so the read works from a worktree as well as the
  workspace root.
- **Do not gate startup on a live agent dispatch to read a static local file.** The
  workflow runtime can read it directly; routing it through a `status-checker` adds an
  API round-trip whose failure mode is a false halt.

**Why it matters beyond the message.** `/plan-feature` is the mandated entry point for
all new work (`CLAUDE.md`, "New Work Goes Through ACs"). While this holds, that path is
closed from any worktree, and the only way to author ACs is to dispatch the PO/BA/IT-PO
agents by hand — which skips the triage, the gates, and the staged-commit invariant the
workflow exists to enforce.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8, inverted — not a check
reporting success it did not establish, but a check reporting a *specific failure cause*
it did not establish.

---
