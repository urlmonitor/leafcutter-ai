---
title: "ADR-058: Langfuse Is the Colony History — Every Node Traced, Decisions Scored, Datasets as Regression Memory"
description: "Langfuse is Leafcutter's foundational record of what happened. Every important node, including non-LLM steps, is traced; later outcomes attach to decisions and routing choices as Langfuse Scores; and confirmed wrong decisions become Langfuse Dataset cases that every policy change must pass before it deploys. The kernel's hot path never queries Langfuse."
type: "adr"
status: "active"
created: "2026-09-30"
last_updated: "2026-09-30"
deciders:
  - BrainCandy
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/architecture/adrs/ADR-057-colony-memory-store-optional-postgres.md
  - docs/architecture/components/colony-memory.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md
  - docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md
  - tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md
related_code:
  - kernel/observability/langfuse_tracer.py
  - kernel/observability/tracer.py
  - kernel/observability/correlation.py
  - kernel/observability/spool.py
  - kernel/contracts/base.py
---

# ADR-058: Langfuse Is the Colony History — Every Node Traced, Decisions Scored, Datasets as Regression Memory

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-30 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded from the 2026-09-30 "Langfuse + colony-memory store" discussion, which BrainCandy endorsed, and his binding instruction that followed it |
| Supersedes | None. Extends [ADR-056](ADR-056-colony-memory-evidence-reinforcement.md) §4 and §8. Sibling of [ADR-057](ADR-057-colony-memory-store-optional-postgres.md). |

## Context

[ADR-056](ADR-056-colony-memory-evidence-reinforcement.md) makes colony memory the organising
idea of the Decision Kernel
([TICKET-20260930-KernelBootstrapV0](../../../tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md)).
Paths gain evidence from verified outcomes. A decision carries its outcome
([§4](ADR-056-colony-memory-evidence-reinforcement.md#4-decisions-carry-outcomes)). Runtime
routing reads compact statistics and never Langfuse
([§8](ADR-056-colony-memory-evidence-reinforcement.md#8-observability-stays-separate-from-operational-state)).
ADR-056 does not say where an outcome is recorded, or how it finds the decision it belongs to.
[ADR-057](ADR-057-colony-memory-store-optional-postgres.md) decides the store for the compact
statistics: an optional, plain-PostgreSQL colony memory store (see
[colony memory](../components/colony-memory.md)).

The discussion asked: "Would we use Langfuse for the tracking / tracing of this?" The answer was
yes, as the primary tracking and evaluation layer, but not as the live memory that the kernel
queries on every routing decision.

**What V0 already has** ([design part 5](../../analysis/2026-09-30-decision-kernel-design-5-client-observability.md),
`kernel/observability/langfuse_tracer.py`):

- The Langfuse v4 SDK on OpenTelemetry, verified against v4.16. There is one trace per run.
  `trace_id` is derived deterministically from `run_id`, so a resumed run appends to the same
  trace across process restarts.
- An observation map: `kernel.<node>`, `capability.<id>`, `retrieval.<source>`, `jev.<purpose>`,
  and the events `routing.assessed`, `decision.status`, `guard.tripped`, the interaction events,
  `gap.recorded` and `run.finalized`.
- The non-null `CorrelationIds` in every observation's metadata, including `decision_id` where a
  decision exists. Redaction runs through the client's `mask=`. A degraded mode spools to
  `telemetry_spool.jsonl`.

**What is missing:**

- (a) No way to attach a later outcome to the decision it judges. The kernel's `Tracer` protocol
  has no score operation.
- (b) No record that turns a confirmed mistake into a reusable test case.
- (c) No rule that checks a change to an ADR, Jev instructions, retrieval or thresholds against
  past mistakes. Spec §19.4 requires evaluation on held-out cases but names no source for them.
- (d) No statement of Langfuse's standing. ADR-057 makes the colony memory store optional.
  Without a rule, Langfuse can be read as equally optional, or as something the kernel may query.

If this stays undecided, an outcome recorded nowhere cannot feed calibration (ADR-056 §4), and a
mistake fixed once can return with the next template or threshold change.

## Decision

### 1. Langfuse is the colony history, and it is foundational

Langfuse MUST be Leafcutter's complete observational record: traces, evidence references,
decisions, outcomes, corrections, cost, latency and evaluation scores. It answers "What actually
happened?"

- Langfuse MUST be part of Leafcutter Core. It MUST NOT be an optional add-on, and it MUST NOT sit
  behind ADR-057's self-learning switch: neither `LEAFCUTTER_COLONY_DB_URL` nor
  `LEAFCUTTER_SELF_LEARNING` affects tracing. With no colony memory store configured, every run
  MUST still be traced.
- Foundational does not make a run depend on it. Missing keys, a failed auth check or an SDK
  error MUST keep degrading to the local spool and `observability="degraded"`, as design part 5
  specifies ([spec §12.4](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md)).
  A Langfuse failure MUST NOT fail, block or change a run.
- Langfuse MUST NOT become the checkpointer or the decision database. The durable local run record
  stays authoritative for workflow state (spec §12.2). Evidence stays referenced by id and
  locator, never by full payload (design part 5).

> "Langfuse remembers what happened. [The colony memory store] remembers what Leafcutter learned."

### 2. Every important node is traced, not only model calls

Every run MUST be one top-level trace. Its child observations MUST cover every important node,
whether or not it calls a model: routing, retrieval, tool and adapter calls, Jev calls,
deterministic decisions and checks, verification, host handoffs, human interactions, capability
gaps and the final outcome. Automatic LangChain callbacks alone MUST NOT be relied on. Spec
§12.1 requires custom observations around deterministic decisions, source calls and host
handoffs, and the V0 live smoke test recorded the Jev call as a `CHAIN` with no usage.

The source's trace shape, ILLUSTRATIVE (these node names are not kernel names):

```text
TRACE
 ├── route_request   └── Jev → research_graph (.96)
 ├── research_graph  ├── retrieve_internal_patterns ├── retrieve_guidance └── synthesize
 ├── decision        └── subgraph (.93)
 ├── implementation  └── Claude
 ├── verification
 └── final outcome
```

What V0 already covers
([design part 3](../../analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md) node
map, design part 5 observation map):

| Node kind | V0 observation | V0 status |
|---|---|---|
| Scheduler steps (`intake`, `schedule`, `route`, `execute`, `integrate`, `record_gaps`, `open_interactions`, `await_interaction`, `finalize`) | `kernel.<node>` (chain) | Covered |
| Routing choice | `routing.assessed` event, and the `jev.<purpose>` generation for the batched Jev call | Covered |
| Jev call | `jev.<purpose>` generation with model id, usage, estimated cost, template ids, input fingerprint, raw distributions, confidence and thresholds | Covered |
| Decision | `capability.decision` (agent) and the `decision.status` event | Covered |
| Retrieval and tools | `retrieval.<source>` (retriever); `capability.<id>` (tool) for the retrieval adapter | Covered |
| Result validation and guards | `kernel.integrate`; `guard.tripped` event | Covered |
| Generative work (synthesis, implementation) | Host handoff: `interaction.opened`, `submission.accepted` / `submission.rejected` | The handoff is covered. The host's own work is host-reported (spec §11.5). |
| Capability gap | `gap.recorded` event | Covered |
| Final outcome of the run | `run.finalized` event | Covered |
| Later outcome of an earlier decision | None | Not in V0 (§3) |

V0 has no implementation or verification capability. When one is registered, it MUST emit its
observations under the same map and with the same `CorrelationIds`.

### 3. Decisions and routing choices are scored observations

This realises [ADR-056 §4](ADR-056-colony-memory-evidence-reinforcement.md#4-decisions-carry-outcomes)
("decisions carry outcomes") in Langfuse.

- Every Jev decision and every routing choice MUST be its own observation carrying its
  `CorrelationIds`. V0 already emits `decision.status` and `routing.assessed` for this.
- When the outcome becomes known, it MUST be attached to that observation as Langfuse Scores.
  Scores attach to a trace or to an individual observation. They can come from human review,
  application code, deterministic evaluators or LLM judges.
- V0's deterministic `trace_id` (from `run_id`) and the `decision_id` in the decision
  observation's metadata are what let a later outcome find the observation it scores.

Score names from the source, all ILLUSTRATIVE (see Open Question 1):

| Observation | Scores |
|---|---|
| Jev decision | `decision_correct`, `final_choice`, `reason` |
| Routing choice | `routing_success`, `required_fallback`, `required_rework`, `human_override`, plus iterations, cost and latency |

Example from the source, ILLUSTRATIVE. Jev decides node vs subgraph as SUBGRAPH with confidence
.94. The final architecture turns out to be NODE. That decision's observation then receives
`decision_correct = false`, `final_choice = node` and `reason = "No independent lifecycle"`.
Capability gaps are recorded the same way. V0 emits `gap.recorded`, and the source's illustrative
fields are `capability_gap`, `fallback`, `fallback_success` and cost.

Aggregated scores give calibration per decision type and confidence bucket (ILLUSTRATIVE: .5–.6
right 62% of the time, … .9–1.0 right 96%). They also give pheromone strength per capability:
uses, success %, fallback % and average cost. That aggregation MUST run outside the routing hot
path, in the learning evaluator that writes ADR-057's colony memory store. Whether the evaluator
runs right after a completed run or as a separate periodic job is ADR-057 Open Question 4.
A score records an outcome. It does not define "correct"; that remains ADR-056 Open Question 3.

### 4. Langfuse Datasets are the regression memory

- Every wrong decision confirmed by an outcome score MUST become a case in a Langfuse Dataset.
  A case holds the decision's input, the correct outcome and the previous result. ILLUSTRATIVE,
  from the source: dataset `node_vs_subgraph_decisions`; input = feature description + ADR;
  expected = NODE; previous Jev result = SUBGRAPH.
- Before a change to an ADR, to Jev instructions
  ([ADR-052 §8](ADR-052-capabilities-replace-agents-prompts-are-compiled.md) decision
  specifications), to evidence retrieval or to confidence thresholds
  ([ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md)) is deployed, the
  decision system MUST run offline against the relevant dataset cases, using Langfuse
  datasets and experiments. This is the concrete form of
  [spec §19.4](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md)
  ("Evaluate proposed policies, capability changes, retrieval plans, and prompt/model versions on
  held-out cases") and of ADR-056 §3 rule 5.
- A passing regression run MUST NOT replace review. Activation still needs review, preserved
  versions and a rollback path (spec §19.2; ADR-056 §3 rule 5).

The loop:

```text
production mistake → Langfuse trace → human / correct outcome → score → dataset case
  → improve decision policy → offline regression test → deploy
```

### 5. New code uses the Langfuse v4 / OpenTelemetry SDK

New Python code that writes to Langfuse (traces, observations, scores, dataset runs) MUST use the
current Langfuse v4 / OpenTelemetry SDK. It MUST NOT use the deprecated legacy `trace()` /
`span()` API. V0 already complies: `LangfuseTracer` uses `create_trace_id`, `start_observation`,
`propagate_attributes` and `CallbackHandler`, verified against v4.16, and reads back through
`api.observations.get_many`. Design part 5 records that the legacy trace GET returns 410 for this
organisation. The kernel's own `Tracer.span(...)` is a Leafcutter protocol method implemented on
`start_observation`. It is not the legacy API.

### 6. Three layers, and the hot path never queries Langfuse

| Layer | Holds | Answers | Read by |
|---|---|---|---|
| **Langfuse traces and scores: colony history** | Complete traces, evidence references, decisions, outcomes, corrections, cost, latency, scores | What actually happened? | Humans, the learning evaluator, analytics |
| **Colony memory store: pheromone map** ([ADR-057](ADR-057-colony-memory-store-optional-postgres.md)) | Small derived statistics | What has the colony learned? | The kernel, at runtime |
| **Langfuse Datasets: regression memory** | Confirmed wrong decisions as cases | Which old mistakes must not come back? | Offline regression, before deploy |

```text
Execution → Langfuse trace + scores → final outcome known → learning evaluator
          → colony memory store → kernel hot path
```

The kernel's hot path MUST NOT query Langfuse: not traces, not scores and not datasets. It reads
only the colony memory store (ADR-056 §8, ADR-057 §5). What Langfuse holds reaches the kernel
only through the learning evaluator, which distils it into that store. The evaluator's cadence
and its other inputs are ADR-057 Open Question 4. When the evaluator reads Langfuse, it MUST use
Langfuse's Metrics and Observations APIs and SDK access. No custom
tracing backend is built.

## Consequences

### Positive

- One place answers "what actually happened" for every run, including the non-LLM steps. A
  wrong decision can be traced back to the evidence and the versions it used.
- ADR-056 §4 gets a concrete home. An outcome becomes a score on the decision's observation, and
  calibration per decision type can be computed from those scores.
- Changes to ADRs, Jev instructions, retrieval and thresholds get a regression gate built from
  real production mistakes, so a later version does not relearn an old mistake.
- The V0 integration is reused as it is: deterministic trace ids, correlation ids, redaction and
  degraded mode. No custom tracing backend is needed.
- Runtime routing stays independent of Langfuse's availability and latency.

### Negative

- The colony history lives in a third-party service outside the repository. Its contents depend
  on redaction being right and on that service's retention.
- Degraded-mode runs never reach Langfuse, because V0 keeps the spool without re-exporting it.
  Those runs cannot be scored or become dataset cases, so the history undercounts them.
- Many wrong decisions never produce a later outcome, so scores lean toward mistakes that are easy
  to detect (ADR-056, Negative). A missing `decision_correct = false` does not prove a decision
  right, and a `human_override` can express a preference rather than an error.
- A dataset case that motivated a change is not held out for that change. Spec §19.4's held-out
  requirement needs cases that were not used to draft the change.
- Tracing every important node raises observation volume. That is why sampling and retention stay
  open (Open Question 2).
- Scores, datasets and the regression gate are new work beyond V0. The `Tracer` protocol has no
  score operation today.

### Operational

- V0 scope is unchanged. V0 already delivers §2's tracing for the nodes it has. §3 and §4 need
  new work, which this ADR does not schedule.
- Review rejects new Langfuse code that uses the legacy `trace()` / `span()` API (§5).
- Langfuse needs its own configured credentials (spec §11.7). Without them the tracer runs in
  degraded mode and the envelope reports `observability="degraded"`.
- Traces are inspected through the authenticated Langfuse data MCP, restricted to read-only
  tools (spec §12.3). That MCP connection is not tracing transport.
- A change to an ADR, Jev instructions, retrieval or thresholds records its dataset regression
  result together with its review before it is activated.

## Alternatives

- **A custom tracing backend or a Leafcutter-owned trace store.** Rejected. Langfuse already
  provides traces, scores, datasets and experiments, Metrics and Observations APIs, and a
  LangGraph callback integration, and V0 has verified the v4 SDK live. Spec §12.4 forbids a
  separate distributed telemetry platform for the MVP. A custom backend would rebuild all of that
  before the first score could be recorded.
- **Langfuse as the live pheromone store that the kernel queries.** Rejected, as in ADR-056 §8
  and ADR-057. Routing would wait on a remote query over raw traces (the source's example is the
  "last 10,000 traces" before every Jev call). It would also depend on a service the spec allows
  to be unavailable (§12.4), and observability would become operational state, which §12.2 rules
  out.
- **Langfuse as an optional add-on, enabled together with self-learning.** Rejected. With tracing
  off, a decision has no observation to score and a mistake has no trace to become a dataset
  case. The learning evaluator that feeds ADR-057's store would have nothing to read. A user
  without a colony memory store would also lose the only record of what happened.
- **Trace model calls only, through automatic callbacks.** Rejected. Routing, retrieval,
  deterministic decisions and host handoffs would be invisible, so a wrong routing choice or a
  bad retrieval could never be scored. Spec §12.1 requires those custom observations, and the V0
  smoke test showed that the callback records a Jev call as a `CHAIN` with no usage.
- **The legacy `trace()` / `span()` API.** Rejected. It is deprecated, the legacy trace GET
  already returns 410 for this organisation (design part 5), and V0 is built on v4.

## Open Questions

This ADR explicitly does not decide:

1. **Score naming and ownership.** The final score names and value types, which observation of a
   decision carries its scores, and which source (human review, application code, a
   deterministic evaluator or an LLM judge) may write each score. This interacts with ADR-056
   Open Question 3, ground truth for "correct".
2. **Sampling and retention.** Whether every node of every run is kept, for how long, and at what
   volume, honouring the configured region and retention policy (spec §12.4). This includes
   whether dataset cases must outlive the traces they came from.
3. **Where scores are written.** By the learning evaluator after the final outcome is known, or
   inline by the component that observes the outcome, for example at a human override.

## References

- Source: the 2026-09-30 "Langfuse + colony-memory store" discussion between BrainCandy and an
  assistant, endorsed by BrainCandy, and his binding instruction of the same day (the colony
  store is plain PostgreSQL; ADR-057 records that part).
- Originating work: `tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md`
- [ADR-056](ADR-056-colony-memory-evidence-reinforcement.md) §3 rule 5, §4, §8 and Open
  Question 3; [ADR-057](ADR-057-colony-memory-store-optional-postgres.md);
  [ADR-052](ADR-052-capabilities-replace-agents-prompts-are-compiled.md) §8;
  [ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md).
- [Decision Kernel component](../components/decision-kernel.md);
  [colony memory component](../components/colony-memory.md).
- Kernel design [part 3](../../analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md)
  (node map) and [part 5](../../analysis/2026-09-30-decision-kernel-design-5-client-observability.md)
  (Langfuse integration); kernel spec Rev 3
  [part 5](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md)
  (§11.5, §11.7, §12) and
  [part 7](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md) (§19.2, §19.4).
