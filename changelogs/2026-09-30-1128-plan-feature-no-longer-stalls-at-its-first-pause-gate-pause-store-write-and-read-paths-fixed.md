---
title: "/plan-feature no longer stalls at its first pause gate — pause-store write and read paths fixed"
date: "2026-09-30"
time: "11:28"
type: manual
components: 
  - ac_driven_dev
  - build_orchestration
  - ac_store
  - commit_guardian
  - agent_registry
summary: "Fixed the mandated entry point for planning new work — /plan-feature was silently failing to save its progress every time it paused for your input, so no run could ever get past the first checkpoint — and corrected eleven acceptance-criteria records that had been marked complete before the underlying work actually was."
description: "7 commits. Categories: Bug Fixes (BO-2300e-2 routes the six pause-store dispatches from worktree-agent, which declined them, to command-step-runner; BO-2300e-3 replaces a fail-open pause-read with a three-way read/refusal/failure classification, and repairs 23 tests the write-path fix had broken unnoticed), Documentation (two known-issue filings, KI-ACD-20260928 and KI-CG-20260929), and Maintenance (ac-store reconciliation: eleven phantom-done composites corrected across three commits)."
commits: 
  - f1a9bd4d
  - 07aa5d47
  - 2ae165d1
  - 179d5245
  - e9457f8b
  - 78d452ff
  - 32e410fb
breaking: false
---

## Entry

`/plan-feature` is this repo's mandated entry point for all new work — every feature is
supposed to start there. Until this fix, an interactive run could not complete: it halted
at the very first user gate, every time, because the mechanism that saves your place while
you're away from the keyboard never actually saved anything.

### Two failures, one root cause

Every pause-store operation (write the pause record, read it back, clear it) was dispatched
to `worktree-agent`, whose charter is creating and removing git worktrees. Asked to persist
a pause record, it correctly declined — that's the guardrail working as designed — but
nothing dispatched the request anywhere else, so the run died at the first checkpoint.

That defect showed up in two different shapes:

- **The write path failed loudly.** A refused write surfaced immediately as
  `pause_persist_failed`, which is how the problem was first found.
- **The read path failed silently.** A refused read was indistinguishable from "no pause
  record exists yet" — a genuinely empty result. So a resumed run would sail straight past
  the check that should have stopped it and fail later, somewhere that looked unrelated to
  pausing at all.

Both are fixed. Pause-store work now goes to `command-step-runner`, an agent chartered to
run one given command in one named workspace — the write half landed in `179d5245`, the
read half (the harder, silent one) in `78d452ff`, via a shared helper that now reports three
outcomes instead of two: a genuine empty read, a refusal, and an outright failure. Only the
first may report "no record."

Fixing the write path broke 23 tests outside the directory its own verification covered,
without anyone noticing at the time; `78d452ff` found and repaired all 23 as part of closing
out the read-path fix.

### Eleven phantom-done acceptance criteria corrected

While tracking this down, eleven AC-store records turned up marked `done` while the work
they described was not finished — including the very record whose own promise ("a paused
run waits reliably until you get back to it") this bug broke. One of the eleven had also
been quietly exempt from a schema rule that requires a test contract, because that rule
only applies to records that are *not yet* marked done — so the false `done` was hiding a
second, unrelated gap as well as the first.

### Two guard defects filed, not fixed here

- **KI-CG-20260929** — a commit-guardian check derives "this record asserts a durable
  write" from a keyword regex with no notion of negation, so a criterion that explicitly
  *forbids* a durable write reads as asserting one.
- **KI-AR-004** — no agent in the package is currently chartered to own
  `templates/workflows-js/` bodies at all. 32 acceptance criteria assign that work to an
  agent that declines it on charter grounds; only 18 are findable by a path-based sweep; a
  quarter of that set (the three BO-2300e-3 records this branch corrects) were themselves
  in that blind spot.

### What this does not claim

`BO-2300` (the top-level record for this whole effort) is still `in_progress`, not `done`:
its `BO-2300a` children remain `todo`. Three further phantom-done records were found in the
same sweep (`BO-2300a-3`, `BO-2300d-2`, and `BO-2300d`, which sits above one of them) and
were deliberately left alone for a separate pass rather than folded in here.

This has not been verified by running `/plan-feature` end-to-end interactively since the
fix landed. What backs it instead: 14 behavioural tests that drive the real workflow under
`run_workflow_under_e2` (asserting on captured agent dispatches, not on source text), plus
a full `unit_tests/workflows/` run at 852 passed, 0 failed.
