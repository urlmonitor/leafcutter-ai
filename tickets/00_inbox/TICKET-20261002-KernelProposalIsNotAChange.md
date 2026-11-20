---
title: "Kernel: a feature proposal is not a change request — intake offers 'decide how' instead of declining"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - intake
  - routing
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: a feature proposal is not a change request — intake offers 'decide how' instead of declining

## Actor / Goal
In order that ideas and feature proposals typed into `/leafcutter` get evaluated instead of
declined, we need intake to tell "the user proposes something we should build and asks to evaluate
it" apart from "the user asks the kernel to edit the repository now", so that a proposal reaches
the decision or ideas root.

## Context
- **Live reproduction (2026-10-02, run `run-b2262865f6c74bc7`, Langfuse trace
  `d8bd33ecc1c76ac71d9e6c2033991361`):** the goal "For the kernel we often use similar decision
  basis and we should also reuse them ... we can should put them into a new file type (needs
  evaluation), and then also into neo4j ..." was classified `change` (P 0.88; ideas 0.06,
  decision 0.05; confidence 0.86) and ended `blocked` with `out_of_scope_write`. The goal says
  outright that the file type "needs evaluation".
- **Cause:** `kernel/intent/classify.py` `_CRITERIA[CHANGE]` reads "The goal asks to implement,
  edit or modify something". Every "we should build X" proposal matches it. A `change` result is a
  terminal decline (`kernel/intent/roots.py` `decline_for`), although the decline text itself says
  the kernel can "decide what to implement".
- The user rule since 2026-10-01 is that ideas go through the kernel first, so this misroute hits
  every idea phrased as a proposal.
- Builds on `TICKET-20261001-KernelIntakeIntent.md` (the answer-kind classifier).

## Scope (no acceptance criteria by user decision)
- Narrow the `change` criterion to "asks the kernel itself to carry out an edit now". Add a
  criterion text (or kind) for proposals: "proposes something to build or change and wants it
  evaluated, designed or planned". It maps to the decision contract. Bump `INTENT_TEMPLATE_REV`.
- A `change` result is no longer a dead end when `decision` or `ideas` is a plausible reading.
  The human gets one plain clarification with choices "decide how to do this" (decision), "give me
  ideas" (ideas) and "I wanted an edit" (decline as today). The existing at-most-one-follow-up
  rule applies.
- Regression fixtures (Jev mocked): this goal routes to decision or to the clarification, never
  straight to `out_of_scope_write`. "Implement a critical acceptance criterion." still declines.
- Update `docs/how-to/run-the-decision-kernel.md` (what intake does with proposals).

## Out of Scope
- Splitting a multi-part proposal into bounded decisions:
  `TICKET-20261002-KernelDecomposeMultiPartGoal.md`.
- Write capabilities (the kernel stays read-only).

## Comments

## Implementation Tasks
### test-writer
- [ ] Fixtures for the proposal goal, the clarification path and the unchanged write decline.
### python-coder
- [ ] Criterion texts and template revision in `kernel/intent/classify.py`; the clarification in
  place of the terminal decline in `kernel/intent/roots.py` / `kernel/intent/step.py`.
- [ ] How-to update.

## Risk & Safety
- Touches money? No.
- Touches data? No; run artifacts only.
- Reversibility? Fully reversible; an explicit `requested_output_schema` bypasses intake as today.
