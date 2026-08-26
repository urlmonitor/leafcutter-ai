---
title: "Known issues — supervisor-system"
description: "Open, observed defects in the supervisor-system component: ticket-supervisor, the phase-agent dispatch chain, and the conventions agents follow when spawning sub-agents. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - supervisor_system
related_docs:
  - docs/architecture/components/supervisor-spawn-topology.md
  - docs/architecture/agent_delivery_workflows.md
---

# Known issues — supervisor-system

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-SS-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-SS-001 — An agent that backgrounds a sub-agent then waits for it parks forever, and the stall cascades down the chain

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 2 (same drive, two levels of the chain)
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `ticket-supervisor` and `architect-review` dispatch behaviour; the sub-agent spawn convention generally

**Symptom.** An agent that dispatches a child and then yields to wait for its completion
terminates having done nothing, and — because it exited without an error — reports no
failure. The parent sees a completed child and a clean status.

It cascades: each level does the same thing to the level below, so a single drive can strand
a whole chain.

**Mechanism — corrected 2026-08-25.** This entry originally described the cause as "the
completion notification is delivered to the top-level session, not to the agent that
spawned it." That is a true observation about where notifications land, but naming it as
*the* mechanism points the fix upstream at the harness and mis-states what actually
happens. The real mechanism is one level more basic:

> **A subagent has no idle state.** In the main session, emitting text with no tool call
> ends the *turn*, and the session survives to be notified later. In a subagent, emitting
> text with no tool call ends the *agent* — that text **is** the result returned to the
> parent.

So "I'll wait for the completion notification" is not a failed await. It is the agent
typing its own exit. Re-routing notifications would not have saved either observed stall,
because in both cases the waiting agent was already gone.

There is also no wait primitive a subagent could use instead: the harness strips
`TaskOutput`, `ScheduleWakeup`, `Workflow` and `AskUserQuestion` from every subagent, and
nothing else blocks until a background task completes. Subagents are designed not to park.
The durable invariant is therefore not "don't background a child" but:

> **A subagent must never depend on the result of anything it spawns.** If it needs the
> result, it must not delegate — it must do the work itself, or not be the one
> orchestrating.

That statement survives fork-mode changes, depth-limit changes, and notification routing
changes, because it references none of them.

**Evidence.** Driving `TICKET-20260817-BO-1500f-1` on 2026-08-18. `ticket-supervisor`
dispatched `architect-review` in the background and returned:

> "Waiting for the `architect-review` phase agent to complete before proceeding to the next
> step. I will not poll further — I'll act on the completion notification when it arrives."

State verified independently at that point: no commits, no test file, no edits to
`plan-feature.js`. The only change on disk was the ticket's `status: in_progress`. The drive
had produced nothing and said nothing was wrong.

Re-dispatched with an explicit instruction to run every phase synchronously. The stall then
reappeared one level down, in `architect-review`, which named the cause itself:

> "SendMessage isn't available in this session, so I'll simply wait for the background
> research-agent to finish — I'll be notified automatically when it completes."

The `research-agent` at the bottom of the chain ran fine and returned a thorough result. Only
the waiting was broken. Both stalled agents had `run_in_background` semantics available and
no way to consume the resulting notification.

**Why it is a blocker rather than an annoyance.** The failure is silent and shaped exactly
like success. An agent that stalls exits cleanly, so a supervisor reading only the child's
status concludes the phase completed. That is the phantom-done shape this repo exists to
prevent, relocated from the artifact layer to the orchestration layer — and it is invisible
to every gate, because no gate runs. This session caught it only by checking `git status` and
`git log` against the agent's own report, which is the same discipline
`CLAUDE.md` → "Real-artifact behavioral spot-check" prescribes for build output.

**Workaround, and its expiry.** Dispatch every phase agent synchronously
(`run_in_background: false`) so the result returns inside the dispatching agent's own turn.
This fixes the level you control and not the level below it. Treat any phase agent's
"waiting for…" as a completed-with-nothing result and verify against the repository, never
against the payload.

Do not rely on this for long. Claude Code's interactive **fork mode** runs spawned
subagents in the background by default and removes the `Agent` tool's
`run_in_background` parameter altogether, so the knob this workaround stands on disappears
— silently, with no error. Reported to become the interactive default at **v2.1.232**;
this workspace was on **2.1.231** when that was checked on 2026-08-25, i.e. one release
away. The version threshold is second-hand and unverified here; the direction of travel is
not. `CLAUDE_CODE_FORK_SUBAGENT=0` disables fork mode as a dated stopgap.

**The prompt-level fix has already been tried, and rotted.** Before proposing it again,
note that it exists: `building-epics/SKILL.md` §2.1-R1 "Synchronous phase dispatch
(MANDATORY)" — "the supervisor's turn MUST NOT end while a phase agent is still running" —
was authored from the *EPIC-WorktreeQualityGateGuard* retrospective (KI-1, 2026-07-06)
whose war story is this same failure. `ticket-supervisor.md` separately specifies a
repo-verified disk-diff guard ("returned ok but no bytes changed → do NOT spawn the next
phase agent"). Both are correct, both were in force on 2026-08-18, and neither fired.
Neither could reach the second-level stall either: `building-epics` is loaded by
`ticket-supervisor` only, and `architect-review` — where the stall recurred — never loads
it. Two prompt rules, invisible to every gate, bypassed. Prompt discipline is not a fix
for this; only mechanical enforcement is.

**Fix direction.** Route all fan-out into the depth-0 JS workflow runtime, where
`await agent()` is a real await and there is no `run_in_background` option, so the failure
is structurally unrepresentable. Enforce "an agent may not spawn" mechanically in
`scripts/registry_validator.py` (build-time) rather than in prose. Add a fail-closed
runtime detector — a `SubagentStop` hook can veto an agent's exit (exit 2 prevents the
subagent from stopping), turning "parked and returned prose" from an undetectable success
into a forced retry.

Note the discarded candidate: "route child-completion notifications to the spawning agent"
was previously recorded here as the real fix. Per the corrected mechanism above it would
not have helped, and it is not available to us in any case.

**Partially remediated 2026-08-25.** The workflow runtime no longer treats a missing or
unrecognised agent result as success — see the fail-closed changes to `build-epic.js`,
`build-feature.js`, `build-ticket.js` and `plan-feature.js`, and the new `undetermined`
status. That narrows the blast radius (a parked agent can no longer be counted as a
completed phase or a completed epic) but does not close this issue: nothing yet stops an
agent from parking in the first place, and the registry/hook enforcement above is not
built.
