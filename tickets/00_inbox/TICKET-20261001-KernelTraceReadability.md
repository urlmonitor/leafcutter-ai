---
title: "Kernel: make the Langfuse trace readable"
status: todo
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - observability
  - later-stage
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel: make the Langfuse trace readable

## Actor / Goal
In order to read a run from its trace alone, we need the kernel telemetry to show structure, timing, paths and evidence ids, so that the 503 observations of one run can be followed. The orchestrator schedules it as wave 3.

## Context
Finding 7: most observations are LangGraph plumbing; Jev generations show 0.00 s; retriever and rerank outputs carry counts and scores without paths or evidence ids; `root_task_id` is "pending" in the first segment; the OTel service name is `unknown_service:python.exe`; interrupts appear as Python repr strings.

Source: `docs/analysis/2026-10-01-kernel-trace-review-decision-records-run.md` (trace review of live run run-5d246775f5e54f11).

## Scope (no acceptance criteria by user decision; later stage)
- Drop or nest the LangGraph callback spans under the kernel spans that ran them.
- Give Jev generations real start and end times (not 0.00 s; `latency_ms` is already recorded).
- Put paths and evidence ids into retriever and rerank outputs (the ADR-056 analytics job needs that link).
- Backfill `root_task_id` in the first segment.
- Set the OTel `service.name`.
- Show interrupts as structured values, not repr strings.

## Out of Scope
- Host token and cost reporting (a separate gap: Claude usage is `null`).

## Comments
