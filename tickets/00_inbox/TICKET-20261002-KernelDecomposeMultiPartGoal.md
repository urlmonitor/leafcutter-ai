---
title: "Kernel: split a multi-part design goal into bounded decisions instead of blocking"
status: deferred
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
  - superseded
last_updated: 2026-10-05
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: split a multi-part design goal into bounded decisions instead of blocking

> **Superseded on 2026-10-05: do not build from this ticket.** The DK-400 AC tree
> (`docs/acceptance-criteria/decision-kernel/DK-400-split-compound-requests/`, merged in PR #1012)
> replaces it. It covers this ticket's routing-failure case (`jev_none` or `ambiguous`,
> run-40d2159630bb48bd) and the rest of its scope:
> - the `host.decompose_goal` proposal with verbatim quotes (DK-400c);
> - the human split gate (DK-400d);
> - child runs in dependency order (DK-400e);
> - the report (DK-400f);
> - the bounds and the ADR (ADR-067, before DK-400c-1).
>
> Two rules differ from this ticket, as the user decided at the DK-400 gates:
> - a rejected split of an `ambiguous` request falls back to today's clarification question, and
>   only `jev_none` ends `blocked`;
> - bundled requests the kernel would accept as one are split too.
>
> Build from the ACs with `/build-ac`. The ticket is retired with status `deferred` and moves to
> `tickets/99_rejected/` on main (move-on-main-only).

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
- **Overlap:** `TICKET-20261001-KernelCompoundGoalSplit.md` (2026-10-01) asks for the same split
  at decision level (one record per sub-decision, linked to the goal). This ticket adds the
  routing-level fallback.
  - On 2026-10-02 the user asked for product truth plus PO/BA/IT PO ACs for splitting goals
    "(and other things)", authored on branch `ac-authoring/split-compound-goals`.
  - Once those ACs merge, build from them with `/build-ac`, and retire both tickets as
    superseded.
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
