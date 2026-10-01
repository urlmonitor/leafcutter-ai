---
title: "Kernel: an applicable precedent no longer skips option-grounding research"
status: todo
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: normal
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

# Kernel: an applicable precedent no longer skips option-grounding research

## Actor / Goal
In order to let the host propose repository-grounded options, we need the grounding research to run even when the decision already holds a precedent as evidence.

## Context
- **Live reproduction:** in run `run-12741427fdf8450d`, precedent `dec-ef8ddcb79d668a67` (how to file decision records) was judged applicable to "what to build next" and became `prior_decisions` evidence `ev-f657e2f7b406cf8f`. The grounding rule ("evidence the caller already supplied skips the research") then skipped `ground:options`, so the options packet offered only the precedent to cite and the host could propose no repository-grounded option.
- **Cause:** `needs_grounding` and `grounding_gap` tested `work.evidence`, which includes evidence the kernel added from the memory port.
- **Branch:** decision-store only (precedent lookup is not on main).

## Scope (no acceptance criteria by user decision)
- `Working.grounding_evidence` excludes kernel-added precedent evidence (`is_precedent_evidence`, by source id `memory.decisions`); both grounding checks use it. Evidence a caller really supplied keeps skipping the research.
- The precedent evidence stays beside the researched evidence in the options packet.
- Test: tests/kernel/memory/test_precedent_grounding.py (precedent-only decision researches; the options packet cites both kinds).

## Comments

### 2026-10-01 12:00 — python-coder (status: ok)
feedback-id: fb_2026-10-01_98ac9716
Fixed in the decision-store worktree (uncommitted).
