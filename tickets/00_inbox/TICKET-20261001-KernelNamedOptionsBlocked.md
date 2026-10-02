---
title: "Kernel: a goal that names its options no longer ends blocked"
status: todo
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
last_updated: 2026-10-01
agents:
  python-coder: signed_off
  commit: needed
---

# Kernel: a goal that names its options no longer ends blocked

## Actor / Goal
In order to decide between options the caller already named in the goal, we need the kernel to accept its own verified `named_options` instead of refusing them.

## Context
- **Live reproduction:** run `run-12741427fdf8450d`, goal "Decide what to build next ... Options: run trace analyzers ...; file human decisions ...; have agents consult ...". The host returned the three options in `options` with `named_in_goal: true` (as the packet instructs) and did not set `named_options`. The run ended `blocked`: `work-...: semantic_invalid: named_options is set by the kernel only: return named options in options with named_in_goal true`.
- **Cause:** `host.generate_options` verifies the claims and builds its result with `named_options`. `kernel/scheduler/validation.py` then runs `validate_semantics` on every capability result, and `_options_violations` refused ANY non-empty `named_options`. A rule meant to stop a host from returning `named_options` was applied to the kernel's own converted output.
- **Reach:** the defect is on main (V0) and in PR #977, so every goal that names its options blocks there.
- **Why the tests missed it:** `tests/kernel/grounding/test_round5.py` tested the conversion (`convert_payload`) and the refusal (`semantic_violations` on a bare payload) separately. No test ran a goal with named options through result validation.

## Scope (no acceptance criteria by user decision)
- `SemanticContext.kernel_built` (default False). Result validation sets it; the host submission path (`kernel/interaction/submissions.py`) leaves it False, so the refusal applies to host submissions only. Every other host-facing rule (no pre-approved options or criteria) is unchanged.
- No other host-only semantic rule had the same layering problem.
- Tests: an end-to-end run (real service and graph, scripted Jev, fake host) whose goal names two options reaches the criteria-approval question; unit tests for both sides of the flag.

## Comments

### 2026-10-01 12:00 — python-coder (status: ok)
feedback-id: fb_2026-10-01_09f39537
Fixed in the decision-store worktree (uncommitted): flag on SemanticContext, set by result validation; tests in tests/kernel/grounding/test_named_options_end_to_end.py.
