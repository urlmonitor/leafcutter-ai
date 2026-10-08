---
title: "Kernel: split compound goals into sub-decisions"
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
  - decision
  - later-stage
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel: split compound goals into sub-decisions

## Actor / Goal
In order to get decisions that are real alternatives, we need the decision capability to split a goal that bundles several questions into sub-decisions, so that a human is not asked to pick one of N composite specifications.

## Context
Finding 5 (shape): the goal bundled five sub-decisions (fields, filters, layout, naming, approval and corrections) into one "pick one of N"; the human added a composite spec rather than an alternative.

Source: `docs/analysis/2026-10-01-kernel-trace-review-decision-records-run.md` (trace review of live run run-5d246775f5e54f11).

## Scope (no acceptance criteria by user decision; later stage)
- Detect a compound goal and propose sub-decisions, each with its own options and criteria, subject to human approval.
- Keep one decision record per sub-decision and link them to the goal.

## Out of Scope
- Calibrating the gate (see the gate calibration ticket).

## Comments
