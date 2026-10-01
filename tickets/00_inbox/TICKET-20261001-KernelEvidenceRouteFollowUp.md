---
title: "Kernel: let the evidence route follow up on the unknowns a synthesis names"
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
  - research
  - later-stage
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel: let the evidence route follow up on the unknowns a synthesis names

## Actor / Goal
In order to answer an evidence question as well as the budget allows, we need the evidence route to search for what its own synthesis said is still unknown, instead of stopping after the synthesis while most of the Jev budget is unused.

## Context
A live regression pass of five goals (kernel `feature/kernel-v01` at 3299cc3c, goal "How does the Leafcutter kernel store decisions today, and do later runs learn from earlier decisions?") showed the evidence route stop after synthesis even though the synthesis named unknowns and the run had used 12 of 40 Jev calls. Unknowns only become targeted needs (`need.gap.N`) on the decision path, where the decision keeps them as gaps and passes them in the next research request. The evidence route has no such loop.

## Scope (no acceptance criteria by user decision; later stage)
- After a synthesis on the evidence route, turn the unknowns into targeted needs (the same bounded `research.max_targeted_needs` mechanism the decision path uses) and run one more research round when the budget affords it beside the reserve rules of the budget-aware decision work.
- Stop after a configured number of rounds, and say in the report which unknowns stayed open and why the route stopped.

## Out of Scope
- The decision path (already follows up on gaps).
- Changing how needs are covered or ranked.

## Comments
