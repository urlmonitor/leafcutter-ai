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
