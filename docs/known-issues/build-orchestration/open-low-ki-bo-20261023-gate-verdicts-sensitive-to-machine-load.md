---
title: "KI-BO-20261023-gate-verdicts-sensitive-to-machine-load — on a busy Windows machine the done-proof gate and the wrong-version finish step stop on tests that pass when run alone, and mark_done does not say which test failed or timed out"
description: "medium — with two lanes running heavy pytest suites at once, fast_lane.py mark_done reported ACs stale whose tests all passed on rerun (TQ-500g-3-i, TQ-500g-2-i), and wrong_version_gate.py finish stopped on 'failing on the code as written' for all 7 TQ-500g-3-ii tests (they pass alone) and on 'pytest exceeded its 330s timeout budget' for TQ-500g-2-i. Tests that spawn nested pytest runs inside done_proof's budget are hit hardest. The gates fail closed, but each false stop costs a 10-25 minute rerun, and mark_done prints no reason."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/how-to/fast-lane-build.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261009-1833.md
---

# KI-BO-20261023-gate-verdicts-sensitive-to-machine-load — gate verdicts flip under machine load

> Filed 2026-10-23. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The gates fail closed, so nothing wrong is marked done or committed. But
  each false stop costs a 10-25 minute rerun. It also teaches the operator to read a stop as "a
  flake", which is the wrong habit for a gate whose job is to stop real failures.
- **Status:** open, no AC.
- **Occurrences:** 4 stops across 3 ACs on 2026-10-22 (TQ-500g-3-i, TQ-500g-2-i twice,
  TQ-500g-3-ii), all while two lanes ran heavy pytest suites on one Windows machine.
- **First seen:** 2026-10-22 · **Last seen:** 2026-10-22
- **Where** (line numbers at `origin/main` `212a126bf`):
  - `scripts/build_orchestration/fast_lane.py`:564-581, the `mark_done` subcommand. It calls
    `verify_done_eligible` per AC (:570) and reads only `verdict["eligible"]` (:571). The
    verdict's `reason` is dropped. The printed payload (:575-579) carries only `marked_done`,
    `all_done` and `stale`.
  - `scripts/ac_store/done_proof.py`:324-326 and :336-375, `_resolve_pytest_timeout_seconds`:
    a 30s collection floor plus 300s per linked test file, so one linked file gets 330s.
    :1356-1370: a `TimeoutExpired` becomes the run-incomplete sentinel with a message that goes
    to stderr only.
  - `scripts/build_orchestration/_wvr_pytest.py`:178-186. The wrong-version runner uses the same
    budget, and a timeout becomes `PytestRun("timeout", "pytest exceeded its ...s timeout
    budget")`.
  - `scripts/build_orchestration/wrong_version_runner.py`:247-255, `_baseline`. A run that did
    not finish gives "the run on the code as written was cut short (timeout)" (:252). A run that
    finished with a test not `PASSED` gives "failing on the code as written (outcome ...)"
    (:254), which is also what a test that failed only because its own nested pytest ran out of
    time produces.

## Symptom

- `mark_done` prints `{"marked_done": [...], "all_done": false, "stale": ["<ac-id>"]}` and exits
  1. Every linked test passes when rerun. Nothing in the output says which test failed or that a
  run timed out.
- `finish` stops with `reason: "failing on the code as written"` for tests that pass when run
  alone, or with rows "the run on the code as written was cut short (timeout): pytest exceeded
  its 330.0s timeout budget".

## Mechanism

1. **The budgets assume an idle machine.** 300s per file is generous for one suite. With two
   lanes running heavy suites at once on Windows, process start-up and file I/O slow down
   enough that a long file goes over.
2. **Nested pytest multiplies the effect.** Some tests start their own pytest subprocess, using
   the same done-proof budget logic (for example the TQ-500g-1 and TQ-500g-2-ii fixtures that set
   `LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS`). The inner run times out first. The outer test
   then fails by assertion, so the outer gate reads "failing", not "timeout".
3. **mark_done hides the cause.** `done_proof` builds a reason, but `fast_lane.py` throws it away
   and prints only the stale ids. The operator cannot tell a real failure from a timeout without
   rerunning.

## Detection

A `stale` from `mark_done`, or a `finish` stop on "failing on the code as written" or "cut short
(timeout)", while another heavy gate or test suite was running on the same machine. Rerun the
named tests alone: if they all pass, it is this issue.

## Workaround

Run one heavy gate at a time on a machine. Rerun a stopped gate once with nothing else heavy
running before acting on its verdict. For one rerun,
`LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS` raises the budget.

## Suggested fix

Directions only; nothing here is applied.

- **Name the cause in mark_done.** Add each non-eligible AC's `reason` to the payload, so the
  output names the failing test or the timeout.
- **Tell timeout from failure in finish.** `finish` already says "cut short (timeout)" when its
  own run times out. Do the same in the row detail when a test failed because a nested run timed
  out, if the test's output shows it.
- **Document the limit.** State "one heavy gate at a time per machine" in
  `docs/how-to/fast-lane-build.md`. That file is already 478 lines, over the 300-line doc limit,
  so the note must be balanced by an equal cut.
- **Consider scaling budgets** for tests that start nested pytest runs, so the outer budget
  covers the inner one.

**Related.** `KI-BO-20261009-1833` is another gate verdict lost to a timeout, there in the
relaying agent's 120s Bash limit.

**Pattern:** a fixed time budget sized for an idle machine, and a gate output that drops the
reason it already computed.
