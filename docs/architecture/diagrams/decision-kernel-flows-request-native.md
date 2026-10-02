---
title: "Decision Kernel Request Flow 1 — Native Work up to the First Wait"
description: "L3 sequence of one kernel run from the Claude Code skill through the CLI, RunService and LangGraph scheduler: Jev routing, the decision capability with its precedent lookup, a research child with parallel retrieval, parent resume, and the point where the run either finalizes or stops to wait for host or human work."
type: architecture
flight_level: L3-Component
diagram_type: sequence
status: draft
parent: docs/architecture/diagrams/decision-kernel-flows-overview.md
created: 2026-09-30
last_updated: 2026-10-02
source_ticket: null
components:
  - decision_kernel
related_docs:
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md
  - docs/architecture/diagrams/decision-kernel-flows-request-handoff.md
related_code:
  - kernel/service.py
  - kernel/adapters/cli.py
  - kernel/scheduler/graph.py
  - kernel/scheduler/nodes_route.py
  - kernel/intent/step.py
  - kernel/capabilities/decision/executor.py
  - kernel/capabilities/research/executor.py
  - kernel/capabilities/retrieval/executor.py
  - kernel/memory/precedent.py
tags:
  - decision-kernel
  - request-flow
  - jev
---

# Decision Kernel Request Flow 1 — Native Work up to the First Wait

This is the first half of one kernel run. It starts when the user calls the `/leafcutter` skill
in Claude Code. It ends at one of two points: the run finalizes, or it stops and waits for host or
human work. The second half is [Request Flow 2](decision-kernel-flows-request-handoff.md).

**Status: V0, on main.** Phases P1–P10 merged with PR #973, the V0.1 rounds with PR #977 and the
decision store with PR #978. The CLI, `RunService` and skill (P7) and the host operations (P8) are
built (design parts 5 and 6).

**Example path.** The caller's `TaskInput` carries a `decision_request.v1` payload with options
and approved criteria, as in the spec §4.4 demonstration ("node or subgraph?"). The typed payload
makes the intent `explicit`, so no intake intent question is asked. With a bare goal the first
route pass asks Jev the answer kind first; with no options, research grounds the option space and
the host proposes options. Those branches are in [flow 2](decision-kernel-flows-request-handoff.md)
and [Context: Jev calls](decision-kernel-context-jev.md).

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant CC as Claude Code skill
    participant CLI as CLI python -m kernel
    participant SVC as RunService
    participant SCH as Scheduler LangGraph
    participant JEV as Jev
    participant DEC as decision capability
    participant RES as research capability
    participant RET as retrieve.repository

    U->>CC: /leafcutter with a goal
    CC->>CLI: run --input task-input.json --json
    CLI->>SVC: start_run(TaskInput)
    SVC->>SCH: ainvoke with thread_id = run_id, durability sync
    Note over SCH: intake - Task, root Request, root WorkItem, pinned registry snapshot, budgets, trace id from run_id
    Note over SCH: schedule - guards and cancel probe. route - intent already explicit, deterministic eligibility filter first
    SCH->>JEV: one batched choice route.item over eligible descriptions plus NONE and NEEDS_CONTEXT
    JEV-->>SCH: probabilities, confidence, model_id
    Note over SCH: selected only if p at least 0.8 and confidence at least 0.5, else insufficient_context, no_match or unavailable
    SCH->>DEC: execute CapabilityInvocation via Send
    Note over DEC: load, precedent - find_decisions through the ColonyMemory port, then validate_basis (deterministic)
    DEC->>JEV: assess batch - kind, sufficient, satisfies, missing, preference, conflict, precedent per candidate
    JEV-->>DEC: answers per question
    DEC-->>SCH: waiting with research_request.v1 child and continuation
    Note over SCH: integrate validates and merges. Parent waits, child is ready and binds to research without Jev
    SCH->>RES: execute research child
    Note over RES: plan - the decision named its categories, so no Jev planning call
    RES-->>SCH: waiting with one retrieval_request.v1 per need
    par independent needs run concurrently
        SCH->>RET: retrieve internal_principles
    and
        SCH->>RET: retrieve prior_decisions
    end
    Note over RET: each worker pre-filters its sources and reranks in up to 3 Jev batches
    RET-->>SCH: evidence_bundle.v1 with excerpts, locators, content hashes
    SCH->>RES: resume children_done
    RES->>JEV: one research.assess batch - conflict, evaluable, answers per need
    RES-->>SCH: completed evidence bundle
    SCH->>DEC: resume with child_outcomes and the new evidence
    DEC-->>SCH: completed decision_report.v1 or waiting with a host or human child
    alt nothing left to hand out
        SCH-->>SVC: finalize - report.json, report.md, terminal status
    else a host or human item is pending
        Note over SCH: route binds host.* or human, open_interactions writes the packet, checkpoint, await_interaction calls interrupt
        SCH-->>SVC: GraphOutput with the interrupt
    end
    SVC-->>CLI: RunEnvelope
    CLI-->>CC: one JSON document on stdout, exit 0
```

Parent: [Decision Kernel and Colony Memory — Design Map](decision-kernel-flows-overview.md)

See also: [Request Flow 2 — Handoff, Resume and Finalize](decision-kernel-flows-request-handoff.md)
and [Context: Jev calls](decision-kernel-context-jev.md).

## Where the flow waits

| Wait point | What is persisted first | What the envelope says |
|---|---|---|
| A host item is bound (`host.generate_options`, `host.synthesize`, `host.research`, `host.formulate_question`) | `open_interactions` writes the packet to `runs/<run_id>/interactions/<id>.json`; the superstep is on disk (`durability="sync"`) before the CLI exits | `waiting_host` with the full `HostWorkRequest` |
| A human item is bound (decision `needs_human`, criteria and options approval, a ranked design choice, a precedent reuse question, an intent or routing clarification) | Same, as a `HumanQuestion` | `waiting_human` |
| No interaction pending and the root is terminal or a guard trips | `finalize` writes `report.json`, `report.md` and the terminal status | `completed`, `partial`, `blocked` or `failed` |

Native work never waits inside a CLI call. Children run inside the same `ainvoke`, and the
parent resumes when every required child is terminal (spec §8.1 steps 8–9). Only host and human
work stop the process. `await_interaction` has no side effects before `interrupt()`, so it can
safely run again on resume (design part 3).

## Notes per step

Step numbers are the diagram's message numbers.

| Step | Source of truth |
|---|---|
| 2 | The goal travels as a JSON file, never interpolated into a shell command (spec §11.2) |
| 4 | `intake` is idempotent. With no `input_payload`, the root request is a `goal_request.v1`. A request of kind `capability` needs semantic routing (design parts 2 and 3) |
| 5–6 | One Jev call covers every item that needs semantic routing; the top candidate is never selected silently (design part 4). `fixed` capabilities are never offered. With a bare goal the intake intent question comes first, and a classified root with one eligible candidate skips 5–6 (`intent_bound`, design part 3) |
| 7 | The `precedent` node looks up earlier approved decisions once. With options present, its `precedent.<dec-id>` questions ride the assess batch in step 8; an applicable one becomes `prior_decisions` evidence (ADR-059 §5) |
| 8–10 | `validate_basis` and `combine` are deterministic; `assess` is one Jev batch. Thresholds come from `config/kernel_config.default.json` (`decision.*`, `memory.*`) |
| 11 | A `research_request.v1` child of kind `evidence` binds to `research` without Jev (design part 3, "As built") |
| 12 | Decision-driven research plans exactly the categories the decision named (`evidence_needs_only`). Each retrieval child carries `operation`; a need with no native source goes to `host.research` instead (design parts 2 and 4) |
| 13–15 | Workers get independent state snapshots and return results only; `integrate` merges in sorted-id order (spec §8.3) |
| 17 | Skipped when there is no evidence to judge. A need Jev says is not answered drops to `partial` (design part 4, V0.1) |
| 19 | The parent reads child output from the run artifact `result-<invocation_id>.json` (design part 3, "As built") |
| 20 | A resolved decision is staged as a record in `runs/<run_id>/staged/decisions/` only when a human approved it; nothing is ever written to `docs/decisions/` during a run (ADR-060 §2–§3) |
| 21–24 | Exit code 0 for every envelope, including `waiting_*`, `blocked` and `failed` (design part 5) |

Every node, capability and Jev call becomes a Langfuse observation on one trace whose id is
derived from `run_id` (design part 5). The trace is observability only; the run root is
authoritative ([learning loop](decision-kernel-flows-learning-loop.md)).

**Later stages change the context, not this sequence.** From the INFLUENCE ROUTING step, the
routing call can also receive learned statistics (ADR-065 store). From Stage 2, evidence can come
from the context compiler, and ADR-062 knowledge retrieval (not yet on main) would add a research
source. See [Context: Jev calls](decision-kernel-context-jev.md).

Open points for this flow: OP-01, OP-03, OP-31 in [open points](decision-kernel-flows-open-points.md).

## Legend

| Element | Meaning |
|---|---|
| Solid arrow | A call or message |
| Dashed arrow | A return value |
| `par` block | Work items dispatched in the same superstep by separate `Send` packets |
| `alt` block | Mutually exclusive outcomes |

## Cross-Links

- Parent: [Design Map](decision-kernel-flows-overview.md)
- Sibling: [Request Flow 2](decision-kernel-flows-request-handoff.md)
- Kernel graph topology: [design part 3](../../analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md)
- Capabilities and Jev templates: [design part 4](../../analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md)
- Running it: [How to run the decision kernel](../../how-to/run-the-decision-kernel.md)
