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
- **Occurrences:** 3
- **First seen:** 2026-08-19 · **Last seen:** 2026-09-16
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
- **Do not gate startup on a live agent dispatch to read a static local file.**
  Routing it through a `status-checker` adds a round-trip whose failure modes are all
  false halts. **CORRECTION, 2026-09-16 — the sentence that stood here was wrong.** It
  read "the workflow runtime can read it directly". It cannot:
  `docs/reference/workflow-authoring-contract.md` §1 enumerates the globals the E2
  engine injects into a workflow body (`agent`, `parallel`, `pipeline`, `phase`, `log`,
  `args`, `workflow`, `budget`) and there is **no filesystem and no subprocess
  primitive**. `KI-BO-20260901-1620` records the same constraint independently. The
  correction matters because `ACD-2100b-5` (readiness `approved`, unbuilt) is written
  against that false premise: its Given is "an environment in which no agent can be
  dispatched" and its Then requires the check to complete anyway, which no
  implementation can satisfy today. The user chose a **chartered executor** on
  2026-09-16 — an agent whose whole charter is to run one exact command and return its
  output verbatim, exercising no judgement — over an engine-level primitive, which is
  upstream in Claude Code and not this project's to add. See `BO-3200f`.

**THIRD CAUSE, ADDED 2026-09-16 — A CHARTER REFUSAL, NOT AN I/O FAILURE.** The two
causes recorded above (worktree path-absence, and a transient API error) are both
genuine and neither was what happened in the two reproductions of 2026-09-16
(`wf_6e6de02b-3f9`, `wf_82e1655d-e68`). Both halted at
`resolve-workspace-setup-permission` before any authoring agent was dispatched, with
zero ACs produced, reporting that the registry could not be **read**. The file was
present and readable at *both* candidate locations — 131 KB, at
`leafcutter-ai/.leafcutter/config/` and `leafcutter-ai/config/`, verified by direct
`ls`. What actually failed is that the step reads the registry by dispatching
`status-checker` to `cat` it, and `status-checker` declares `permits_shell: false` and
refuses arbitrary file reads by charter. It refused both times:

```
run 1: {"status":"failed","payload":{"blocker_summary":"out-of-scope-request: arbitrary cat command with no ticket context"}}
run 2: {"output":"","exit_code":1,"error":"out-of-scope: status-checker only executes commands within the ticket-investigation protocol... I will not run arbitrary file-read commands outside that scope."}
```

The circularity is the point: **the workflow cannot read the registry to determine
whether shell is permitted, because doing so requires a shell dispatch to an agent that
is not permitted shell.** The permission check is the step that fails.

Note run 2 in particular — the refusing agent fabricated `exit_code: 1` *inside* its
refusal payload, so the workflow reported "exit code 1, no stdout", which is
indistinguishable from a genuinely unreadable file and sends the operator to inspect a
path that is fine. The first fix direction below ("distinguish the four outcomes") has
**partially landed** — the halt now correctly says "This is a lookup failure, not a
permissions verdict" — but it still cannot tell a **refusal** from an **I/O error**,
and a refusal is a *fifth* outcome that the four-outcome enumeration never contained.

**SCALE.** `plan-feature.js` dispatches roughly **20** shell steps to `status-checker`
(git status, git log, `cat`, file deletes, git restore, telemetry appends, script runs).
Exactly **1 of 60** registered agents declares `permits_shell: true`, and it is
`worktree-agent`.

**AC coverage as of 2026-09-16.** `BO-3200f` (chartered executor — removes the need to
ask a specialist for a mechanical errand at all), `BO-3200g` (a refusal is reported as a
refusal, not as a damaged file), `AR-200c` (every agent states its limits). `ACD-2100b`
amended to require the fifth outcome on this startup path. The path fix
(`ACD-2100a-3`) and the round-trip removal (`ACD-2100b-5`) were already approved and
unbuilt before this reproduction, in
`tickets/00_inbox/epics/EPIC-StartingNewWorkTheProperWayAlways/`.

**Why it matters beyond the message.** `/plan-feature` is the mandated entry point for
all new work (`CLAUDE.md`, "New Work Goes Through ACs"). While this holds, that path is
closed from any worktree, and the only way to author ACs is to dispatch the PO/BA/IT-PO
agents by hand — which skips the triage, the gates, and the staged-commit invariant the
workflow exists to enforce.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8, inverted — not a check
reporting success it did not establish, but a check reporting a *specific failure cause*
it did not establish.

---
