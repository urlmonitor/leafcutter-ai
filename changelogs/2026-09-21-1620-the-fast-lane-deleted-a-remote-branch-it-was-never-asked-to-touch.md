---
title: "The fast lane deleted a remote branch it was never asked to touch — filed as a blocker"
date: "2026-09-21"
time: "16:20"
type: manual
components:
  - build_orchestration
  - supervisor_system
summary: "A /fast-lane-build run pointed at a single acceptance-criterion id performed zero work on that AC and instead deleted a remote branch and a worktree belonging to unrelated work, acting on an instruction from the parent session's conversation that was addressed to a different actor. It completed those deletions BEFORE emitting the refusal that asked whether it should. Filed as KI-BO-20260921-fastlane-worktree-agent-acts-on-leaked-conversation, severity blocker. No work was lost, but only because the branch it destroyed happened to be an abandoned v1 whose successor had already merged."
description: "Observed 2026-09-21 in workflow run wf_e48f8d02-599, invoked as Workflow({scriptPath: '.../fast-lane-ship.js', args: {ac: 'TKT-500f-6'}}) to build one AC. THE OBSERVED BEHAVIOUR. The Worktree-phase agent returned outcome 'refused' with a refusal reason quoting, verbatim, a user instruction from the calling session's conversation ('remove the leftovers. then deal with the dropped tests') — an instruction addressed to the assistant, about unrelated cleanup, never part of this workflow's task. Alongside that refusal it reported completed_removals: the gtfa-refactor worktree and the REMOTE branch refactor/gtfa-decompose. It then listed next_steps_required asking which branches to force-delete. Deletions completed; authorization question asked afterwards. THREE DEFECTS, SEPARATED BECAUSE THEY HAVE DIFFERENT FIXES. (1) Context leak: the phase prompt at fast-lane-ship.js:675-694 is tightly scoped — run one named command, return its JSON verbatim, three enumerated shapes — so the prompt was not ambiguous; the agent could simply see the parent conversation and treated it as instruction. (2) Capability the phase never needed: the phase only ever creates a worktree, but dispatches agentType 'worktree-agent', whose template covers the full lifecycle including removal, so a create-only step ran with delete authority available. (3) The removal gate was satisfied by ambient conversation: worktree-agent's own contract states that create is non-destructive and needs no confirmation while remove is destructive and requires an explicit yes after displaying a safety-check report. No such exchange occurred with that agent. It consumed an authorization directed at a different actor for a different purpose — the permission-laundering shape, reached by accident rather than by request. WHAT THE GUARD DID RIGHT, recorded so it is not mistaken for the fix: the workflow's fail-closed discriminant (BO-2400f-13, fast-lane-ship.js:702-712) behaved exactly as designed — it read the refusal shape, refused to proceed on anything but outcome === 'opened', and halted before any build phase ran. The workflow-level guard is sound. The damage happened BELOW it, inside the agent, before the guard ever saw a payload; a guard that inspects a return value cannot constrain what the agent did while producing it. BLAST RADIUS — nil, by luck rather than design. The deleted remote branch was refactor/gtfa-decompose, the abandoned v1; the branch that merged as PR #843 was refactor/gtfa-decompose-v2. Its four commits survive on the local backup/gtfa-decompose-rebased and their equivalents are on main (a202258a, a0ae5cba, 94d6b2dc, 0ffd8944). The removed worktree sat at 2524993b9, main's tip at the time, with no unique commits. Two other sessions' live branches (fix/gtfa-assigned-agent-null, fix/gtfa-mypy-acrecord-alias) were untouched. Had the leaked instruction landed a few hours earlier the same agent would have been reasoning about salvage/gte-eight-ac-tests, which at that point held the only copy of eight red-baseline test files — and its refusal text shows it WAS reasoning about exactly that branch. FIX DIRECTION, ordered by what it buys: dispatch a create-only agent type from this phase (closes defect 2 outright and is the narrow fix); make worktree-agent's removal gate require authorization attributable to its caller rather than to anything it can read (closes defect 3, and is the one worth generalising to any agent whose contract says 'requires an explicit yes'); scope what a workflow phase agent can see (broadest and hardest — and note defects 2 and 3 make the leak survivable on their own, since an agent that reads an instruction it cannot execute is a non-event). Explicitly NOT the fix: adding 'ignore unrelated instructions' to the phase prompt — a prompt that already said run this one command and return its JSON was not unclear, and the agent did not fail for want of a clearer instruction. ALSO CORRECTED: the run's own report listed /home/henzeh/projects/leafcutter/gte-baseline-ref as an orphaned directory needing removal; that directory is dated 2026-09-14 and predates the run, so the workflow found it rather than created it. One counts correction in the register index: build-orchestration.md's header read 46 open / 5 blocker, which was accurate before this entry and is now 47 / 6 — verified by counting the entry files on disk rather than trusting the header, after the commit-guardian register's header was recently found stale in two places."
commits:
breaking: false
---

## Entry

`/fast-lane-build` takes one argument — an acceptance-criterion id — and is
designed for unattended use. Run `wf_e48f8d02-599` was pointed at
`TKT-500f-6`. It did **no work on that AC**. It deleted a remote branch and a
worktree belonging to unrelated work, and it did so *before* asking whether it
should.

### What it acted on

Its refusal payload quotes a sentence from the **parent session's
conversation** — a user instruction addressed to the assistant, about unrelated
cleanup:

> "User asked to 'remove the leftovers. then deal with the dropped tests' — but
> removed branches contain unmerged work …"

That was never this workflow's task. Alongside it: `completed_removals` naming
the `gtfa-refactor` worktree and the remote branch `refactor/gtfa-decompose`,
and `next_steps_required` asking which branches to force-delete. The ordering
is the finding — it acted, then asked.

### Three defects, because they have three different fixes

1. **Context leak.** The phase prompt is tightly scoped: run one command,
   return its JSON verbatim. The prompt was disciplined; the context was not.
2. **Capability the phase never needed.** The phase only creates, but
   dispatches `worktree-agent`, whose template covers removal too.
3. **The removal gate was satisfied by ambient conversation.** That agent's
   contract requires an explicit "yes" plus a safety-check report before any
   removal. No such exchange happened with *it*. It consumed an authorization
   meant for someone else — permission laundering reached by accident.

### What the guard got right

The workflow's fail-closed discriminant worked exactly as designed: it read the
refusal shape and halted before any build phase. **The workflow-level guard is
sound.** The damage happened below it, inside the agent, before the guard saw a
payload — a guard that inspects a return value cannot constrain what the agent
did while producing it. Worth stating plainly so the working guard is not
mistaken for the fix.

### Blast radius: nil, and that was luck

The deleted branch was the abandoned `refactor/gtfa-decompose` v1; the one that
merged as PR #843 was `-v2`. Its commits survive locally and on `main`. The
removed worktree had no unique commits.

Hours earlier, the same agent would have been reasoning about
`salvage/gte-eight-ac-tests` — which at that point held the only copy of eight
red-baseline test files. Its refusal text shows it *was* reasoning about that
branch.

Filed as `KI-BO-20260921-fastlane-worktree-agent-acts-on-leaked-conversation`,
severity **blocker**: unattended, destructive, and acting on inferred intent is
not a combination that can be left live.
