---
title: "Kernel: calibrate the resolution gate from recorded outcomes"
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

# Kernel: calibrate the resolution gate from recorded outcomes

## Actor / Goal
In order to let a decision reach a recommendation when the evidence is as good as it realistically gets, we need the resolution gate calibrated (per-criterion bars, required versus nice-to-have criteria) from recorded outcomes, so that six required criteria at 0.8 are not practically unreachable.

## Context
Finding 2: the best option passed 2 of 6 required criteria; Jev scores cluster between 0.5 and 0.7, so with both bars at 0.8 the gate can only open if scores move far above where they sit. This is the calibration problem from live QA, now with numbers.

Source: `docs/analysis/2026-10-01-kernel-trace-review-decision-records-run.md` (trace review of live run run-5d246775f5e54f11).

## Scope (no acceptance criteria by user decision; later stage)
- Per-criterion bars or a required / nice-to-have split, chosen from recorded outcomes rather than guessed.
- Keep the rule that an approval and a human choice stay the only ways to resolve a design decision.

## Out of Scope
- Changing how Jev is asked (separate concern).

## Comments
