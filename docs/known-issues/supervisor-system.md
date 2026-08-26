---
title: "Known issues — supervisor-system"
description: "Open, observed defects in the supervisor-system component: ticket-supervisor, the phase-agent dispatch chain, and the conventions agents follow when spawning sub-agents. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-26
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

---

> **Entries `KI-SS-002` … `KI-SS-004` are recovered from an unmerged branch.** They were
> observed directly on 2026-08-19 while driving `EPIC-GE122UniquenessPassAndRepair` — not
> inferred from reading the code — and written into the parallel known-issues register PR #495
> invented (as `KI-SUP-1` … `KI-SUP-3`), which was discarded during reconciliation. All three
> were re-verified against `main` at `37655862`; `KI-SS-002`'s mechanism had to be **corrected**
> in the process and the correction is recorded in the entry rather than edited away.

---

### KI-SS-002 — A gate adjudicated `failed` does not stop the drive, so the commit phase still runs

- **Severity:** high — a phantom-done defect one level up from the ones the package exists to
  prevent
- **Status:** open — code is on `main` and live, **but by a different mechanism than the one
  originally recorded** (see the correction below)
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/workflows-js/build-feature.js:1757-1772` (the `!verdict.verified`
  branch) and `:305-328` (`phaseOrder`, `commit` at priority 12)

**Symptom as observed.** During the epic drive, `pr-reviewer` and `documentation-verifier` both
returned `status: blocker` on ticket `01_TICKET-20260818-GE-122a-1.md`. Neither blocker was
remediated. The drive nevertheless proceeded to the `commit` phase, which committed and set
`commit: signed_off` while the frontmatter still read:

```yaml
documentation-verifier: failed
pr-reviewer: failed
```

The commit message did name both open blockers, so the record is not dishonest — but a gate that
reports a blocker and is then committed past provides no enforcement. The two blockers were real:
one was a performance regression that would have shipped a commit-time gate slow enough to be
routinely bypassed, the other a malformed contract line.

**CORRECTION — the mechanism named on the branch is closed; the defect is not.** The branch
recorded the cause as *"the precondition check is missing, not the ordering"*, implying an
agent-reported blocker walks straight past `commit`. On `main` that specific path is **shut**:
`build-feature.js:1656` intercepts `resultStatus === "blocker" || "failed"`, and every
classification outcome either returns `status: "blocked"` (mechanical-retries-exhausted, design,
halt, unknown) or `break`s out of the phase loop (`cross_agent`). `commit` cannot be reached that
way. Filing the original text unchanged would have pointed the fix at code that already does the
right thing.

**What is actually live.** The same shape survives one branch over, on the *verification* path.
When a phase reports success but its sign-off record cannot be confirmed, the drive adjudicates
it failed — and then continues:

```js
if (!verdict.verified) {
  unverifiedPhases.push({ agent: phaseName, reason: verdict.reason });
  unverifiedReasons[phaseName] = verdict.reason;
  log(`VERIFICATION FAILED for '${phaseName}' ... The gate is adjudicated failed and is
       NOT counted as completed.`);
} else { ... }
```

There is no `break` and no `return`. `unverifiedPhases` is collected, threaded into the payload
at `:1792` and reported at `:955-956` — and consumed by nothing that stops the loop. So the
iteration advances to the next entry in `phaseOrder`, and `commit` sits at priority 12, last.
A gate the drive itself has just declared failed is followed by a commit.

The comment above that branch states the intent honestly — *"The drive continues so the remaining
gates still run and are reported, but the ticket can no longer be recorded complete"* — which is
right for a *reporting* gate and wrong when the remaining phase is `commit`. Withholding the
completion claim is not the same as withholding the commit.

**Detection.** After any drive, check for a ticket where `commit: signed_off` coexists with any
phase in state `failed`, and check the payload for a non-empty `unverified_phases`:

```bash
grep -n "failed" <ticket>.md
```

**Workaround.** Do not treat drive completion as evidence. Read the frontmatter `agents:` map
directly and confirm no phase is `failed` before merging.

**Fix direction.** Gate the `commit` phase specifically on `unverifiedPhases.length === 0` —
the collection already exists and is already correct, it is simply never consulted. Everything
before `commit` should keep running and reporting, which is what the current comment argues for
and what makes the narrow fix the right one.

**Pattern:** a signal computed correctly and then not consumed — the same shape as
`commit-guardian.md`'s `KI-CG-007` and `KI-CG-026`, here at the orchestration layer.

---

### KI-SS-003 — The adjudication ladder escalates to `brainstorm-lead` without a per-ticket cap and can burn a drive without converging

- **Severity:** medium
- **Status:** open — code is on `main` and live; the code carries a per-*phase* retry cap and no
  per-*ticket* escalation cap at all
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/workflows-js/build-feature.js:1657-1668` (the `failure-classifier`
  dispatch) and `:296` (`MAX_RETRIES = 2`); `templates/skills/building-epics/SKILL.md` §4

**Symptom.** Three `brainstorm-lead` escalations fired on a single ticket and none produced an
applied fix. Roughly 50 minutes of a 2.5-hour drive went to them. In one case the blocking agent
had already written the exact corrective line into its own sign-off comment; the escalation did
not apply it, and it was later applied by hand in a single edit.

For scale: the full drive covered **one** ticket of five in 2.5 hours. Driving the same gates by
direct dispatch covered the equivalent ground and found three real defects in roughly 90 minutes.

**Root cause.** `building-epics` §4 specifies a cap of one escalation per ticket. Nothing
implements it. `build-feature.js` dispatches `brainstorm-lead` as the `failure-classifier` on
**every** blocker or failure, unconditionally, before any classification exists to gate on. The
only bound in the code is `MAX_RETRIES = 2` per phase name — so a ticket with several failing
phases can legitimately escalate many times while every individual counter stays inside its
limit. The observed behaviour did not violate the code; the code never encoded the rule.

**Detection.** Count `brainstorm-lead` spawns per ticket in the workflow transcript directory.
More than one on the same ticket is a signal:

```bash
grep -l brainstorm-lead <session>/subagents/workflows/<run>/agent-*.meta.json
```

**Workaround.** When a blocker's own remediation text is concrete and mechanical, apply it
directly rather than routing it through escalation.

**Fix direction.** Two parts, in order of value. (1) Before escalating, check whether the
blocker's sign-off contains an actionable remediation and attempt that first — in the observed
case the answer was already written down and the escalation was pure cost. (2) Count escalations
per *ticket*, not per phase, and enforce the §4 cap of one. A documented cap that no counter
implements is worse than no cap, because it is read as a guarantee.

---

### KI-SS-004 — A workflow invoked by name can run a stale session-cached script

- **Severity:** low — the workaround is reliable
- **Status:** open — a harness-level behaviour, independent of repository state; reproduced
  repeatedly and unaffected by anything on `main`
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** the Workflow tool's by-name resolution, against `.leafcutter/workflows/<name>.js`

**Symptom.** Invoking a workflow by name may execute a stale session-cached script even after
`build.py` has redeployed it. The redeploy succeeds, the file on disk is correct, and the run
still exercises the old code — so a verified fix appears not to work.

**Why it costs time out of proportion to its severity.** It presents identically to "the fix is
wrong". An agent that has just edited a workflow, rebuilt, and re-run has every reason to
conclude the edit was ineffective, and the disk state supports the opposite conclusion only if
someone thinks to check it.

**Workaround.** Invoke by `scriptPath` against `.leafcutter/workflows/<name>.js` to force the
current version.

**Related:** `testing-quality.md`'s `KI-TQ-004` is the same hazard one layer down — a stale
deployed copy pinned in `sys.modules` for a whole pytest session. Both turn "I rebuilt" into a
false premise.

---

### KI-SS-005 — Concurrent agents in one worktree each report their siblings' files as another session's stray work

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1 (4 agents, 1 dispatch, all four identical)
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `templates/agents/product-owner.md`, `templates/agents/business-analyst.md`,
  `templates/agents/it-po.md` — none states that the agent may be one of several concurrent
  writers in the same tree. The fan-out site inherits the gap rather than causing it.

**Symptom.** Four AC-authoring agents were dispatched in parallel into one shared worktree. Each
ran `git status`, saw untracked AC YAML it had not written, and reported it — unprompted, in its
sign-off — as unrelated pre-existing work from other parallel sessions, recommending it be left
alone. Every file so described had been written minutes earlier by a sibling in the same dispatch.
All four made the same call independently.

**Why it is not just noise.** The inference is locally sound: an agent sees untracked files it did
not create, and nothing in its prompt says a peer might be writing beside it, so "another session"
is the only available explanation. That makes it a systematic misreading rather than a mistake any
one agent could avoid.

Three costs, in ascending order of seriousness:

1. **The operator gets four contamination reports for one clean tree.** Each is individually
   credible and, read together, suggests the worktree is unusable — the exact opposite of the
   truth.
2. **Staging advice is wrong in a way that looks careful.** "Leave these alone, they are not
   yours" is the correct instinct applied to the wrong facts; followed literally at commit time it
   drops the sibling work the same drive just produced.
3. **The failure mode is one step away.** An agent that decides stray untracked files should be
   cleaned up rather than preserved would destroy peer output, and untracked AC and ticket folders
   are unrecoverable. Nothing observed here went that far — no work was lost — and the reason is
   that all four chose the conservative branch, not that anything prevented the other one.

**Fix direction.** Tell the agent what it is. A dispatched agent that may run concurrently should
be told so, and told the rule that follows: files you did not write are peers' work — never
foreign, never stray, never yours to clean up or to characterise in a sign-off. The narrow,
mechanical form of the rule is that an agent stages by explicit path (`git commit -- <paths>`,
already the project's practice) and reports only on paths it wrote, which makes the whole
distinction moot rather than requiring the agent to reason about it correctly.

Resist fixing this by having each agent work out who wrote what — timestamps and `git status`
cannot answer it, and an agent that guesses confidently is what produced the reports above.

**Related:** `build-pipeline.md`'s `KI-BP-20260826-1331` is the same shape at the filesystem layer
— shared mutable state written by parties who do not know each other exist. There, the writers
collide; here, they only misdescribe each other. Project memory *"Commit into a dirty shared
tree"* records the operator-side half of this.

**Pattern:** an agent reasoning correctly from a prompt that never told it it had company.
