---
title: "Kernel: ground the ideas route in evidence and outside practice before generating options"
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
  - options
  - later-stage
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel: ground the ideas route in evidence and outside practice before generating options

## Actor / Goal
In order to get ideas that rest on something, we need the ideas route to research the question (repository evidence and outside practice) before the host generates options, so that its proposals are not all ungrounded.

## Context
The ideas route sends a bare `OptionsRequestPayload(problem=goal)` with no grounding research, so every idea it returns is ungrounded (live regression pass, `feature/kernel-v01` at 3299cc3c). The decision path already grounds an unknown option set with a bounded research request (task context, existing patterns, prior decisions) and requires options to cite evidence. This is the user's trace-review finding 3: outside practice and evidence should come before option generation.

## Scope (no acceptance criteria by user decision; later stage)
- Before the ideas route asks for options, run the same bounded grounding research the decision path uses, and pass its evidence ids in the options request; ideas then cite them.
- Decide where outside practice (external practices category, host research) enters, bounded by the host-operation budget.
- Keep ideas presented as proposals, never decisions.

## Out of Scope
- The decision path (already grounded).
- Approval of ideas.

## Comments
