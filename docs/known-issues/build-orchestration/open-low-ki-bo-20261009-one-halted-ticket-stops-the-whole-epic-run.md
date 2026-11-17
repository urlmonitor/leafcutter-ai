---
title: "KI-BO-20261009-one-halted-ticket-stops-the-whole-epic-run — in practice any single ticket's handoff or blocker ends the /build-feature run, because a halting batch almost always leaves staged files and that stops the run; each manual re-run re-plans from scratch, and the end-of-run epic re-read is an unreliable agent listing"
description: "medium — the BO-4300 drive needed about 30 manual re-runs. BO-100e-4 meant a halt to no longer end the run, but the same block stops it whenever the halting batch leaves anything staged (build-feature.js:3529-3543), which in a shared epic worktree is the normal state. Every re-run repeats the resolve, the planner and every read-back. The completion-time re-read is a status-checker listing the folder; it once reported tickets that were on disk as no longer present, and once could not list the folder."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-12'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-025.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261009-1832.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260901-0920.md
---

# KI-BO-20261009-one-halted-ticket-stops-the-whole-epic-run — one ticket's halt ends the run, and each re-run starts over

> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Nothing wrong is written, and each halt is reported. But a 14-ticket epic
  took about 30 manual re-runs. Each re-run is a fresh resolve, plan and read-back of every
  ticket, and so another chance to hit the non-deterministic steps recorded in
  `KI-BO-20261009-epic-worktree-resolution-is-split-brained` and
  `KI-BO-20261009-completion-write-refuses-closes-the-script-allows`.
- **Status:** open, no AC. The run stop is verified by reading the code. That it was the route on
  each of the ~30 re-runs is inferred: the run payloads were not retained here.
- **Occurrences:** about 30 re-runs over the BO-4300 drive (2026-09-28 to 2026-10-09), 2 bad
  re-reads (session count). Then 1 run on EPIC-RightJobRightAgent (`wf_54e15913-aea`,
  2026-10-12), with the stop confirmed from the run's own payload. See "Observed again,
  2026-10-12".
- **First seen:** 2026-09-28 · **Last seen:** 2026-10-12
- **Where:** `templates/workflows-js/build-feature.js` on `origin/main` `c373b005e`: halt handling
  (:3473-3545, the stop at :3538-3542); the planner (:3074-3091); `recheckEpicTicketSet`
  (:2634-2649).

## Symptom

Whenever one ticket in a batch handed off to a phase the driver refused, or returned a blocker
the classifier routed to halt, the run ended. Its siblings and every later batch waited for the next
manual `/build-feature`. Each re-run re-planned the epic from the folder.

At the end of two runs, the completion-time re-read of the epic folder was wrong. Once it reported
tickets as "no longer present" that were on disk. Once it could not list the folder at all.

## Mechanism

1. **The halt is supposed to be local.** BO-100e-4: "a halt no longer ends the run: halted,
   incomplete and withheld tickets accumulate" (:3504-3506).
2. **The run still stops if anything is staged.** After a halting batch the driver reads the
   worktree's dirty state once. If anything is staged, or the state cannot be read, it sets
   `haltStop` and does `break epicLoop` (:3533-3542). In a shared epic worktree something is
   nearly always staged: the commit agent stages the ticket before it commits
   (`KI-SS-20260927-commit-signoff-precedes-the-commit`), and sibling tickets' phases stage their
   work. On 2026-09-30, ticket 02's commit agent found tickets 04 and 05's files staged in the
   shared index (see `KI-BO-20260901-0920`). So a halt in practice still ends the run.
3. **Halts are easy to trigger.** A handoff whose target is not on the ticket, is deferred, or is a
   phase the handing phase just added is refused and halts the ticket (:2389-2403;
   `KI-BO-20261009-1832`). A blocker classified `design`, `halt` or unknown halts it too
   (:2476-2493).
4. **A re-run keeps nothing from the last one.** The planner is an agent that reads every ticket
   again (:3074-3091). No record of the previous run's plan or progress is carried forward except
   what is in the ticket files.
5. **The re-read is an agent listing.** `recheckEpicTicketSet` asks a status-checker to list
   `NN_*.md` with statuses (:2636-2641). There is no script behind it. An unreadable reply fails
   closed (:2681-2690), which is correct. A readable but wrong listing goes into
   `no_longer_present_not_completed` (:3590) as if it were true.

## Impact

Operator time and model cost scale with the number of halts, not the number of tickets. The epic
cannot run unattended, and the repeated resolve and plan steps multiply the exposure to the other
non-deterministic steps. A wrong re-read misstates what is left to build.

## Fix direction

- Scope the staged-leftovers stop to the halted ticket: stop only if the staged files belong to it,
  or unstage the halted ticket's files and continue the run.
- Let a refused handoff dispatch the named target when it is a real phase agent, rather than
  halting the ticket (see `KI-BO-20261009-1832`).
- List the epic folder with a script (glob plus frontmatter read), not an agent. The planner's
  enumeration can use the same script.
- Persist the plan and per-ticket outcome between runs, so a re-run resumes rather than re-plans.

**Related.** `KI-BO-025` (plans only the first wave) is the earlier form of "one run cannot finish
an epic". The driver now re-plans within a run through repeated looks (BO-100e-1), but the stop
above ends the run before those looks are reached.

## Observed again, 2026-10-12

**Where:** `/build-feature` on EPIC-RightJobRightAgent (48 tickets), run `wf_54e15913-aea`.
`templates/workflows-js/build-feature.js` at `b6249edd3`, which is the script the run
executed. The stop is at :3529-3543.

**What happened.** Look 1 planned three batches: batch 1 with tickets 01, 03, 04, 06 and 46,
batch 2 with 20 and 27, and batch 3 with 22 and 41. All nine have an empty `depends_on`. In
batch 1, four tickets halted at `documentation-expert`
(`KI-BO-20261012-documentation-expert-cannot-reach-its-specialists-in-the-flat-driver`). Ticket
46 was recorded complete even though its commit was refused
(`KI-BO-20261009-completion-write-closes-a-ticket-whose-gate-failed`, occurrence 2026-10-12).
The dirty-state read then found 13 staged paths, and the run stopped: "Stopped: batch 1 left
staged changes the next commit would sweep in". The payload shows `looks: 1`, `batches_run: 1`
and `ended_because: "halted"`.

**What this adds.**

- **The stop also abandons batches already planned.** Batches 2 and 3 were in look 1's own
  plan. All four of their tickets were free of dependencies and none of them halted, but none
  was started. A halt in one batch costs every later batch of the same look, not only the later
  looks.
- **The staged files were mostly not a halted ticket's.** Ten of the 13 paths were ticket 46's:
  its nine work files plus the ticket, staged by its commit agent for a pathspec commit that
  `check-doc-length` refused. The run had counted ticket 46 as *completed*. The other three
  were the ticket files of halted tickets 01, 04 and 06. Inferred: their phases' sign-off
  writes staged them, since the phase agents in this run report staging the ticket after
  signing off. So the first fix direction above, scoping the stop to the halted ticket's files,
  would still have stopped this run. The worst leftover belonged to a ticket the driver
  believed was finished.
- **The completion report then hid the cause.** The 39 dependants that the missing look 2
  would have reached were reported as work "discovered after planning"
  (`KI-BO-026`, occurrence 2026-10-12). That sent the diagnosis to the planner rather than to
  this stop.
