---
title: "KI-ACD-20260928 — every pause-store write in /plan-feature is dispatched to worktree-agent, which refuses it, so no interactive run can ever pass a gate"
description: "plan-feature.js hardcodes worktree-agent as its shell-permitted agent for all six pause-store operations. worktree-agent's charter is create/remove worktrees, so it declines the write; the record is never persisted, verify correctly reports it absent, and the run halts pause_persist_failed at the first gate. /plan-feature is the mandated entry point for all new work and cannot currently complete an interactive run."
type: reference
category: reference
status: active
created: 2026-09-28
last_updated: 2026-09-28
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/architecture/adrs/ADR-024-interactive-pause-resume.md
---

# KI-ACD-20260928 — every pause-store write in /plan-feature is dispatched to worktree-agent, which refuses it, so no interactive run can ever pass a gate

> One known issue in the ac-driven-dev register.
> Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`blocker`); the original
> grading is the `**Severity:**` line below.

- **Severity:** blocker. `/plan-feature` is the mandated entry point for ALL new work
  (`CLAUDE.md`, "New Work Goes Through ACs"), and it cannot complete an interactive run.
  Every gate needs a durable pause record; the write that creates it is refused, so the
  run halts at the first gate every time. There is no fallback path.
- **Status:** open — no AC.
- **Occurrences:** 2 (runs `wf_51a32979-97e` and its resume, both 2026-09-28). Also the
  likeliest cause of the `pause_persist_failed` recorded as Occurrence 2 of
  `KI-BO-20260901-1620` on 2026-09-25, which was attributed to refused dispatches.
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-28
- **Where:** `templates/workflows-js/plan-feature.js` — `const _shellPermittedAgentId =
  "worktree-agent"` at lines 1599, 1647 and 1831, feeding six
  `agent(..., { agentType: _shellPermittedAgentId })` dispatches: `peek-pause-record`,
  `read-pause-record`, `clear-pause-record`, `clear-pause-record-verify`,
  `pause-persist`, `pause-persist-verify`.

**Symptom.** An interactive `/plan-feature` run reaches its first user gate and ends:

```
{"status":"pause_persist_failed","gate_id":"gate-ba",
 "message":"Gate 'gate-ba' needed a human answer, but the pause record for run
 'default-run' could not be verified as written, so this run CANNOT be resumed."}
```

**Mechanism — every component behaved correctly; the routing is wrong.** The pause-store
write is dispatched to `worktree-agent`, whose charter is two actions. It declined, in its
own words, recorded verbatim in the run journal:

> "I'm the worktree lifecycle agent, scoped to two actions: **create** and **remove**"

The record was therefore never written. `pause-persist-verify` then returned
`{"exists": false, "stale": false, "record": null}` — a correct report. The workflow
halted fail-closed — correct behaviour. Nothing malfunctioned: an agent was asked to do
something outside its charter and said so, and the guard that exists to catch exactly
that did catch it. The defect is the choice of agent.

**Why this agent was chosen, and why that reasoning is wrong.** `worktree-agent` is one of
only two agents in `config/agent_registry.json` declaring `permits_shell: true`, so it was
selected as "the agent allowed to run shell". But `permits_shell` answers *may this agent
run a command at all*, not *is this command within its role*. This is precisely the defect
`KI-BO-20260901-1620` names — "`permits_shell` is read as two states, and no check compares
a workflow's dispatches against it" — recorded there against `fast-lane-ship.js`. It is
also present here, and here it is fatal rather than latent.

**Second-order: the same defect is SILENT on the read path.** `peek-pause-record` is
dispatched the same way and refused the same way, but a refusal there is parsed as "no
paused record exists" — indistinguishable from the legitimate no-record case. So the run
sails past peek and only fails at persist. One defect, failing open on one path and closed
on another; only the closed one is visible. Any fix must close the read path too, or the
next occurrence is silent again.

**Evidence.** Run `wf_51a32979-97e`, 2026-09-28, resumed after an unrelated API outage:
**10 agents, 0 errors**, same `pause_persist_failed`. The outage is ruled out — the first
attempt had 3 SSL failures, the resume had none and failed identically. Journal:
`subagents/workflows/wf_51a32979-97e/journal.jsonl`, agent `accc4fc0d12af3cc3`
(label `pause-persist`) carries the refusal text; `abb030dcc8cc75d5b`
(`pause-persist-verify`) carries the `exists: false` verdict. Both pause stores on disk
(`leafcutter-ai/.leafcutter/paused_runs/` and the workspace parent's) contain only an
unrelated July record — the write reached neither, so this is not the two-install split of
`KI-ACD-20260927`.

**Fix direction.** Dispatch the pause-store operations to an agent whose charter is running
a given command, not to whichever agent happens to hold `permits_shell`. The package now
ships one built for this: `command-step-runner` (`BO-2400a-1-i`) — `permits_shell: true`,
`model: haiku`, and a charter that is explicitly "runs exactly one given command, once, in
one named workspace, and hands back that command's exit status, stdout and stderr
untouched", holding "no judgement about whether a command is wise". Three things follow:

- Its prompts must name the target workspace; it declines a request that names none.
- `command-step-runner`'s `spawned_by` is `["user"]` and would need `plan-feature.js`.
  Note `KI-AR-002`: `registry_validator.py`'s `_EXTERNAL_CALLERS` is `{"user",
  "finalize-feature.js"}` and excludes `plan-feature.js`, so the spawn-symmetry check will
  not validate that edge either way — do not read its silence as approval.
- Moving the write to a chartered runner does NOT fix the read path's fail-open parse. That
  needs its own change: a refusal must be reported as "could not determine", never as
  "no record".

Do **not** fix this by routing to `status-checker`. It declares `permits_shell: false` —
the pre-flight returns `permission_denied` for it — while ~37 other dispatches in this same
workflow already send it shell commands. That inconsistency is real and worth its own
entry, but widening it is not a fix.

**Pattern:** an authorisation flag read as a capability. "Allowed to run commands" was
taken to mean "allowed to run THIS command", and the agent's own charter — the thing that
actually decides — was never consulted.
