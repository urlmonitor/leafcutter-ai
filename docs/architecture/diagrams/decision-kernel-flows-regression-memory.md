---
title: "Decision Kernel Regression Memory — Confirmed Mistakes as Langfuse Dataset Cases"
description: "L3 data flow of the offline regression branch of colony memory: a later outcome scores an earlier Jev decision in Langfuse, a confirmed wrong decision becomes a dataset case, and every change to an ADR, Jev instructions, retrieval or thresholds is run against those cases and reviewed before it is activated."
type: architecture
flight_level: L3-Component
diagram_type: data_flow
status: draft
parent: docs/architecture/diagrams/decision-kernel-flows-overview.md
created: 2026-09-30
last_updated: 2026-10-02
source_ticket: null
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/architecture/adrs/ADR-058-langfuse-colony-history-scores-datasets.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md
  - docs/architecture/diagrams/decision-kernel-flows-learning-loop.md
related_code:
  - kernel/observability/tracer.py
  - kernel/observability/correlation.py
  - kernel/memory/publish.py
tags:
  - decision-kernel
  - colony-memory
  - langfuse
  - regression
---

# Decision Kernel Regression Memory — Confirmed Mistakes as Langfuse Dataset Cases

Langfuse datasets are the colony's regression memory. They hold confirmed wrong decisions, so
that a later version does not relearn an old mistake
([ADR-058](../adrs/ADR-058-langfuse-colony-history-scores-datasets.md) §4). This branch runs
offline. The kernel's hot path never reads datasets (ADR-058 §6).

**Status: decided, not built.** ADR-058 says V0 scope is unchanged and that scores, datasets
and the regression gate "need new work, which this ADR does not schedule". The roadmap lists
scores and dataset cases among the exit criteria of `phase_colony_2_analyze`, which is kernel
Stage 4. On main the kernel's `Tracer` protocol still has no score operation.

```mermaid
flowchart LR
  OBS["Decision observation in a trace - ILLUSTRATIVE node_vs_subgraph gives subgraph at .94"] -.-> OUT["Later outcome - post-check failure, human override, repair, revert, bug root cause"]
  OUT -.-> SC["Langfuse score on that observation - decision_correct, final_choice, reason"]
  SC -.->|"confirmed wrong"| DS[("Langfuse dataset case - input, expected, previous result")]
  SC -.->|"learning evaluator"| CAL[("Learned statistics - per-type calibration, Neo4j")]
  CHG["Proposed change - ADR, Jev instructions, retrieval, thresholds"] -.-> EXP["Offline regression run - datasets and experiments"]
  DS -.-> EXP
  EXP -.->|"regresses"| CHG
  EXP -.->|"passes"| REV["Review before activation - versions kept, rollback path"]
  REV -.-> DEP["Activate or deploy"]
```

Parent: [Decision Kernel and Colony Memory — Design Map](decision-kernel-flows-overview.md)

See also: [Learning loop](decision-kernel-flows-learning-loop.md) (the runtime branch).

## From a decision to a dataset case

| Step | What the sources say | Source |
|---|---|---|
| The decision is observable | Every Jev decision and routing choice is its own observation with `CorrelationIds`. V0 emits `decision.status` and `routing.assessed` | ADR-058 §3; design part 5 |
| A later event attributes an outcome | A post-check failure, a human override at an interaction, a repair loop, a revert or a bug root-cause analysis that references the earlier `decision_id`, possibly from another run | ADR-056 §4 |
| The outcome finds its decision | The deterministic `trace_id` (from `run_id`) and the `decision_id` in the observation's metadata. V0 is recommended to add an outcome event keyed to `decision_id` | ADR-058 §3; ADR-056 §9 |
| The outcome becomes a score | ILLUSTRATIVE: `decision_correct = false`, `final_choice = node`, `reason = "No independent lifecycle"`. Scores can come from human review, application code, deterministic evaluators or LLM judges | ADR-058 §3 |
| A confirmed mistake becomes a case | ILLUSTRATIVE: dataset `node_vs_subgraph_decisions`; input = feature description plus ADR; expected = NODE; previous Jev result = SUBGRAPH | ADR-058 §4 |
| The same scores feed calibration | The learning evaluator distils them into decision-outcome aggregates, the raw material for per-decision-type calibration. ADR-057 §6 named a `decision_outcomes` table; ADR-065 keeps them as derived Neo4j aggregates | ADR-056 §4; [ADR-065](../adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md) |

**A second record of a wrong decision, in Git.** A published decision record can be corrected
with `python -m kernel decisions publish --correct OLD_ID`: an append-only correction with reason,
time, approver and the preserved evidence, plus a `superseded_by` link
([ADR-060](../adrs/ADR-060-source-of-truth-and-approval-authority.md) §5). It is a confirmed wrong
decision keyed by its `dec-` id, and it is live on main. No source says whether a correction also
becomes a Langfuse score, a dataset case or a statistics update (OP-32).

## The regression gate

Before a change to any of these is deployed, the decision system runs offline against the
relevant dataset cases, using Langfuse datasets and experiments (ADR-058 §4):

- an ADR or other decision basis;
- Jev instructions, meaning the decision specifications of ADR-052 §8;
- evidence retrieval;
- confidence thresholds (ADR-053).

This is the concrete form of spec §19.4, "Evaluate proposed policies, capability changes,
retrieval plans, and prompt/model versions on held-out cases". A passing run does not replace
review: activation still needs review, preserved versions and a rollback path (spec §19.2;
ADR-056 §3 rule 5). The change records its regression result together with its review
(ADR-058, Operational).

## Limits the sources name

- Many wrong decisions never produce a later event, so cases lean toward mistakes that are easy
  to detect. A missing `decision_correct = false` does not prove a decision right, and a human
  override can express a preference rather than an error (ADR-056, ADR-058 Negative).
- A case that motivated a change is not held out for that change (ADR-058 Negative; OP-24).
- Degraded-mode runs never reach Langfuse, so they cannot be scored or become cases
  (ADR-058 Negative).
- What counts as "correct" is not settled (ADR-056 open question 3; ADR-058 open question 1).

Open points for this page: OP-21, OP-24, OP-25, OP-32 in [open points](decision-kernel-flows-open-points.md).

## Legend

| Element | Meaning |
|---|---|
| Dotted arrow | Every step here is decided by ADR-058 but not built yet |
| Cylinder | Stored data in Langfuse or the learned-statistics store |

## Cross-Links

- Parent: [Design Map](decision-kernel-flows-overview.md)
- Sibling: [Learning loop](decision-kernel-flows-learning-loop.md)
- Decisions: [ADR-056](../adrs/ADR-056-colony-memory-evidence-reinforcement.md) §3–§4,
  [ADR-058](../adrs/ADR-058-langfuse-colony-history-scores-datasets.md) §3–§4,
  [ADR-060](../adrs/ADR-060-source-of-truth-and-approval-authority.md) §5,
  [ADR-065](../adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md)
- Evaluation before activation: [spec §19](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md)
