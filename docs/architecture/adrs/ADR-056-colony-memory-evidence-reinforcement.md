---
title: "ADR-056: Colony Memory — Evidence Reinforcement from Observed Outcomes"
description: "Leafcutter learns from the observed outcome of every capability invocation and important decision: verified outcomes strengthen a path, failures and wrong decisions weaken it, and repeated capability gaps create pressure for new capabilities. Usage alone never counts as evidence of correctness, and evidence can rank and propose but never activate a change without review."
type: "adr"
status: "active"
created: "2026-09-30"
last_updated: "2026-10-02"
deciders:
  - BrainCandy
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-054-process-representation-and-maturity-model.md
  - docs/architecture/adrs/ADR-057-colony-memory-store-optional-postgres.md
  - docs/architecture/adrs/ADR-058-langfuse-colony-history-scores-datasets.md
  - docs/architecture/adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md
  - docs/architecture/components/decision-kernel.md
  - docs/vision.md
  - docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md
  - docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md
related_code:
  - kernel/contracts/base.py
  - kernel/contracts/decision.py
  - kernel/contracts/run.py
  - kernel/observability/correlation.py
  - kernel/observability/tracer.py
---

# ADR-056: Colony Memory — Evidence Reinforcement from Observed Outcomes

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-30 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded from the 2026-09-30 "colony memory" design discussion, which BrainCandy endorsed |
| Supersedes | None |

## Context

Three sibling ADRs define what the Decision Kernel
([TICKET-20260930-KernelBootstrapV0](../../../tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md))
runs and how it runs it. [ADR-052](ADR-052-capabilities-replace-agents-prompts-are-compiled.md)
replaces agents with capabilities. Its §9 records the policy, evidence and template versions
behind each invocation. [ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md)
picks the mechanism that answers each question. Its §6 holds that the runtime guarantees a check
ran, not that its answer was correct.
[ADR-054](ADR-054-process-representation-and-maturity-model.md) sets the maturity levels and the
promotion rule, and it leaves "how promotion is detected or triggered" open.

None of them says how Leafcutter learns from what actually happened. BrainCandy observed that the
kernel follows the leafcutter-ant metaphor more closely than before. Ants build paths that get
stronger, based on evidence, the more ants use them. Early on the queen has tasks besides laying
eggs. Later, many workers help the colony autonomously: they find food, which for Leafcutter
means finding missing graphs and capabilities. "So the whole feedback process, counting of used
graphs, nodes and (wrong) decisions becomes super important."

Counting use is easy, and Langfuse already shows it. Counting correctness is not. A wrong
decision appears only later, as an event pointing back at an earlier decision. Without that
back-attribution Leafcutter measures popularity, not quality.

**What V0 already has.**

- `CorrelationIds` on every observation, including `decision_id`, `capability_id` and
  `invocation_id`. `kernel/contracts/base.py` defines them.
- The events `routing.assessed`, `decision.status`, `gap.recorded` and `run.finalized`
  ([design part 5](../../analysis/2026-09-30-decision-kernel-design-5-client-observability.md)).
- Version data on individual records: `template_version` and `model_id` on a
  `RoutingAssessment`, `capability_version` on a `CapabilityInvocation`, and a `versions` map on
  a `Decision`
  ([design part 2](../../analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md)).
- Deduplicated `CapabilityGap` records with `occurrence_count`, `first_seen`, `last_seen`,
  `example_run_ids` and `fallback_outcome`. Every host operation also records a `host_only`
  observation
  ([design part 4](../../analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md)).
- Stage 4, "Controlled learning"
  ([spec §19](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md)), which
  requires review before activation and evaluation on held-out cases.

**What is missing:** (a) an outcome event that references an earlier `decision_id`, including a
decision from an earlier run; (b) policy, template and model version fields next to the
`CorrelationIds`; (c) any cross-run aggregation, which would be the trail map itself. (a) and (b)
cannot be added retroactively, so traces recorded without them can never be counted.
Without a recorded safeguard, the first reinforcement mechanism built would likely reinforce on
usage.

## Decision

### 1. The colony model is the architecture's organising metaphor

The mechanism is **stigmergy**. There is no central plan: ants coordinate by changing their
environment (pheromone trails), and other ants respond. In the kernel, every run MUST leave a
trace, and routing and promotion MUST read those traces. The feedback records ARE the trails.
They are not a reporting add-on.

| Ant colony | Leafcutter |
|---|---|
| Colony | Leafcutter runtime |
| Worker | capability / LangGraph workflow |
| Scout | research / capability-gap workflow |
| Pheromone trail | learned routing preference |
| Food found | successful task resolution |
| Dead-end trail | failed / incorrect decision path |
| Colony memory | execution statistics + decision evidence |
| Queen | bootstrap/growth mechanism rather than central controller |

The last row is a correction. Ant colonies are largely decentralised, and the queen is not their
central manager. In Leafcutter the queen stands for bootstrap and growth. At first a human with
an LLM does almost everything (ADR-054 Level 1). Later, capabilities do the work.

**The fungus garden.** Raw LLM work is the leaves, policies and workflows are the garden, and
promotion is gardening.

### 2. The governing principle and the safeguard

> **Leafcutter must learn from the observed outcome of every capability invocation and important
> decision. Successful paths gain evidence; unsuccessful paths lose evidence; repeated capability
> gaps create pressure for new specialized workflows.**

> **Historical usage may inform routing, but usage alone must never be treated as evidence of
> correctness.**

Both statements are binding. The safeguard prevents bad-path lock-in, the "ant mill" of army ants
that follow each other in a circle until they die.

### 3. Reinforcement rules

1. **Reinforce on verified outcomes, not on invocations.** Evidence MUST come from outcomes: a
   post-check passed, tests went green, a human accepted the result. An invocation count MUST
   NOT raise a path's standing. A heavily used graph that keeps needing repair is a busy road to
   nowhere. A `jev` or `reasoning` check that ran does not verify what it judged (ADR-053 §6).
2. **Evaporation.** Evidence MUST be scoped to the versions that produced it and MUST decay over
   time. A record made under template v1 and model X says little once v2 exists. Version scoping
   depends on ADR-052 §9. A fading trail also marks a capability for retirement, which becomes a
   proposal under rule 5.
3. **Negative evidence.** Wrong decisions and dead ends MUST count against the path that
   produced them. The most important measure is the wrong-decision count. The source lists
   further per-capability measures, as an illustration and not a schema: usage, successful and
   failed resolutions, fallback after use, human corrections, overrides, confidence when right
   and when wrong, cost, latency and downstream rework.
4. **Exploration.** Once routing uses reinforcement, a share of runs MUST try an alternative
   eligible path instead of the currently strongest one. A path that is never retried can never
   gain evidence. Exploration MUST stay within the existing eligibility, permission and budget
   rules.
5. **"Trails may rank and propose; they may not legislate."** Reinforcement MUST only rank
   candidates and produce proposals. Turning a trail into a policy, a workflow, a threshold or a
   registry entry MUST remain a reviewed step. That step requires review before activation,
   preserved versions, a rollback path and held-out evaluation (spec §19.2, §19.4; ADR-054 §3,
   §6). The runtime MUST NOT activate generated code by itself
   ([spec §2.3](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3.md)).

### 4. Decisions carry outcomes

A decision MUST have its outcome attributed to it when a later event references its
`decision_id`. These events attribute an outcome: a post-check failure, a human override at an
interaction, a repair loop, a revert, and a bug root-cause analysis. Spec §19.2 already requires
the "relevant failed decision trace".

Example, using the spec §4.4 demonstration question. The values are ILLUSTRATIVE, and `ADR-NNN`
stands for whichever ADR governs the decision:

```text
Decision:      type node_vs_subgraph, result subgraph, confidence .94
Outcome:       correct false, final_result node   (a later review changed it)
Evidence used: ADR-NNN, feature description, existing graph
Reason for correction: feature had no independent lifecycle
```

Enough such records answer a new question: under which conditions does the node_vs_subgraph
policy fail? For example, accuracy is high when `reusable` is known and low when neither
`reusable` nor `stateful` is known. A pattern like that shows a missing criterion or missing
evidence, so Leafcutter can improve the ADR or checklist itself.

**Calibration MUST be tracked per decision type.** If Jev says .95 a hundred times, it should be
right about 95 times. ILLUSTRATIVE: `component_mapping` answered in the .90–1.00 band and was
right .96 of the time. `node_vs_subgraph` answered in the same band and was right .78 of the
time. A poorly calibrated decision type MUST first be read as a deficient decision basis, meaning
the policy or ADR behind it. It is not necessarily a Jev fault. Spec §13.2 already treats an
initial threshold such as `0.90` as "an uncalibrated starting policy, not a correctness claim".

### 5. Three feedback layers

All names and numbers in this section are ILLUSTRATIVE. None of them is a kernel name.

1. **Capability reinforcement.** Did this capability resolve this kind of request? Example for
   "architecture uncertainty": decision_research .93, generic_research .71, ask_human .18.
2. **Path reinforcement.** A whole route gains evidence as a unit. Example: decision → retrieve
   internal principles → retrieve authoritative guidance → synthesize → decision, "seen 87
   times, resolves successfully 96%". A well-evidenced route is preferred and becomes a workflow
   candidate under ADR-054.
3. **Decision-rule reinforcement.** A policy question that keeps causing mistakes produces a
   **POLICY GAP** proposal. Example: the rule "Reusable capabilities should be subgraphs" has 12
   observed failures whose common missing factor is independent state or lifecycle, so the
   proposal is to add a lifecycle criterion. A POLICY GAP MUST remain a proposal under §3
   rule 5. It is the evidence-driven form of the maintenance assessment in spec §18.4 and the
   bug-to-policy proposal in §19.2.

### 6. Scouts are capability gaps

When the routing outcome is `no_match` (earlier `NO_CAPABILITY`, spec §7.6), the kernel records a
gap and then either runs an approved fallback or blocks (ADR-054 §5). This is the scout. At first
Claude does the work through fallback. A solution that keeps working becomes a capability
candidate and then a new worker. The frequency, fallback cost and fallback success of repeated
gaps MUST be the pressure signal for new capabilities. ILLUSTRATIVE: "analyze database migration
impact", seen 27 times with fallback success 24/27 and average cost $0.31, is a strong signal to
build that capability.

- Only `unsupported` and `host_only` gaps MUST create that pressure. `provider_failure`,
  `permission` and `ambiguous` gaps MUST NOT (spec §14; design part 4).
- Gap evidence informs backlog prioritisation. The priority itself MUST remain a human decision:
  strategic importance is product intent and preference, and ADR-053 §1 gives those to a human.
  Jev is permitted to PROPOSE a ranking. The counts, costs and rates behind it MUST be computed
  deterministically (ADR-053 §5).
- A candidate becomes a worker only after it is implemented, tested, reviewed, versioned and
  registered (spec §14).

### 7. Crystallisation uses ADR-054's maturity levels

The source's chain runs from LLM exploration through recurring decisions, then a policy or
checklist, then recurring sequences, then a workflow, then stable invariants, and finally
deterministic code. It abbreviates the chain as UNKNOWN → LLM → POLICY → JEV → WORKFLOW →
DETERMINISTIC. "JEV" MUST NOT be read as a maturity level, and this ADR creates no new level:

| Source step | [ADR-054](ADR-054-process-representation-and-maturity-model.md) level |
|---|---|
| UNKNOWN | 0 Unknown |
| LLM | 1 LLM-guided |
| POLICY, JEV | 2 Policy-guided. Jev is what applies the policy dynamically per task (ADR-054 §1). |
| WORKFLOW | 3 Workflow-guided |
| DETERMINISTIC | 4 Deterministic |

This answers ADR-054's open question on how promotion is detected or triggered: **it is
evidence-driven and reviewed.** Reinforcement evidence MUST detect promotion candidates and
propose them, and a promotion MUST be activated only through review under ADR-054 §3. Not all
knowledge reaches Level 4.

### 8. Observability stays separate from operational state

```text
Langfuse → analytics / evaluation job → Leafcutter performance store
         → compact routing statistics → kernel
```

Runtime routing MUST NOT query Langfuse directly. The kernel MUST read only the compact routing
statistics in the performance store. This extends spec §12.2, which says the durable local
record is authoritative for workflow state and "Langfuse is observability, not the checkpointer
or decision database". Routing MUST keep working when Langfuse is unavailable (§12.4). Statistics
MUST NOT override the deterministic eligibility exclusions, which run before Jev (ADR-053 §5).

### 9. Staged adoption: the colony must get measurably stronger at every stage

A stage MUST NOT be reported as strengthening the colony unless a colony-health measure shows
it. These measures are ILLUSTRATIVE, not a schema:

- the share of requests resolved by specialised capabilities rather than by fallback;
- decision accuracy and calibration per decision type;
- cost and time per resolved task;
- rework rate;
- gap recurrence after a capability ships.

**Stage 1 (MVP, kernel V0): recording prerequisites only.** These items are a **RECOMMENDATION
to the kernel V0 build. They do not change V0 scope.** They add no aggregation, no reinforcement
and no routing change:

1. Policy, template and model version fields next to the existing `CorrelationIds`.
2. An outcome event that references an earlier `decision_id`, across runs if needed. This ADR
   leaves the event's name and schema to the build.
3. Gap records that can be counted. The V0 design already provides them, so the recommendation
   is to keep them countable.

The reason is that traces recorded without these fields can never be counted retroactively.
Stage 1 already begins calibration evaluation on a small labelled set (spec §16, §21).

The later stages follow the spec's §3 roadmap:

| Stage | What this ADR places there | Basis |
|---|---|---|
| 2: knowledge and context compiler | None from the source. The closest mechanism is spec §17.5: reusable searches and retrieval plans, revalidated against model and policy versions. That is a narrow trail with evaporation. | The source is silent on Stage 2. |
| 3: workflows and executable policies | The prerequisites only. Policies (§18.4) and workflows must exist before decision-rule or path reinforcement can apply to them. | The source is silent. |
| 4: controlled learning (§19) | The analytics job and performance store; gap statistics used for prioritisation proposals; per-type calibration from observed outcomes; POLICY GAP proposals; evidence-driven promotion proposals. | Spec §3 puts capability prioritisation and bug-to-policy proposals here. The source puts the trail map here but does not stage the job or calibration separately. |
| 4 or later | Reinforcement-informed routing, path reinforcement and exploration. | The source is silent. They MUST NOT come before the performance store exists, activating them MUST pass the §19.4 evaluation, and exploration MUST NOT ship before reinforcement-informed routing. |
| 5: independent runtime | Native executors justified by `host_only` scout evidence (§6). | Spec §21: "a justified incremental replacement for observed host reliance". |

[ADR-057](ADR-057-colony-memory-store-optional-postgres.md) later refines the performance store's
placement: it is the optional PostgreSQL colony memory store, and its write-only COLLECT step (no
behavioural change) may start right after V0. ANALYZE, SUGGEST and INFLUENCE ROUTING keep the
placement and gates above. (Store technology superseded:
[ADR-065](ADR-065-colony-learned-statistics-neo4j-aggregates.md) keeps the learned statistics in
Neo4j as derived aggregates; the staging and gates are unchanged.)

## Consequences

### Positive

- Routing, promotion and prioritisation get an empirical basis. That is evidence about which
  engineering processes and decisions actually work, which software engineering normally lacks.
- ADR-054's promotion-trigger question has an answer: evidence detects and proposes, and review
  activates.
- A miscalibrated decision type points at the ADR or policy to improve, instead of at Jev.
- V0 pays for three recording prerequisites and nothing more, and its traces stay countable.
- Runtime routing does not depend on Langfuse's availability or latency.

### Negative

- Back-attribution is incomplete. Many wrong decisions never produce a later event, so evidence
  leans toward failures that are easy to detect. A missing failure event does not prove a
  decision correct.
- "Correct" has no settled ground truth yet, and a human override can express a preference
  rather than an error.
- Version scoping splits the data into small samples. Early statistics are noisy, and a new
  version starts with little evidence.
- Exploration costs something: some runs deliberately take a path other than the strongest one.
- Host cost is often `unavailable` (spec §11.7), so cost-based ranking works from partial data.
- V0 keeps the degraded-mode telemetry spool without re-exporting it (design part 5). A job that
  reads only Langfuse therefore undercounts those runs.
- New parts must be built and run: the analytics job, the performance store and the outcome
  events. A colony-health measure used as a target can also be gamed, so the measures need
  review.

### Operational

- The Stage 1 recommendation goes to the kernel V0 build. Adopting it is that build's decision
  and does not change V0 scope.
- Every learned change (a policy, workflow, threshold, registry entry or routing change) gets
  review before activation, preserved versions, a rollback path and held-out evaluation
  (spec §19.2, §19.4).
- The first countable input is `.leafcutter/kernel/gaps/observations.jsonl` with its aggregated
  view, `python -m kernel gaps --json`
  ([design part 3](../../analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md),
  part 5).
- Each stage's delivery reports which colony-health measures it made measurable or moved.

## Alternatives

- **Popularity- or usage-based routing.** Rejected. A path would gain standing from how often
  it is taken, whether or not it works. An early bad routing choice would reinforce itself and
  lock in, which is the ant mill the §2 safeguard prevents.
- **Static routing with no feedback.** Rejected. A capability that keeps failing post-checks
  would keep receiving the same requests, and a miscalibrated decision type would keep its
  thresholds. Repeated gaps would give no prioritisation signal, and ADR-054 promotion would
  have no trigger.
- **Runtime routing that reads Langfuse directly.** Rejected. Routing would depend on a service
  the spec allows to be unavailable (§12.4), and V0 does not export degraded-mode runs to it.
  Observability would become operational state, which §12.2 rules out. Every routing decision
  would also wait on a remote query of raw traces.
- **Fully automatic promotion with no review.** Rejected. Evidence that leans toward detectable
  failures would harden into policy without anyone checking it. The spec forbids this: the
  runtime must not activate generated code (§2.3), model output cannot rewrite active policies
  (§13.3), and a changed policy needs review before activation (§19.2).

## Open Questions

This ADR explicitly does not decide:

1. **The decay function.** How fast evidence fades, and whether time, versions or both drive it.
2. **The exploration rate.** Whether it is fixed or adaptive, and whether it varies by risk.
3. **Ground truth for "correct".** Which outcomes count as a verified success or a wrong
   decision. Spec §17.5 notes that changed files are "not perfect relevance labels".
4. **How "similar task" is defined.** This includes which key groups decisions into a decision
   type. V0 has Jev `template_id`s and decision questions, but no decision-type field.
5. **Where the performance store lives and its format.** This includes whether the job also
   reads the authoritative local `events.jsonl` records. Answered by
   [ADR-057](ADR-057-colony-memory-store-optional-postgres.md): an optional PostgreSQL store, named the colony memory store.
   [ADR-065](ADR-065-colony-learned-statistics-neo4j-aggregates.md) supersedes the store
   technology: the store is Neo4j and holds the statistics as derived aggregates.
6. **Threshold changes.** Whether calibration-driven changes to evidence thresholds may apply
   automatically within bounds, or always need review.

## References

- Source: the 2026-09-30 "colony memory" discussion (BrainCandy's idea, a Claude Code reply, and
  a second assistant's elaboration that BrainCandy endorsed: "we definitely need to write this
  down AND update our vision"). The `docs/vision.md` update is made separately.
- Originating work: `tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md`
- ADR-052 §9; ADR-053 §1, §5 and §6; ADR-054 §1–§6 and Open Questions (all linked in Context).
- [Decision Kernel component](../components/decision-kernel.md); kernel design parts 2–5; kernel
  spec Rev 3 [part 5](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md)
  (§11.7, §12, §13), [part 6](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md)
  (§14, §16) and part 1 and part 7 (linked in Decision and Context).
