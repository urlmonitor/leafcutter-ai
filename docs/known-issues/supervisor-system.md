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

**Symptom.** A sub-agent's completion notification is delivered to the **top-level session**,
not to the agent that spawned it. An agent that dispatches a child in the background and
then yields to wait for that notification therefore waits for a message it can never
receive. It terminates having done nothing, and — because it exited without an error — it
reports no failure. The parent sees a completed child and a clean status.

It cascades: each level does the same thing to the level below, so a single drive can strand
a whole chain.

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

**Workaround.** Dispatch every phase agent synchronously (`run_in_background: false`) so the
result returns inside the dispatching agent's own turn. This fixes the level you control and
not the level below it, so a synchronously-dispatched agent that itself backgrounds a child
will still return thin. Treat any phase agent's "waiting for…" as a completed-with-nothing
result and verify against the repository, never against the payload.

**Fix direction.** Two candidates, not exclusive. Make the spawn convention explicit in the
agent templates — an agent that cannot receive notifications must never background a child —
which is a prompt-level fix and cheap. Or route child-completion notifications to the
spawning agent rather than the session root, which is the real fix and a harness change. In
the meantime, a supervisor that receives a child result containing no artifacts should treat
it as a failure and retry synchronously rather than advancing.
