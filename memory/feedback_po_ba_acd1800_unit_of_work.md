# PO learnings — ACD-1800 (AC-as-unit-of-work / ticket-as-container) framing

Captured 2026-08-11 (product-owner, origin_agent: BrainCandy run) authoring a new
sibling L0 in ac-driven-dev refining the AC-driven build model. For BA (L2/L3
decomposition) and IT-PO (enrichment).

## Why a NEW L0 (ACD-1800), not more children under ACD-1600

ACD-1600 = "single source, always buildable" (is the SPEC single-sourced and
buildable?). ACD-1800 = "what IS the unit of work, and where does completion live?"
Distinct theme -> distinct L0. ACD-1600 already carries 6 L1s (a-f); adding this
would blur single-source with unit-of-work/done-accounting. ACD-1800 is the deeper
reframing the thin-ticket L1s (ACD-1600a/b) are a symptom of.

## The two concepts and their L1 homes

- CONCEPT A (AC = mini-ticket): ACD-1800a (AC lists its own deliverable checklist:
  code/tests/docs/diagrams/config) + ACD-1800b (per-deliverable sign-offs recorded
  ON THE AC; AC done only when all signed off).
- CONCEPT B (ticket = grouping container): ACD-1800c (ticket bundles ACs into a
  valuable feature, no sign-offs of its own, done when grouped ACs done).

## Supersession vs carry-forward — LOAD-BEARING for BA/IT-PO, do not re-litigate

- ACD-1800c records SUPERSESSION INTENT against the PREMISE of ACD-400b (generator
  produces a fully WIRED ticket an agent completes). ACD-1800b records supersession
  intent against ACD-400b-4's sign-offs-in-ticket clause. DO NOT edit ACD-400b /
  ACD-400b-4 -- governance handles the amend/supersede step; both already carry
  partial-supersession notes anticipating this.
- ACD-1800d CARRIES FORWARD ACD-400b-2 (implemented_by back-reference) and ACD-1800e
  CARRIES FORWARD ACD-400b-3 (idempotency / no duplicates). Those two L2s remain
  ACTIVE and are NOT superseded -- the new L1s only reframe them at AC-level (attach
  to AC-level work derivation, not ticket wiring). Keep ACD-400b-2/-3 as the concrete
  L2 behaviours when decomposing; do not re-author their mechanics under ACD-1800.

## Component-home caveat flagged to the user

Concept A's sign-off-recording mechanism touches the `signoff` skill / supervisor
sign-off machinery -> may also implicate `infrastructure` or build-orchestration.
Kept in ac-driven-dev to keep the goal cohesive; re-home candidate.

## Field convention (matched same-folder ACD-1600/ACD-1700 siblings, NOT stale schema)

components:[ac_driven_dev], readiness: draft, priority: medium, level, status:
active, req_status: draft, work_status: todo, roadmap_phase: phase_1, change_target
(pipeline for model L1s, pipeline for carry-forwards), risk_surface
(contract_boundary for Concept A/B model changes, internal for carry-forwards),
documentation_triggers on every L1 (ACD-1800e uses [] + documentation_rationale as a
carry-forward with no new user-facing behaviour). validate_ac_schema.py takes
explicit file paths (glob the *.yaml), all 6 passed.
