---
title: "KI-SS-001 — An agent that backgrounds a sub-agent then waits for it parks forever, and the stall cascades down the chain"
description: "KI-SS-001 — An agent that backgrounds a sub-agent then waits for it parks forever, and the stall cascades down the chain"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - supervisor_system
related_docs:
  - docs/known-issues/supervisor-system.md
  - docs/known-issues/README.md
---

# KI-SS-001 — An agent that backgrounds a sub-agent then waits for it parks forever, and the stall cascades down the chain

> One known issue, split out of `docs/known-issues/supervisor-system.md` on
> 2026-09-14. Index: [supervisor-system.md](../../supervisor-system.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** closed — not reproducible. See "Closed 2026-09-23" at the foot of this entry.
  Not marked fixed: no code change closes the mechanism this entry names.
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

**Re-verified 2026-09-23: CANNOT DETERMINE — left open, blocker unchanged.** This entry's
core claim is a live property of the Claude Code harness's subagent execution model ("a
subagent has no idle state" / no wait primitive survives being stripped from a subagent's
tool set). That is not something reading this repo's code can confirm or refute either way
— it would take actually reproducing a background-then-wait stall at runtime, which is an
orchestration-behaviour probe, not a code-inspection one, and this audit was scoped to
reading and running repo code. So, per the letter of this re-verification: no verdict is
asserted on whether the underlying stall still occurs.

What COULD be checked from the repo, specifically because ACD-2100 reworked `/plan-feature`'s
entry point and decision gates and this entry names `plan-feature.js` as one of the
partially-remediated call sites: the mitigation is still there and unregressed.
`templates/workflows-js/plan-feature.js` still carries five `status: "undetermined"` call
sites after ACD-2100's rework of the entry point and gates — so that narrow protection (a
parked phase can't be silently counted as `ok`) survived the rework. Also checked and still
true today: no `SubagentStop` hook exists anywhere in the repo (a repo-wide search for
`SubagentStop` finds only this entry and its own changelog record), and
`scripts/registry_validator.py`'s spawn-related checks are limited to
`spawn_allowlist`/`spawned_by` symmetry and self-loop detection — nothing there mechanically
forbids an agent from backgrounding a child and waiting on it. Both "Fix direction" items
(route fan-out into the depth-0 JS runtime; a fail-closed `SubagentStop` veto) remain
unbuilt. None of this proves or disproves that a fresh stall can still happen; it only
confirms the previously-recorded partial remediation has neither regressed nor grown since
2026-08-25, and that this entry's own "does not close this issue" conclusion still applies to
everything checkable from source.

---

> **Entries `KI-SS-002` … `KI-SS-004` are recovered from an unmerged branch.** They were
> observed directly on 2026-08-19 while driving `EPIC-GE122UniquenessPassAndRepair` — not
> inferred from reading the code — and written into the parallel known-issues register PR #495
> invented (as `KI-SUP-1` … `KI-SUP-3`), which was discarded during reconciliation. All three
> were re-verified against `main` at `37655862`; `KI-SS-002`'s mechanism had to be **corrected**
> in the process and the correction is recorded in the entry rather than edited away.

---

**Closed 2026-09-23 — CLOSED, NOT REPRODUCIBLE (not fixed).** This entry already carries a
same-day "Re-verified 2026-09-23: CANNOT DETERMINE" note (above) concluding that the core
claim — a subagent backgrounding a child and waiting on it parks forever — is a live property
of the Claude Code harness's execution model, unconfirmable and unrefutable by reading or
running repo code. That conclusion is adopted here rather than redone: this pass re-checked
each of its three checkable facts independently and found all three unchanged:

```
$ grep -c '"undetermined"' templates/workflows-js/plan-feature.js       # (status: assignments)
4   (lines 2663, 2847, 3212, 3368 — a fifth reference at line 3363 is the file's own
     comment, "...the other four call sites...", naming the same set)

$ grep -rl "SubagentStop" .                     # whole worktree
docs/known-issues/supervisor-system/resolved/resolved-blocker-ki-ss-001.md   (this entry)
changelogs/2026-08-25-2210-a-dead-agent-is-no-longer-counted-as-a-completed-phase-ticket-or-epic.md
# no hook config, no settings.json entry — the hook still does not exist anywhere

$ grep -n "spawn_allowlist\|self.loop" scripts/registry_validator.py
# still limited to _check_spawn_bidirectionality / _check_self_loops — no mechanical
# check forbids an agent from backgrounding a child and waiting on it
```

So: the `status: "undetermined"` mitigation in `plan-feature.js` is intact and unregressed
(the file has been substantially reworked since by ACD-2100, and the mitigation survived
that rework); no `SubagentStop` hook has been added; `registry_validator.py`'s spawn checks
are unchanged. Nothing here is capable of proving or disproving a fresh stall.

Per the ticket's own decision rule, this qualifies for **closed — not reproducible** rather
than **still true** or an indefinite **cannot determine**, on the following reasoning: the
entry is now over five weeks old (first seen 2026-08-18), its only two occurrences were both
observed in a single drive on that one day, and every checkable artifact tied to those two
occurrences (the `ticket-supervisor` / `architect-review` dispatch path recorded in "Evidence"
above, and the `plan-feature.js` call sites recorded in the prior re-verification) has since
been reworked at least once (ACD-2100 for `plan-feature.js`) without reproducing or
regressing the described stall. No fix is identified for the underlying claim — the harness
property this entry names may still be entirely true today, and nothing above says otherwise.

**One discrepancy worth flagging rather than quietly correcting:** this closure was requested
under a premise that described the entry as carrying `Occurrences: 1`. The entry's own
`Occurrences` line (above) has read `2 (same drive, two levels of the chain)` since it was
filed on 2026-08-18, and that has not changed. The reasoning above treats "two levels of one
drive, one day" as substantively the single-incident case the closure criterion contemplates,
but the literal field value is 2, not 1 — recorded here so the count is never misquoted from
this entry going forward.

**Reopen if:** a fresh background-then-wait stall is observed and can be tied to a specific
dispatch (as the original two were), or the harness's fork-mode default-on-background change
(flagged as "one release away" in the original entry) lands and removes `run_in_background`
from the `Agent` tool — at which point the workaround this entry documents stops being
available and the underlying risk becomes untestable by a different route.

---
