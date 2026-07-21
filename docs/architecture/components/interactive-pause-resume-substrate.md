---
title: "Interactive Pause/Resume Substrate — Container Overview"
description: "Container-level overview of the ADR-024 interactive pause/resume substrate inside the build orchestration workflow engine: the inline resolveGate()/pauseAtGate() helpers, the agent-mediated durable pending-question store under .leafcutter/paused_runs/, and the run lifecycle and pause->ask->answer->resume interaction documented by its two L3 child diagrams."
type: reference
status: active
flight_level: L2-Container
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
children:
  - docs/architecture/diagrams/c3-001-interactive-pause-resume-run-lifecycle.md
  - docs/architecture/diagrams/c3-002-interactive-pause-resume-sequence.md
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/adrs/ADR-024-interactive-pause-resume.md
  - docs/architecture/diagrams/c3-001-interactive-pause-resume-run-lifecycle.md
  - docs/architecture/diagrams/c3-002-interactive-pause-resume-sequence.md
related_code:
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/finalize-feature.js
related_adrs:
  - ADR-024
tags:
  - pause-resume
  - interactive-gate
  - resolveGate
  - workflow-engine
  - agent-mediated-io
---

# Interactive Pause/Resume Substrate — Container Overview

The **Interactive Pause/Resume Substrate** is the ADR-024 mechanism inside the
[Build Orchestration](build-orchestration.md) workflow engine that stops
interactive gates from silently cancelling a run when no human is reachable.
Instead of resolving a headless gate to a hardcoded `cancel`/`defer` default and
exiting with `status: ok`, a gate now **pauses**: it terminates the run cleanly,
persists a durable, run-keyed pending-question record, and returns the distinct
status `paused_awaiting_input`. A later re-invocation **resumes** past the gate.

The substrate is implemented as inline helpers — `resolveGate()`,
`pauseAtGate()`, `validateAnswerShape()`, `applyAnswerByType()` — in the engine
files that own interactive gates: `templates/workflows-js/plan-feature.js` and
`templates/workflows-js/finalize-feature.js` (`build-feature.js` has no gates).
E2 workflow bodies cannot import local modules, so the helper is duplicated
inline in each file and kept in sync (ADR-024 Rule 3).

This container groups the mechanism into two component-level (L3) child diagrams:

| View | Child diagram | What it shows |
|---|---|---|
| Run lifecycle (states) | [Interactive Pause/Resume — Run Lifecycle State Diagram](../diagrams/c3-001-interactive-pause-resume-run-lifecycle.md) | The states `running`, `paused_awaiting_input`, `resumed`, `cancelled`, `completed` and the `resolveGate` resume outcomes `nothing_to_resume` and `unresumable_stale`, making clear that `paused_awaiting_input` and `cancelled` are distinct and only `paused_awaiting_input` is resume-eligible. |
| Pause → ask → answer → resume (messages) | [Interactive Pause/Resume — Pause, Ask, Answer, Resume Sequence](../diagrams/c3-002-interactive-pause-resume-sequence.md) | The interaction between the workflow engine, the agent-mediated persist/read agent, the durable store, and the answerer — including the wrong-shape re-prompt loop and cross-process resume via `resumeFromRunId`. |

## Key invariants

1. **Distinct `paused_awaiting_input` status.** A paused run never returns `ok`
   or `cancelled`; only `paused_awaiting_input` is resume-eligible.
2. **Answer-before-live-gate (ADR-024 Rule 4).** `resolveGate()` consults
   `args.resume_answer` *before* calling the live gate function, so on resume the
   harness replay does not re-apply the headless default and re-cancel.
3. **Agent-mediated durability.** The workflow body performs no filesystem I/O;
   the record under `.leafcutter/paused_runs/<run_id>.json` is written and read
   only via `agent()` dispatches (`pause-persist`, `read-pause-record`).
4. **Guarded resume outcomes.** A missing record resolves to `nothing_to_resume`
   (a no-op), a stale record to `unresumable_stale` (rejected with a reason,
   committed stages kept), and a wrong-shape answer keeps the run paused.

## Cross-References

- [Build Orchestration — Epic & Ticket Dispatch Sequencing](build-orchestration.md) — the component that owns the engine workflow files carrying `resolveGate()`.
- [ADR-024 — Interactive Gates Pause and Persist Instead of Cancelling When Headless](../adrs/ADR-024-interactive-pause-resume.md) — the design of record.
