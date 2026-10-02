---
title: "Kernel: split a multi-part design goal into bounded decisions instead of blocking"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: true
change_target: code
risk_surface: contract_boundary
tags:
  - decision-kernel
  - routing
  - host-operation
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: split a multi-part design goal into bounded decisions instead of blocking

## Actor / Goal
In order that a goal holding several design questions gets decided instead of blocked, we need the
kernel to propose a split into bounded decisions, have the human approve the split, and then run
those decisions in order, so that the user doesn't have to rephrase the goal by hand.

## Context
- **Live reproduction (2026-10-02, run `run-40d2159630bb48bd`, Langfuse trace
  `4c4c2b3f0b2742a1ad59afab8563a9c0`):** this is the goal from
  `TICKET-20261002-KernelProposalIsNotAChange.md`, sent with
  `requested_output_schema: leafcutter.decision_report.v1`. Routing ended `jev_none` and the run
  was `blocked` with an `unsupported` gap.
  - `decision` was the only eligible candidate. Its registry description in
    `config/capability_registry.json` says "for a bounded question".
  - The goal holds at least four decisions: the storage format for reusable criteria, the Neo4j
    projection, the clustering method, and the mining source (Langfuse vs published records).
- **What the human had to do instead:**
  - The orchestrator drafted three bounded sub-questions (format, clustering, mining source).
  - The user picked "format first", and run `run-aa2831ba7f0e4ec9` then proceeded normally.
  - That split was done by hand outside the kernel; this ticket brings it inside.
- ADR-053: generation (proposing sub-questions) is LLM work; the human approves; Jev only selects
  among supplied candidates. ADR-055: a new capability enters the registry only by a recorded
  decision.

## Scope (no acceptance criteria by user decision)
- **New host operation** (working name `host.decompose_goal`), on the pattern of
  `kernel/capabilities/host/generate_options.py`. It proposes 2–5 bounded sub-questions, each with:
  - the question text, using the caller's words where possible;
  - `depends_on` between sub-questions;
  - the span of the goal it covers.
- **Schemas** `leafcutter.goal_decomposition_request.v1` and `leafcutter.goal_decomposition.v1`.
  Conversion is total and drops sub-questions with no quote from the goal.
- **Routing:** when routing on a decision-shaped goal returns `jev_none` or `ambiguous`, the root
  runs the decomposition before declaring a gap.
- **Human gate:** the human approves, edits or picks a subset of the proposed split.
- **Child decisions:** each approved sub-question runs as a child decision in dependency order. An
  earlier child's result is evidence (precedent) for later ones. A bounded count goes in config.
- **Report:** lists each sub-decision with its outcome.
- **Registry descriptor and ADR:** dispatch `adr-author` directly with a pinned number.
- **Tests (Jev and the host mocked):**
  - this goal leads to a decomposition request, approval and child decisions;
  - a single bounded goal never triggers decomposition;
  - a rejected split ends `blocked` with a plain report.

## Out of Scope
- Intake classification of proposals: `TICKET-20261002-KernelProposalIsNotAChange.md`.
- Parallel child decisions; children run one after another.

## Comments

## Implementation Tasks
### test-writer
- [ ] Host-op unit tests (quote check, dependency order) and the decision-flow tests above.
### python-coder
- [ ] Host op, schemas, routing fallback, child dispatch, report section, registry entry, config.
- [ ] ADR (pinned number) and an "As built" note in the decision-kernel design docs.

## Risk & Safety
- Touches money? No; bounded by config (children and host-operation caps).
- Touches data? No; run artifacts only.
- Reversibility? Reversible; with the operation disabled in config the behaviour is today's.
