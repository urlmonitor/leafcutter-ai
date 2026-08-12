# PO learnings — ACD-1900 (AC-Driven Build v2 SAFE MIGRATION mechanisms) framing

Captured 2026-08-12 (product-owner, origin_agent: BrainCandy run) authoring a new
sibling L0 in ac-driven-dev that operationalises ADR-026 (phased, dogfooded,
backward-compatible migration). For BA (L2/L3) and IT-PO (enrichment).

## Why a NEW L0 (ACD-1900), not more children under 1600/1700/1800

1600/1700/1800 = the TARGET MODEL end-state (the WHAT/WHY of the new build model).
ACD-1900 = the HOW-TO-MIGRATE-SAFELY layer (reversible, no-breakage adoption). Distinct
theme -> distinct L0. It is cross-cutting and spans ALL THREE phases (foundation ->
cutover -> migration), whereas each target-model L0 sits in one phase and already carries
6/3/5 L1s. Anchored the L0 at phase_acbuild_1_foundation (safety guarantees are set there);
each L1 carries its own phase.

## The 7 L1s and their phases (per ADR-026; migration PLAN, not AC numbers, is ordering authority)

- ACD-1900a additive schema + versioning ...... phase_1 foundation (schema / contract_boundary)
- ACD-1900b UNIVERSAL DUAL-READ (load-bearing) . phase_1 foundation (pipeline / contract_boundary)
- ACD-1900c two-stage flag + kill-switch ....... phase_1 foundation (config / contract_boundary)
- ACD-1900d advisory-before-required + deploy-manifest-first + diff-scoped .. phase_1 (pipeline)
- ACD-1900e opt-in idempotent backfill ......... phase_3 migration (code / contract_boundary)
- ACD-1900f consumer upgrade + compat window ... phase_3 migration (pipeline / contract_boundary)
- ACD-1900g dogfood-on-self-host-first + go/no-go .. phase_2 CUTOVER (pipeline / contract_boundary)

Note on 1900g: dogfood-first proving is phase_2 per the ADR (why roadmap_phase=_2, NOT _3);
the go/no-go criteria it DEFINES govern the phase_3 legacy removal (1900f). Kept as one L1 to
avoid over-fragmenting; do not re-cut at L1.

## LOAD-BEARING for BA/IT-PO — do not re-litigate

- ACD-1900b is ADR-026's load-bearing invariant ("read-side before write-side"). It is the
  store-OR-ticket-body COMPATIBILITY BRIDGE that MUST ship before ACD-1600a (thin tickets).
  It is the transitional twin of ACD-1600b (store-only END STATE) -- complementary, NOT a
  duplicate. Decompose 1900b to BEHAVIORAL tests that execute the dual-read + fallback path
  (per CLAUDE.md "Gate/Workflow ACs — verify behaviorally, not by grep"); a missing new field
  MUST mean legacy-derive, never fail-open-to-green.
- ACD-1900a makes the ACD-1800 fields (deliverable checklist, per-deliverable sign-offs)
  OPTIONAL + version-stamped during migration, and fixes the false docstring on
  validate_ac_schema.py + guards the dormant additionalProperties:false tripwire. It does not
  redefine those fields (ACD-1800 does).
- NO new supersession authored here. 1900c (emit=false returns fat tickets) and 1900f (drain
  in-flight fat tickets) REFERENCE the ACD-400b fat-ticket family that ACD-1800 supersedes, but
  governance handles the ACD-400b amend/supersede step (per ACD-1800 notes + prior PO/BA memory).
  Do NOT edit ACD-400b* here.
- 1900c: enforce may turn on ONLY when zero schema_version<2 ACs remain; two kill-switches
  (enforce=false -> advisory; emit=false -> fat tickets). schema_version = per-AC DATA signal
  (1900a); the flag = store POLICY (1900c) -- keep distinct.

## Component-home caveats (kept in ac-driven-dev for cohesion; RE-HOME candidates flagged)

- 1900a -> ac-store (schema governance). 1900d -> guardrail-engine (staged gate rollout /
  diff-scoping; pattern already exists there + testing-quality, e.g. BO-2500b). 1900e/1900f ->
  build-pipeline + ac-store (backfill script, build.py deploy + schema_version skew warning).
  IT-PO to decide final homes.

## Field convention (matched same-folder ACD-1600/1700/1800 siblings, NOT the stale strict schema)

components:[ac_driven_dev], readiness: draft, priority: medium, level, status: active,
req_status: draft, work_status: todo, roadmap_phase, criteria (tagline + narrative),
depends_on, doc_links (plain path strings on these siblings), assigned_agent/estimated_complexity
(null; estimated_complexity only on L0), delivers_to/expects_from null, origin_agent: BrainCandy,
created, amended_by [], superseded_by null, covered_by, implemented_by [], change_target,
risk_surface, documentation_triggers on every L1 (1900 siblings all had a trigger; none needed
[] + rationale). validate_ac_schema.py takes explicit file paths (glob the *.yaml) -- all 8 passed.
