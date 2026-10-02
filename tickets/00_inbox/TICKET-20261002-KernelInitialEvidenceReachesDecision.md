---
title: "Kernel: caller-supplied initial_evidence reaches the decision instead of being silently dropped"
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
  - evidence
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: caller-supplied initial_evidence reaches the decision instead of being silently dropped

## Actor / Goal
In order that evidence a caller hands the kernel is actually weighed, we need the root decision to
include `TaskInput.initial_evidence` in its evidence set, so that context pulled in by a human or
a reviewer counts in Jev's assessment.

## Context
- **Live reproduction (2026-10-02, run `run-a714fc5394304da8`):**
  - The task carried 11 `initial_evidence` items: ADR-065 sections, the ADR-062 projector code
    from an unmerged branch, criterion-id collisions, precedent criteria, and a SKOS excerpt.
  - None of their ids appears in any synthesis input, assessment result or report of that run.
  - The run still completed a ranking with no warning.
- **The workaround proves the path:** run `run-3bba494c7c9b48ce` used the same input, with the 11
  ids also listed in `input_payload.evidence_ids`. They were cited 33 times in its assessments, and
  option f's Neo4j-projection score moved from 0.54 to 0.34.
- **Cause:** the two halves don't meet.
  - Intake (`kernel/scheduler/nodes_lifecycle.py` `intake`) converts the items and puts their ids
    in `Request.context_refs` and `Task.evidence_refs`.
  - The decision's `_payload_inputs` (`kernel/capabilities/decision/loading.py:55-72`) uses only
    `DecisionRequestPayload.evidence_ids` plus the continuation's ids, and a goal-only request
    starts from `[]`. So `context_refs` never reach the decision.
- **The docs promise otherwise:** `docs/architecture/diagrams/c3-017-decision-kernel-context-jev.md`
  ("Decision Jev calls") lists `TaskInput.initial_evidence` among the evidence the decision
  resolves.
- **Related:** `TICKET-20261002-KernelInconclusiveRankingReview.md`. Its context requests depend on
  supplied evidence actually being used.

## Scope (no acceptance criteria by user decision)
- The root decision merges the request's `context_refs`, i.e. the initial evidence, into its
  evidence ids for both goal and decision-request payloads. Order and dedup follow the existing
  merge. Child requests keep today's behaviour unless the parent passes refs.
- If a caller-listed evidence id cannot be resolved, the run gets a limitation (as
  `missing_evidence_ids` does today), never silence.
- Tests:
  - goal-only and decision-request inputs with `initial_evidence` and no `evidence_ids` both reach
    the assess batch and are cited;
  - with no `initial_evidence`, behaviour is unchanged.

## Out of Scope
- Revision stamping of caller evidence (the "decision basis ... has no recorded revision"
  limitation): a follow-up if needed.

## Comments

## Implementation Tasks
### test-writer
- [ ] The two reach-the-assessment tests and the unchanged-behaviour test.
### python-coder
- [ ] Merge `context_refs` in `_payload_inputs`, plus a limitation for unresolved ids.
- [ ] Check that c3-017 still matches.

## Risk & Safety
- Touches money? No; Jev input grows by the supplied excerpts, within existing payload limits.
- Touches data? No; run artifacts only.
- Reversibility? Fully reversible.
