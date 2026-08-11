---
title: "Build Orchestration — Epic & Ticket Dispatch Sequencing"
description: "Build orchestration: pre-dispatch sequencing gates, dependency-cycle detection, parallelism limits, file-conflict isolation, and pre-drive reachability checks."
flight_level: L3-Component
status: active
type: reference
created: 2026-07-10
last_updated: 2026-07-21
components:
  - build_orchestration
children:
  - docs/architecture/diagrams/c3-fast-lane-build-loop-sequence.md
---

# Build Orchestration

## Overview

Build Orchestration governs how epics and tickets are dispatched to supervisors and phase agents. It sequences work before dispatch: building the dependency graph from `depends_on` (logical) and `files_touched` (physical) edges, detecting dependency cycles, enforcing parallelism limits, isolating file-conflicting tickets into serial batches, and running pre-drive reachability checks (e.g. telemetry sink writability) before a drive begins.

## Responsibilities

- Compute the maximal next-ready ticket batch that is parallel-safe under both logical and physical edges
- Detect and surface dependency cycles before dispatch
- Enforce parallelism limits and file-conflict isolation across concurrent supervisors
- Run pre-drive reachability / precondition checks before starting an epic drive

## Entry Points

- `templates/workflows-js/build-epic.js` — epic dispatch workflow

## Integration

Build Orchestration sits above the supervisor spawn topology: it decides *what* to dispatch and in *what order*, then hands each ready ticket to a `ticket-supervisor`. See `docs/architecture/components/build-epic-workflow-dispatch.md` and `docs/architecture/components/supervisor-spawn-topology.md` for the dispatch mechanics it drives.

## Interactive Pause/Resume Diagrams

The workflow engine files owned by this component (`templates/workflows-js/plan-feature.js`
and `templates/workflows-js/finalize-feature.js`) implement the ADR-024 interactive
pause/resume substrate via the inline `resolveGate()` helper. When an interactive gate is
reached headless, the run pauses and persists a durable, run-keyed pending-question record
instead of silently cancelling; a later re-invocation resumes past the gate. The
[Interactive Pause/Resume Substrate — Container Overview](interactive-pause-resume-substrate.md)
is the L2 container for this mechanism, and the two diagrams below document it:

- [Interactive Pause/Resume — Run Lifecycle State Diagram](../diagrams/c3-001-interactive-pause-resume-run-lifecycle.md) — the run lifecycle states (`running`, `paused_awaiting_input`, `resumed`, `cancelled`, `completed`) and the `resolveGate` resume outcomes (`nothing_to_resume`, `unresumable_stale`), showing that `paused_awaiting_input` and `cancelled` are distinct and only `paused_awaiting_input` is resume-eligible.
- [Interactive Pause/Resume — Pause, Ask, Answer, Resume Sequence](../diagrams/c3-002-interactive-pause-resume-sequence.md) — the message-level interaction between the workflow engine, the agent-mediated persist/read agent, the durable store, and the answerer, including the wrong-shape re-prompt loop and cross-process resume via `resumeFromRunId`.
- [ADR-024 — Interactive Gates Pause and Persist Instead of Cancelling When Headless](../adrs/ADR-024-interactive-pause-resume.md) — the design of record.

## Phantom-Done Prevention — Real-Effect / Real-Intent Verification

The drive and verification-phase routing this component owns is where the BP-1100f
phantom-done-prevention gates plug in. Those gates prove that a durable change actually
happened by its **real effect** and **stated intent**, rather than by **dispatch
topology** (the presence, labels, or counts of dispatched helpers a test mock controls) —
the BO-2300 failure mode in which a feature was signed off twice while its real behaviour
was absent. The sequence diagram below places each of the five gates on the timeline
relative to dispatch and to the done state:

- [Phantom-Done Prevention — Proving a Durable Change by Real Effect and Intent](../diagrams/c3-003-phantom-done-real-effect-intent-verification.md) — the end-to-end BP-1100f verification flow: pre-dispatch intent-vs-surface consistency (BP-1100f-3), instruction-carrying dispatch review (BP-1100f-1), the harness-level instruction-less-dispatch contract violation (BP-1100f-4), the real-artifact test-evidence requirement (BP-1100f-2), and the automatic observable-side-effect smoke check that gates the done state (BP-1100f-5).

## Documentation Coverage — Runtime Phase Flow

On doc-required (v2) tickets, this component sequences two documentation phases into the
drive: `documentation-expert` (priority 10) authors the docs after the coder and test
phases, and `documentation-verifier` (priority 11.9) is the last gate before `commit` — it
asserts the required docs against the ticket's `## Agent Contracts` → `### documentation-expert`
brief and fails closed (blocking the commit) when a required doc is missing or placeholder.

- [Documentation Coverage — Runtime Phase Flow Sequence](../diagrams/c3-004-documentation-coverage-phase-flow-sequence.md) — the ordered `coder → test-runner → documentation-expert → documentation-verifier → commit` flow, including the blocker path where the verifier prevents the commit when required docs are absent or placeholder.
