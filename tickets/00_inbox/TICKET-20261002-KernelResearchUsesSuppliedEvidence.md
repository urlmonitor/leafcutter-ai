---
title: "Kernel: native research uses the evidence it is handed instead of ignoring it"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on:
  - TICKET-20261002-KernelInitialEvidenceReachesDecision.md
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - evidence
  - research
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: native research uses the evidence it is handed instead of ignoring it

## Actor / Goal
In order that research does not re-retrieve, or report as missing, what a caller or a parent
decision already supplied, we need native research to read the evidence ids it is handed. Its
need coverage then counts that evidence.

## Context
- The root-cause analysis of the dropped `initial_evidence` (see
  `TICKET-20261002-KernelInitialEvidenceReachesDecision.md`) found a second drop:
  `kernel/capabilities/research/executor.py:66-81` `parse_plan` reads neither
  `research_request.v1.existing_evidence_ids` (`kernel/contracts/payloads.py:106`) nor
  `invocation.context_refs`.
  - The `Plan` has no field for either.
  - Nothing in `kernel/capabilities/research` calls `ctx.evidence`.
- Research can also be the ROOT capability for evidence goals, so caller evidence is ignored
  there as well.
- Live effect, run `run-a714fc5394304da8`: the research child re-researched `prior_decisions`
  although 11 such items had been supplied.
  - With the fixture ADR removed, the run ends `partial` with "Missing evidence: prior_decisions"
    while the supplied item sits in state (reproduction C of the analysis).

## Scope (no acceptance criteria by user decision)
- `parse_plan` carries `existing_evidence_ids` and `context_refs`.
- Research resolves them through `ctx.evidence`, places them in its bundle, and lets them count
  toward need coverage under the same relevance and answer-judgement rules as retrieved evidence.
  Whether supplied evidence may satisfy a need without that judgement is a design call: put it to
  the decision kernel.
- Unresolvable ids give a limitation.
- Tests:
  - a supplied `prior_decisions` item satisfies its need without re-retrieval when it answers the
    question;
  - a root evidence goal with `initial_evidence` cites it;
  - unresolvable ids give a limitation.

## Out of Scope
- The decision-side merge (`TICKET-20261002-KernelInitialEvidenceReachesDecision.md`).

## Comments

## Implementation Tasks
### test-writer
- [ ] The three tests above.
### python-coder
- [ ] `Plan` fields, `parse_plan`, bundle and coverage changes, limitation.

## Risk & Safety
- Touches money? Saves retrieval calls; no new spend.
- Touches data? No; run artifacts only.
- Reversibility? Fully reversible.
