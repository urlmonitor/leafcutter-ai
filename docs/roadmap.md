---
title: Project Roadmap
type: reference
status: active
created: 2026-10-02
last_updated: 2026-10-02
components:
- infrastructure
description: Overview of Project Roadmap.
---
<!-- AUTO-GENERATED — do not edit by hand. Source: docs/roadmap.json -->
<!-- Regenerate manually: python portable-dev-workflow/scripts/commit_guardian/regenerate_roadmap_mirror.py --manual -->
<!-- Generated: 2026-10-02T08:57:04Z -->

# Project Roadmap

> **Source of truth**: `docs/roadmap.json`  
> To update the roadmap, edit `docs/roadmap.json` and commit — this file regenerates automatically.

## Current Focus

**Current Phase**: `phase_1`
**Current Outcome**: Stable MVP that installs into any project and helps the user build good software — portable, self-onboarding, and reliable enough to use across multiple repos.

## Phases

| Phase | Title | Status |
|-------|-------|--------|
| `phase_1` | Stable Portable MVP | **ACTIVE** ← current |
| `phase_acbuild_1_foundation` | AC-Driven Build v2 — Foundation & Read-Side | Planned |
| `phase_acbuild_2a_unit_of_work` | AC-Driven Build v2 — The Requirement Becomes the Unit of Work | Planned |
| `phase_acbuild_2b_ticket_demotion` | AC-Driven Build v2 — Ticket Demoted to a Grouping Container (dogfooded) | Planned |
| `phase_acbuild_3_migration` | AC-Driven Build v2 — Consumer Migration & Legacy Removal | Planned |
| `phase_store_record_health` | Store-Record Health — the store's own claims are true | Planned |
| `phase_2` | Ecosystem Hardening | Planned |
| `phase_3` | Distribution and Community | Planned |
| `phase_kernel_1_founding` | Decision Kernel — Founding (kernel Stages 0–1, V0 MVP) | **ACTIVE** |
| `phase_kernel_2_knowledge` | Decision Kernel — First Workers: Knowledge and Context Compiler (kernel Stage 2) | Planned |
| `phase_kernel_3_workflows` | Decision Kernel — First Workers: Engineering Workflows and Executable Policies (kernel Stage 3) | Planned |
| `phase_kernel_4_trails` | Decision Kernel — Trails: Colony Memory and Controlled Learning (kernel Stage 4) | Planned |
| `phase_kernel_5_specialists` | Decision Kernel — Specialists: Independent Engineering Runtime (kernel Stage 5) | Planned |
| `phase_colony_1_collect` | Colony Memory — COLLECT (optional Neo4j store, write-only) | Planned |
| `phase_colony_2_analyze` | Colony Memory — ANALYZE (learning evaluator, statistics, calibration) | Planned |
| `phase_colony_3_suggest` | Colony Memory — SUGGEST (evidence shown, routing unchanged) | Planned |
| `phase_colony_4_influence` | Colony Memory — INFLUENCE ROUTING (historical evidence in Jev routing) | Planned |
| `phase_colony_5_evolve` | Colony Memory — EVOLVE (gaps, weak policies and candidate workflows become reviewed proposals) | Planned |

## Phase Details

### phase_1: Stable Portable MVP (Current)

**Status**: **ACTIVE**

A reliable package that installs into any project via build.py, self-onboards the user via interactive config, and produces correct agents/skills/hooks without manual fixup.

**Exit Criteria**:

- Clean install succeeds on a blank project with only skills_config.json present
- build.py --validate-only returns 0 with no template injection errors
- Consecutive builds produce zero git diff (idempotent)
- The self-host build leaves the repository clean and reports truthfully: no unrequested edits to tracked files, no orphaned artifacts, no false all-clear

### phase_acbuild_1_foundation: AC-Driven Build v2 — Foundation & Read-Side

**Status**: Planned

Make the AC store the single source of truth WITHOUT changing behaviour. Additive-only: optional deliverable-checklist and per-deliverable sign-off fields plus a per-AC schema_version in ac_store_schema.json; a productionised effective-prompt render tool; canonical-source path resolution; and universal agent/gate dual-read (store-or-ticket-body). All new gates run advisory/warn-mode behind a two-stage ac_unit_of_work flag ({emit:false, enforce:false}). Read-side lands before any write-side change so the build can never go green while verifying nothing.

**Exit Criteria**:

- New AC fields are OPTIONAL in ac_store_schema.json; schema_version present (default 1); whole-store validation passes on both legacy and new shapes. The schema must declare the OPTIONAL slots for every field phase 2a will author — deliverable checklist, per-deliverable sign-offs, scope boundary (out_of_scope), observable-behaviour proof, adjudication trail, and the product-truth deliverable. additionalProperties:false is ENFORCED today via jsonschema.Draft7Validator in both scripts/ac_store/validate_ac_schema.py and the commit hook, so any field authored before its slot exists is rejected at commit. This criterion is a hard gate on all write-side work (ACD-1900a).
- render_effective_prompt.py productionised and in the build deploy-manifest; a fresh agent rendered purely from the store passes the comprehension test (ACD-1700c)
- Dual-read is verified BEHAVIOURALLY on the three gates that actually degrade, each named: ac-fulfillment-gate (today signs off status:ok and reads no YAML when ac_traceability is absent), ac-validator (today sources AC Coverage, Agent Contracts and sign-offs from the ticket body that ACD-1600a-2 deletes), and check_ticket_signoff_parity (today requires a ## Sign-offs section). Evidence must be a real on-disk thin ticket driven through each gate in a fresh process — per CLAUDE.md 'Gate / Workflow ACs — Verify Behaviorally, Not by Grep', a grep for dual-read prose in an agent template is NOT evidence. Enrichment / canonical-path / surface-to-craft / consistency gates run in warn mode (ACD-1900b, ACD-1600b/c/d).
- Each agent's brief is scoped to its role and the exclusion is demonstrated, not asserted — a rendered coder brief contains no requirement-authoring or supervisor-checklist content (ACD-1700a, ACD-1700b)
- No required CI gate references a new field; ac_unit_of_work flag introduced with a documented one-commit kill-switch (ACD-1900c, ACD-1900d)

### phase_acbuild_2a_unit_of_work: AC-Driven Build v2 — The Requirement Becomes the Unit of Work

**Status**: Planned

Move the truth onto the requirement WITHOUT touching the ticket. Each AC gains a deliverable checklist naming every artifact it needs and the craft responsible, per-deliverable sign-offs recorded ON THE AC, and the five fields the gap analysis found homeless: scope boundary, observable-behaviour proof, adjudication trail, parallel-safety claim, and the product-truth deliverable. Sign-offs are DUAL-recorded (AC and ticket) in this phase — nothing is removed. This is the half of the migration that delivers the actual value the user asked for ('ACs need to store which items need to be there to say the AC is done'), and it is independently shippable: if 2b is deferred, 2a still stands on its own.

**Exit Criteria**:

- Every requirement carries a deliverable checklist naming each artifact's kind and responsible craft, validated against the requirement's change surface; a requirement that needs docs or a diagram and omits them is flagged incomplete, naming each missing kind (ACD-1800a)
- Per-deliverable sign-offs are recorded on the requirement; requirement-level done is computed solely from them; a deliverable that does not apply is recorded explicitly as not-applicable, never silently dropped (ACD-1800b). Sign-offs are DUAL-recorded on AC and ticket in this phase — the move to AC-only is 2b.
- The five gap fields land, each with its consumer still working: scope boundary (ACD-1600g — note exclusions compose by DIFFERENCE not union, or the bundle produces false blockers), observable-behaviour proof (ACD-1800f), adjudication trail and parallel-safety claim (ACD-2000), and the product-truth deliverable as a DECLARED field whose evidence is the existing derived product_truth back-reference — declaring it as a plain deliverable kind creates a status cycle, because the flow already derives impl_status from the AC's work_status
- The fast lane refuses any requirement whose checklist declares a deliverable it cannot produce. Without this, fast_lane.mark_done_built_acs() keeps marking ACs done on test coverage alone once ACD-1800b redefines done as all-deliverables-signed — a phantom-done regression introduced BY the migration, in the tool with the strongest done-proof in the repo.
- THE TICKET IS UNCHANGED. No thinning, no sign-off removal, no gate flips. Any of those belong to 2b.

### phase_acbuild_2b_ticket_demotion: AC-Driven Build v2 — Ticket Demoted to a Grouping Container (dogfooded)

**Status**: Planned

Now that the requirement carries the truth, thin the ticket. The generator emits thin tickets that reference their AC instead of copying it; sign-offs move off the ticket body in a single atomic cutover behind ac_unit_of_work.emit; the ticket becomes a grouping container that bundles requirements into one valuable feature and is done when they are. Dogfooded on leafcutter itself before any consumer sees it. Split from 2a because ADR-026 provides two independent flag stages (emit, enforce) and the roadmap should mirror them — 2a has no observable midpoint otherwise.

**Exit Criteria**:

- Generator emits thin tickets behind ac_unit_of_work.emit; sign-offs move from dual-recorded to AC-only in one atomic change (ACD-1600a, ACD-1800c). ACD-1600a must not land before ACD-1900b-5: thinning ahead of fulfillment-gate dual-read fails QUIETLY, not loudly — the gate returns status:ok having read nothing.
- check_ticket_signoff_parity reconciled with a ticket that has no ## Sign-offs section (ACD-1800c-5). Unlike the gates above this one fails LOUD — it blocks every commit — so it is a stalled-repo risk, not a phantom-green one.
- A full self-host epic built end-to-end thin + AC-sign-off, behaviorally spot-checked on a real on-disk ticket in a fresh process (ACD-1900g)
- Store backfilled to 100% (strict schema validation = 0 errors); already-done ACs grandfathered, not regressed
- ac-fulfillment-gate flips 'absent ac_traceability -> blocker' and any new done-accounting gate is promoted to required (diff-scoped) only after >=10 consecutive green self-host merges (ACD-1900c-6)
- Legacy residue closed by name, not by family: ACD-400b.yaml is already status superseded_by, but ACD-400b-4 remains active/todo carrying the sign-offs-in-ticket clause, and inbox tickets TICKET-20260813-ACD-400b-6 and -7 are actively building the old wired-ticket model. Supersede the first and triage the other two before 2a starts.

### phase_acbuild_3_migration: AC-Driven Build v2 — Consumer Migration & Legacy Removal

**Status**: Planned

Bring existing consumers across safely, then retire the old path. build.py deploys the new artifacts (all hook deps in the deploy-manifest) and warns/refuses on schema_version skew; consumers run an opt-in, idempotent backfill; dual-readers remain for >=2 minor releases while in-flight fat tickets drain; only then are fat-ticket generation and the legacy-derive path removed.

**Exit Criteria**:

- build.py deploys new hooks with all deps in the deploy-manifest and warns/refuses on schema_version skew
- Opt-in idempotent backfill ships (dry-run, --ac-store-dir, preserves notes blocks); >=1 consumer (or consumer-sim) migrated green
- Dual-readers retained >=2 minor releases; in-flight fat tickets allowed to drain; legacy fat-ticket generation and dual-read/derive removed in a dedicated release with one full green cycle
- Rollback rehearsed: ac_unit_of_work.enforce=false restores green within one commit

### phase_store_record_health: Store-Record Health — the store's own claims are true

**Status**: Planned

The AC store is the source of truth every gate reads, so a false record is a false gate. Four trees that share one subject and had no phase to belong to: ACS-1200 (a deliberately parked tree is a recognised state, not a rule to skip), ACS-1300 (the requirement-to-test link is trustworthy in both directions), ACS-1400 (a composite's done-claim is judged against the children that actually exist), and ACS-1500 (those last two are the same overloaded field, and the relation must be declared rather than inferred). None of these advance phase 1's install/idempotency exit criteria, which is why ACS-1200 and ACS-1300 left themselves unphased rather than claim a phase that did not fit — this phase is that missing home. Sequencing inside it is real and load-bearing: ACS-1500a must precede ACS-1400c's adjudication of the population it cannot safely touch, and ACS-1200a must precede ACS-1400a because the strengthened back-link rule fires against parked trees the exemption has not yet protected.

**Exit Criteria**:

- A parked tree is recognised by a positive deliberate signal rather than by the absence of children, and every health surface that infers breakage from a missing link agrees with it (ACS-1200). Absence-keyed exemptions are disqualifying: absence is also what a half-broken tree looks like.
- The requirement-to-test link is repaired in both directions of rot and stays repaired for records that never pass through the ticket pipeline (ACS-1300). Nothing in that tree writes work_status at any level — restoring an evidence link and awarding a done badge are two acts.
- The parent-to-child link is complete, and the commit-time guard's silence means exactly one thing (ACS-1400). Today it has three escape hatches and 26 of 47 known orphans are exempted by an undocumented one, so a green hook is not evidence the link was checked.
- 'Done' is explicitly NOT zero orphans: a store reporting labelled deliberate exclusions is healthy, and any criterion binding success to zero forces the six KM-200 repairs that must never happen.
- The coverage field expresses which relation each entry means, every reader asks for the relation it intends, and the ~76 records already holding both relations in one list carry their meaning across (ACS-1500). No flag day is available — several readers are pre-commit hooks and required CI gates running from the deployed layout — so staged rollout with a one-commit kill-switch is a criterion, not a preference.
- Every safety guarantee in this phase is asserted in the same invocation as a repair that genuinely happened. 'Left the parked records alone', 'byte-stable' and 'changed no done-proof verdict' are all trivially true of a tool that does nothing.

### phase_2: Ecosystem Hardening

**Status**: Planned

Handle version upgrades gracefully with template migrations and config schema evolution. Support multiple concurrent consumer projects and document the contribution workflow for new agents and skills.

**Exit Criteria**:

- Version upgrade path tested: old config + new templates produces valid output with migration warnings
- Documented contribution workflow for adding agents and skills to the package
- Config schema validation rejects unknown keys with actionable error messages

### phase_3: Distribution and Community

**Status**: Planned

Installable via a standard package manager with versioned releases, changelogs, and a documented extension mechanism for community-contributed agents and skills.

**Exit Criteria**:

- Package installable via a standard package manager (pip or npm)
- Versioned releases with auto-generated changelogs
- Extension mechanism documented and tested with at least one community-contributed agent

### phase_kernel_1_founding: Decision Kernel — Founding (kernel Stages 0–1, V0 MVP)

**Status**: **ACTIVE**

The colony is founded. A native LangGraph kernel with an empty capability registry (ADR-055) routes and decides with Jev, runs a generic research loop over read-only retrieval, hands generative and human work to Claude Code, resumes persistently, records capability gaps and traces every run in Langfuse. The human and Claude still do most of the work; the kernel records everything needed to count it later. Driven by TICKET-20260930-KernelBootstrapV0. Lives in leafcutter-ai only; not shipped to adopters. The colony-memory COLLECT step (phase_colony_1_collect) can start right after this phase (ADR-057 §10).

**Exit Criteria**:

- A real question is researched when necessary, returned with evidence, and traceable end to end without hidden host-side orchestration (kernel spec §3 Stage 1 exit, §16)
- Capability-gap records are countable (occurrence_count, example_run_ids) and host_only fallback reliance is recorded (spec §14)
- The colony-memory recording prerequisites are decided: policy/template/model versions beside CorrelationIds and an outcome event keyed to decision_id are either implemented or explicitly deferred by a recorded decision (ADR-056 §9)
- A colony-health baseline is captured from the first real runs, so later stages can show they made the colony stronger (ADR-056 §9)

### phase_kernel_2_knowledge: Decision Kernel — First Workers: Knowledge and Context Compiler (kernel Stage 2)

**Status**: Planned

Glossary- and component-aware search, progressive disclosure, graph-backed retrieval, hybrid code search and reusable retrieval memory, so evidence is assembled before a specialist model is called (spec §17).

**Exit Criteria**:

- The same kernel supplies a compact evidence package before a reasoning or coding model is called, using structural and semantic retrieval where justified (spec §17 Stage 2 exit)
- At least one colony-health measure improves on the previous stage's baseline (share of requests resolved by specialized capabilities rather than fallback; decision accuracy and calibration per type; cost and time per resolved task; rework rate; gap recurrence after a capability ships). A stage is not reported as strengthening the colony without such a measure (ADR-056 §9)

### phase_kernel_3_workflows: Decision Kernel — First Workers: Engineering Workflows and Executable Policies (kernel Stage 3)

**Status**: Planned

Discovery before acceptance criteria, AC-specific context, inherited component policies, role-specific contracts and post-change verification (spec §18). Policies and workflows must exist before decision-rule or path reinforcement can apply to them (ADR-056 §9).

**Exit Criteria**:

- A real feature follows discovery, approved decisions, role-specific contracts, implementation, tests, and documentation/architecture impact review with a complete evidence trail (spec §18 Stage 3 exit)
- At least one colony-health measure improves on the previous stage's baseline (share of requests resolved by specialized capabilities rather than fallback; decision accuracy and calibration per type; cost and time per resolved task; rework rate; gap recurrence after a capability ships). A stage is not reported as strengthening the colony without such a measure (ADR-056 §9)

### phase_kernel_4_trails: Decision Kernel — Trails: Colony Memory and Controlled Learning (kernel Stage 4)

**Status**: Planned

Traces become colony memory (ADR-056): an analytics job feeds a performance store; decisions carry outcomes and per-type calibration; wrong decisions produce reviewed policy-gap and promotion proposals; capability gaps are ranked to propose what to build next. Reinforcement-informed routing and exploration come only after the performance store exists and passes evaluation (spec §19). Delivered through the colony-memory track phase_colony_2_analyze to phase_colony_5_evolve on the optional Neo4j colony memory store (ADR-065, ADR-058).

**Exit Criteria**:

- A reviewed lesson demonstrably changes future work while retaining its evidence, evaluation, version, and rollback controls (spec §19 Stage 4 exit)
- An analytics job produces a performance store of compact routing statistics; the kernel reads those statistics and never queries Langfuse directly (ADR-056 §8)
- Calibration is measured per decision type from observed outcomes, and capability-gap statistics produce prioritization proposals on which a human sets the priority (ADR-056 §4, §6)
- Usage alone never raises a path's standing; reinforcement-informed routing and exploration are activated only after passing held-out evaluation (spec §19.4, ADR-056 §3)
- At least one colony-health measure improves on the previous stage's baseline (share of requests resolved by specialized capabilities rather than fallback; decision accuracy and calibration per type; cost and time per resolved task; rework rate; gap recurrence after a capability ships). A stage is not reported as strengthening the colony without such a measure (ADR-056 §9)

### phase_kernel_5_specialists: Decision Kernel — Specialists: Independent Engineering Runtime (kernel Stage 5)

**Status**: Planned

Direct model and agent executors, additional clients, stronger isolation and production operational controls (spec §20). Native executors replace host work where scout evidence shows the colony still relies on the host.

**Exit Criteria**:

- The backend works without Claude Code as its host and can use specialist providers without changing the engineering process (spec §3 Stage 5 exit)
- Each native executor that replaces host.* work is justified by recorded host_only scout evidence (spec §21, ADR-056 §9)
- At least one colony-health measure improves on the previous stage's baseline (share of requests resolved by specialized capabilities rather than fallback; decision accuracy and calibration per type; cost and time per resolved task; rework rate; gap recurrence after a capability ships). A stage is not reported as strengthening the colony without such a measure (ADR-056 §9)

### phase_colony_1_collect: Colony Memory — COLLECT (optional Neo4j store, write-only)

**Status**: Planned

The optional colony memory store starts recording learned statistics (ADR-057 as amended by ADR-065). A Neo4j backend attaches to the ColonyMemory port (ADR-059) next to its file and null backends; Learned statistics are off when no Neo4j store is configured (LEAFCUTTER_NEO4J_* settings) or when LEAFCUTTER_SELF_LEARNING=false; decision records and precedent keep following memory.backend (ADR-059). Statistics are derived aggregates updated after specific actions. Records graph usage, decisions, outcomes, capability gaps and fallback usage with context dimensions. No behavioural influence. Earliest start: right after phase_kernel_1_founding (inside V0 only if the V0 build decides so).

**Exit Criteria**:

- Without a configured Neo4j store (or with LEAFCUTTER_SELF_LEARNING=false) learned statistics are off and the kernel, Jev, LangGraph, Claude handoff, Langfuse tracing and ADR-059 precedent work unchanged; no code outside the port's startup choice branches on the setting (ADR-057 §3, ADR-065 §4)
- With a configured Neo4j store, completed runs update derived statistic aggregates (graph usage, decision outcomes, capability gaps, fallback usage) after the defined trigger actions; the aggregates are rebuildable and never canonical (ADR-065, ADR-060)
- Every recorded statistic carries the mandatory context dimensions (capability, task_type, component, repository/project, policy_version); nothing is recorded as a global rate (ADR-057 §7)
- Recording changes no routing or decision behaviour (ADR-057 §10)
- Every important kernel node is traced in Langfuse, including non-LLM steps, via the v4/OpenTelemetry SDK (ADR-058)

### phase_colony_2_analyze: Colony Memory — ANALYZE (learning evaluator, statistics, calibration)

**Status**: Planned

A learning evaluator distils completed-run outcomes from Langfuse traces and scores into the store; statistics are derived and shown: success rates, common paths, wrong decisions, confidence calibration per decision type (ADR-056 §4, ADR-057 §10, ADR-058). Kernel stage 4.

**Exit Criteria**:

- Decisions and routing choices carry Langfuse scores from later outcomes (human review, application code, deterministic evaluators) (ADR-058)
- The learning evaluator writes compact statistics to the colony memory store; the routing hot path never queries Langfuse (ADR-057 §5)
- Calibration per decision type is measured from observed outcomes and visible to the team (ADR-056 §4)
- Every confirmed wrong decision becomes a Langfuse dataset case (ADR-058)
- At least one colony-health measure improves on the previous step's baseline before this step is reported as strengthening the colony (ADR-056 §9, ADR-057 §10)

### phase_colony_3_suggest: Colony Memory — SUGGEST (evidence shown, routing unchanged)

**Status**: Planned

Historical evidence is surfaced as suggestions, for example "historically this path performs better", and capability-gap statistics rank what to build next; routing does not change and a human sets priorities (ADR-056 §6, ADR-057 §10). Kernel stage 4.

**Exit Criteria**:

- Suggestions are shown alongside routing and gap reports without changing any routing decision (ADR-057 §10)
- Capability-gap statistics (frequency, fallback cost, failure rate) produce prioritization proposals; a human sets the priority (ADR-056 §6)
- At least one colony-health measure improves on the previous step's baseline before this step is reported as strengthening the colony (ADR-056 §9, ADR-057 §10)

### phase_colony_4_influence: Colony Memory — INFLUENCE ROUTING (historical evidence in Jev routing)

**Status**: Planned

Historical success, failures, calibration, cost and latency for similar requests are fed into Jev routing next to semantic fit, with exploration of alternatives (ADR-056 §3, ADR-057 §10). Kernel stage 4 or later.

**Exit Criteria**:

- Routing influence is activated only after calibration and after passing the held-out evaluation of spec §19.4, including the Langfuse dataset regression cases (ADR-057 §10, ADR-058)
- Usage alone never raises a path's standing; evidence is version-scoped and decays (ADR-056 §3)
- A share of runs explores eligible alternatives within existing permission and budget rules (ADR-056 §3)
- At least one colony-health measure improves on the previous step's baseline before this step is reported as strengthening the colony (ADR-056 §9, ADR-057 §10)

### phase_colony_5_evolve: Colony Memory — EVOLVE (gaps, weak policies and candidate workflows become reviewed proposals)

**Status**: Planned

The colony detects recurring capability gaps, weak policies (POLICY GAP), candidate workflows and repeated LLM reasoning, and turns them into reviewed proposals under the promotion rule (ADR-054, ADR-056 §5–§7, ADR-057 §10).

**Exit Criteria**:

- EVOLVE produces proposals only; turning one into a policy, workflow or registry entry remains a reviewed step with versions and rollback (ADR-056 §3 rule 5)
- At least one reviewed lesson demonstrably changes future work (spec §19 Stage 4 exit)
- At least one colony-health measure improves on the previous step's baseline before this step is reported as strengthening the colony (ADR-056 §9, ADR-057 §10)

---

*Last regenerated: 2026-10-02T08:57:04Z. Do not edit this file directly — edit `docs/roadmap.json` instead.*
