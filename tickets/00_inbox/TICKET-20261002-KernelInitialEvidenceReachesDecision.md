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
- **Root cause (confirmed 2026-10-02 by reproduction with Jev mocked and by decoding the failing
  run's checkpoint): never wired, not a regression.**
  - Intake (`nodes_lifecycle.py:103-121`) puts the ids in `Request.context_refs`.
  - Routing copies them into every `CapabilityInvocation.context_refs` (`nodes_route.py:97`), and
    `ExecutionContext.evidence_lookup` can resolve them (`nodes_execute.py:78-83`).
  - **Loss point:** `kernel/capabilities/decision/loading.py:70`. `_payload_inputs` merges only the
    payload `evidence_ids` and the continuation's ids, never `invocation.context_refs`. A goal-only
    request starts from `[]` (L63-64).
  - Children inherit nothing (`merge.py:205-206`), so research, options and synthesis requests
    carry no caller ids, and `assess` (`assess.py:86-90`) quotes only `work.evidence`.
  - The decision load (3a16a121) and the intake that fills `context_refs` (b37c03fe) landed 26 s
    apart on 2026-09-30, and no test ever joined them.
- **Why the tests missed it:**
  - `tests/kernel/scheduler/test_lifecycle.py:83-97` stops at intake.
  - `tests/kernel/integration/test_wiring.py:179-191` passes for the wrong reason: the fixture
    repo holds the same ADR, so research re-finds a copy.
  - `scenario_support.py:189-196` and `tests/kernel/live/eval_runner.py:62-66` hand-wire the ids
    into `payload.evidence_ids`, which hides the gap.
  - The c3-017 row was wrong from its first version (5a7b9761). `docs/how-to/run-the-decision-kernel.md:164`
    tells callers to use `initial_evidence` and never mentions `evidence_ids`.
- **The failure is silent, and the output misleads:**
  - Nobody checks that supplied ids were used. The envelope's `evidence_ids` lists them anyway
    (`service_envelope.py:124`).
  - The run then reports `prior_decisions` as missing although 11 such items were supplied.
- **Other silent drops found:**
  - Unresolvable `decision_request.v1.constraint_ids` are dropped with no limitation (`assess.py:88`).
  - Host and human packets filter out unknown cited ids silently (`packets.py:64-65`).
  - Native research ignores supplied evidence: see
    `TICKET-20261002-KernelResearchUsesSuppliedEvidence.md`.
- **The docs promise otherwise:** `docs/architecture/diagrams/c3-017-decision-kernel-context-jev.md`
  ("Decision Jev calls") lists `TaskInput.initial_evidence` among the evidence the decision
  resolves.
- **Related:** `TICKET-20261002-KernelInconclusiveRankingReview.md`. Its context requests depend on
  supplied evidence actually being used.

## Scope (no acceptance criteria by user decision)
- **The fix belongs in the decision capability**, because the scheduler already delivers the
  refs. At `loading.py:70`, merge
  `[*payload evidence_ids, *invocation.context_refs, *cont.evidence_ids]` with dedup. This covers
  goal and decision requests, first runs and resumes. The fingerprint is unchanged, since
  `context_refs` is already hashed (`nodes_route.py:90`).
- **Unresolvable ids** (caller evidence or `constraint_ids`) each give a limitation, never silence.
- **Side effects to verify in tests:**
  - caller evidence may make grounding research unnecessary (`basis.py:49-52`);
  - `task_context` caller items count as decision basis (`state.py:181-183`);
  - the options request's `evidence_cap` (12) is shared, with caller ids first;
  - each caller `prior_decisions` item without a revision gets a limitation.
- **Optional guard:** a limitation when `task.evidence_refs` were supplied but none entered the
  root's working evidence.
- **Tests:**
  - unit: `load_working` with `invocation(context_refs=[id])` gives `work.evidence_ids == [id]`
    for goal and decision requests, with dedup, and an unresolvable ref gives a limitation;
  - integration: rework `test_wiring.py:179-191` so it asserts that the caller's id (not a
    re-retrieved copy) is in the first `decision.assess` batch and in `decision.evidence_ids`;
  - integration: in a goal-only run, `initial_evidence` reaches the options request and the
    `host.generate_options` packet;
  - scenario: a `known_basis` variant with no payload `evidence_ids`.
- Fix `docs/how-to/run-the-decision-kernel.md:164` and the c3-017 row if anything still differs.

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
