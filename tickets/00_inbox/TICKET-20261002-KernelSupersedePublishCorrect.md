---
title: "Kernel: the publish instruction carries --correct <old id> when a run supersedes a precedent, and 'same option' compares ids"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - publishing
  - acceptance-criteria
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# Kernel: the publish instruction carries --correct <old id> when a run supersedes a precedent, and 'same option' compares ids

## Actor / Goal
In order for a decision that deliberately replaces an earlier one to be published as a correction without the person remembering a flag, we need the staged record's publish instruction to name the record it supersedes.

## Context
- **Found by:** the it-po verification pass for `DK-100e-3-i` (status `partly_built`), ticket `TICKET-20261002-DecisionLifecycleACs`.
- **Not built:**
  - The run's publish instruction never carries `--correct`. The completed-run limitation is always `python -m kernel decisions publish --run-id <id>`. A person adds `--correct <old id>` by hand (file-and-reuse how-to, Step 6).
  - "Same option" is decided by comparing option **titles**, case-insensitively, not option ids.
  - Not tested end to end: decide anew, a different final choice, and a staged record with `supersedes`. The rule is unit-tested in `final_links` only.
- **AC:** `DK-100e-3-i` ("Deciding anew keeps the precedent as evidence and supersedes it only if you choose differently"), the L3 under `DK-100e-3`.

## Scope (no ACs, by user decision)
- When the staged record has `supersedes`, the publish instruction names the old id, as `--correct <old id>`.
- "Same option" is compared by option id, with the title comparison as the fallback only when ids are unavailable.
- An end-to-end test: decide anew, choose differently, and check the staged record's `supersedes` and the instruction text. Another: choose the same option, and check no `supersedes` and no `--correct`.
- When done, mark `DK-100e-3-i` through `scripts/ac_store/mark_ac_done.py`, with `# covers: DK-100e-3-i` on the new tests.

## Out of Scope
- Gated direct publishing (`TICKET-20261002-KernelGatedDirectPublish`).

## Comments
