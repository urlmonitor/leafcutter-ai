---
title: "A handoff status no longer reads as a passing phase"
date: 2026-08-18
time: "18:30"
type: manual
components:
  - build_orchestration
  - build_pipeline
summary: >-
  Both ticket drivers now route `status: handoff` to the named agent instead of
  treating it as a completed phase and advancing.
---

## What changed

`handoff` was a declared value in the `PHASE_RESULT_SCHEMA` status enum of both
`build-feature.js` and `build-ticket.js`, and in neither file did anything read it.
`grep -c handoff` returned exactly 1 in each — the enum entry itself. The adjudication
branch tested only `blocker` and `failed`, so a `handoff` result fell through that guard
and reached the phase-completed path.

The effect was that the one status whose entire meaning is *"another agent must act
before I can proceed"* was indistinguishable from `status: ok`. The driver advanced to
the next phase in `phaseOrder` and the named agent was never re-dispatched.

Both drivers now handle it identically:

- A `handoff` naming a recognised agent re-dispatches that agent, then returns `blocked`
  so the remaining phases do not run until the handoff is resolved.
- A `handoff` whose `handoff_target` is missing or unrecognised fails closed — the driver
  refuses to guess a target and refuses to advance.

Separately, in the same pass, `build-ticket.js` gained a null/empty-status guard on its
per-phase result — immediately after `resultStatus` is computed and before the `handoff`
branch — mirroring one `build-feature.js` already had. Without it, a phase agent that dies
mid-run (`agent()` resolves to `null`) produced a falsy `resultStatus` that skipped both the
new `handoff` branch and the `blocker`/`failed` branch, so the dead phase was pushed onto
`completedPhases` as if it had succeeded and the loop advanced. This was a pre-existing gap
in `build-ticket.js`, not part of the original handoff defect above — it is closed here
because it sits in the same adjudication code the handoff fix touches.

## Why

Found live in `EPIC-BuildPipelinePhantomRemediation` ticket 07. `python-coder` returned
`status: handoff` asking `test-writer` to update a single stale assertion. `test-writer`
was never respawned and stayed at `needed`. The driver instead ran `pr-reviewer`,
`ac-validator`, `ac-fulfillment-gate` and `commit` — four agents that each independently
re-derived the same unfixed regression and blocked on it.

So a blocker was inverted into a pass, and four agent invocations were spent rediscovering
what the first agent had already diagnosed and correctly reported.

## Coverage

`unit_tests/workflows/test_bo_3000_handoff_routing.py` (AC `BO-3000`) drives the real
driver scripts through the Node-backed E2 stub harness and asserts on the observed
`agent()` dispatch sequence. It does not grep the JS source; a grep-only test cannot tell
a wired handler from a defined-and-ignored one. Five tests in total:

- `test-writer` is dispatched twice (its normal turn, then the handoff re-dispatch) in
  **each** driver — one test for `build-feature.js`, one for `build-ticket.js`.
- An unparseable `handoff_target` produces zero `pr-reviewer` dispatches — fail-closed
  coverage for **both** drivers (`build-feature.js` and `build-ticket.js`), not just one.
- A phase agent whose result is `null` or has no usable status produces zero
  `pr-reviewer` dispatches in `build-ticket.js` (covers the null/empty-status guard
  described above).

Red baseline before the handoff fix: 3 failed. After: 3 passed. The fail-closed
`build-ticket.js` mirror test and the null/empty-status guard test were added in a
follow-up pass; both were confirmed RED against the pre-fix `build-ticket.js` before the
fix and green after. 413 passing across `unit_tests/workflows/` and no regressions.

## Not covered

The adjacent `cross_agent` classification still resolves by *skipping* the failing phase
rather than routing back to the agent that must do the work, and those skips are reported
inside an otherwise-successful summary. That is a separate defect and is untouched here.
