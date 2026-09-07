---
title: An occupied workspace now refuses, instead of quietly building against a stale mainline
date: "2026-09-01"
time: "17:20"
type: manual
components:
  - build_orchestration
summary: "BO-2400f-13 and its four children: the fast lane recognises an occupied build workspace before it dispatches anything and ends in a named refusal with non-destructive and destructive options kept apart. Records the decision as ADR-039 and closes KI-BO-015, whose proposed remedy was the opposite."
description: "The lane could not previously see its own workspace at all — _worktree_exists knew feature/, ticket/ and ac-authoring/ but not fast-lane/. That root cause is fixed. What the lane does on finding an occupant is the part that needed deciding, because the known-issue entry and the acceptance criterion specified opposite behaviour and the contradiction only surfaced at the green gate."
---

## Entry

The fast lane could not recognise its own build workspace. `_worktree_exists` matched three hardcoded branch prefixes — `feature/`, `ticket/`, `ac-authoring/` — and not `fast-lane/`, so the lookup never matched, the reuse branch was unreachable code, and every run fell through to `git worktree add` and died with exit 128 the moment anything occupied the target path.

That is fixed: `refs/heads/fast-lane/<branch>` is now recognised.

### The part that needed a decision

What the lane should *do* on finding an occupant was specified twice, in opposite directions.

`KI-BO-015`'s title, symptom and fix-direction all argued for **reuse** — it framed the harm as "a fast-lane run can never reuse its own worktree" and listed non-idempotency as the cost. `BO-2400f-13` and its four children specify a **named refusal**: the run recognises the occupant before dispatching anything, ends in a refusal rather than a success, names both the criterion and the occupied location, and states each option's consequences so that clearing empty residue and discarding unsaved work are never offered as the same gesture.

The contradiction surfaced the hard way. A `/fast-lane-build BO-2400f-13` run reached its `verify_green_and_coverage` gate with the coder having implemented the AC's refusal and the test-writer having written a regression guard from the KI's framing. One test failed out of ten. Cost: roughly 80 minutes and 907k subagent tokens, no pull request.

### Refusal won, on three grounds

The weakest is precedence — an acceptance criterion is the specification, a known-issue entry is an observation with a suggested direction.

Better: reuse loses work. A workspace may hold a prior run's uncommitted changes, and silently building on top of them is how that work disappears.

Best, and the one that settles it: **a reused workspace is cut from a stale mainline.** The run would return a green result built against code that has since moved. The obvious remedy — refresh the worktree first — is foreclosed for the same reason, because it breaks `BO-2400f-3`'s promise that the workspace comes from the *latest* mainline. The AC anticipates this: "Bringing it up to date is the plausible-looking wrong implementation… it silently breaks BO-2400f-3's latest-mainline promise, and the operator cannot see that it happened."

Both apparent kindnesses are wrong, and the record said so before anyone tried them.

### The accepted cost

**Every re-run against the same criterion now needs an operator decision.** For a tool whose promise is "point at an acceptance criterion, get a pull request back", that is real friction, and it is the most likely reason someone will want to reverse this. It is recorded as the accepted downside in ADR-039, along with the evidence that would justify revisiting: if operators overwhelmingly pick `clear_and_rerun`, the refusal is asking a question with only one real answer.

An auto-clear for the provably-clean-and-unpushed case is the obvious middle path and was rejected for now — `uncommitted_changes` is nullable and `pr_lookup` can return `unavailable`, so "provably clean" is a compound judgement whose inputs can each come back undetermined. An auto-clear whose cleanliness proof degrades to a guess reintroduces the work-loss mode it was meant to avoid.

### Also here

`KI-BO-015` is closed, and its **title was corrected**. It read "can never *reuse* its own worktree", which states the remedy as if it were the defect; it now reads "cannot *recognise* its own workspace". That wording was not cosmetic — it is what the test-writer read, and it is why the collision happened.

### Proof

41 tests across six files, all green under `AC_ENFORCE_STRICT=1`, with per-record coverage: 12 on `BO-2400f-13`, 9 on `-13-i`, 7 on `-13-ii`, 5 on `-13-iii`, 8 on `-13-iv`. A further 45 tests across the changed module pass unchanged. Those five records are marked done through `mark_ac_done.py`'s own coverage gate rather than by assertion. `BO-2400f-3` was pulled in as an unmet dependency, has no test contract of its own, and is deliberately left `todo`.
