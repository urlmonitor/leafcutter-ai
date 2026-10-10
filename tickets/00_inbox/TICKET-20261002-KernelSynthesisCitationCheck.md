---
title: "Kernel: a synthesis finding with no citation is rejected, and 'known' means the items handed to the synthesis"
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
  - grounding
  - acceptance-criteria
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# Kernel: a synthesis finding with no citation is rejected, and 'known' means the items handed to the synthesis

## Actor / Goal
In order for every finding in a decision to rest on evidence that was actually retrieved for that synthesis, we need the synthesis step to reject a finding that cites nothing, and to count a citation as known only when it names an item handed to that synthesis.

## Context
- **Found by:** the it-po verification pass for `DK-600a-3` (status `partly_built`), ticket `TICKET-20261002-DecisionLifecycleACs`.
- **Built differently from the criteria:**
  - `convert_findings` removes an unknown citation from a finding and keeps the finding, with a limitation.
  - A finding left with no citation at all is still accepted.
  - "Known" means any evidence id in the run, not only the items handed to the synthesis.
  - `findings.v1` has no semantic citation check: see `kernel/contracts/schema_catalog.py#semantic_violations`.
- **AC:** `DK-600a-3` ("Findings cite only the retrieved evidence, and options you named stay yours"). Its propose half is built and tested; only the synthesize half is open.

## Scope (no ACs, by user decision)
- A finding left with no citation after unknown ones are removed is rejected, not accepted.
- "Known" is limited to the evidence items handed to that synthesis.
- Add the semantic citation check to `findings.v1` in `semantic_violations`.
- Tests for each of the three, in `tests/kernel/`.
- When done, mark `DK-600a-3` through `scripts/ac_store/mark_ac_done.py`, with `# covers: DK-600a-3` on the new tests.

## Out of Scope
- The propose half of `DK-600a-3` (already built and tested).

## Comments
