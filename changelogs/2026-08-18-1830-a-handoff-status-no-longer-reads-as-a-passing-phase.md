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
`agent()` dispatch sequence — that `test-writer` is dispatched twice in each driver, and
that an unparseable target produces zero `pr-reviewer` dispatches. It does not grep the
JS source; a grep-only test cannot tell a wired handler from a defined-and-ignored one.

Red baseline before the fix: 3 failed. After: 3 passed, with 411 passing across
`unit_tests/workflows/` and no regressions.

## Not covered

The adjacent `cross_agent` classification still resolves by *skipping* the failing phase
rather than routing back to the agent that must do the work, and those skips are reported
inside an otherwise-successful summary. That is a separate defect and is untouched here.
