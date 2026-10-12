---
title: "Kernel V0.1 fix C: count Jev provider calls consistently and report telemetry export failures"
status: in_progress
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - observability
  - budgets
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel V0.1 fix C: count Jev provider calls consistently and report telemetry export failures

## Actor / Goal
In order to trust the budget, the usage rows and the trace of a run, we need every one of
them to count the same thing (provider calls), and we need an envelope that says
`observability: degraded` when telemetry was not delivered.

## Context
Live run `run-5d246775f5e54f11` (trace `954274b26bf886b3d7658e0345453cbb`, envelopes
`r5_resume3.json` to `r5_resume5.json`, run data under `runs5/`, all in the session scratchpad
`explore/` folder) showed two defects:

1. Jev call counts disagreed: the envelope had `jev_calls: 18`, the trace had 18 Jev
   generations, but the usage row said `calls: 20`. A decision assessment of 33 questions with
   `max_questions_per_call: 20` is sent as two provider calls by the adapter, but the budget
   reserved one call, the tracer emitted one generation and the usage row summed attempts.
2. A resume printed a failed OTLP export ("Read timed out") on stderr while the envelope
   reported `observability: ok`. The OpenTelemetry batch processor ignores the exporter result,
   and `flush()` returns True regardless, so the tracer never learned about the failure.

## Decision
- A Jev call is one provider request for one chunk of at most `max_questions_per_call`
  questions. The retries of a chunk are not separate calls (they are bounded by `max_retries`
  and reported as `attempts` in the trace metadata).
- The adapter emits one `jev.<purpose>` generation per provider call, carries `calls=1` in its
  usage, and reserves every chunk after the first from the caller's budget share before sending
  it. A refused reservation stops the assessment (`JevBudgetExhausted`, a `JevUnavailable`).
- Export failures are detected by an exporter wrapper handed to Langfuse's documented
  `span_exporter` argument; it marks the tracer degraded with a reason and spools the spans.

## Scope
Edits stay in `kernel/providers`, `kernel/observability`, the status plumbing of
`kernel/service*.py`, and the worker budget binding in `kernel/scheduler/nodes_execute.py`.
Decision, retrieval and research capabilities and the payload contracts are not touched.

## Test Requirements
Offline regression tests (each fails without the fix): chunked assessment counted equally by
budget, envelope usage, usage rows and tracer; a budget cap hit mid-chunk; an exporter failure
leads to degraded status and a spool entry; a successful export stays ok.

## Comments

### 2026-10-01 12:00 — commit (status: ok)
feedback-id: fb_2026-10-01_a616193b
Auto-authorized commit gate: subject "fix(kernel): count Jev provider calls consistently across budget, usage and trace and report failed telemetry export as degraded (#KernelV01/C)"; staged files: kernel/observability/export_monitor.py kernel/observability/langfuse_tracer.py kernel/providers/jev.py kernel/providers/jev_budget.py kernel/providers/jev_errors.py kernel/providers/jev_trace.py kernel/scheduler/nodes_execute.py kernel/service.py kernel/service_envelope.py kernel/service_session.py tests/kernel/observability/test_export_failure.py tests/kernel/providers/test_jev_adapter.py tests/kernel/scheduler/test_jev_call_accounting.py tickets/00_inbox/TICKET-20261001-KernelJevAccountingTracing.md 
