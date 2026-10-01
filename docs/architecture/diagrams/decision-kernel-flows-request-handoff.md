---
title: "Decision Kernel Request Flow 2 — Host or Human Handoff, Resume and Finalize"
description: "L3 sequence of the second half of a kernel run: the waiting RunEnvelope, Claude Code performing exactly the requested host operation or asking the human, the validated resume through the submissions ledger, parent continuation and finalization, including rejection, repair and cancellation."
type: architecture
flight_level: L3-Component
diagram_type: sequence
status: draft
parent: docs/architecture/diagrams/decision-kernel-flows-overview.md
created: 2026-09-30
last_updated: 2026-09-30
source_ticket: null
components:
  - decision_kernel
related_docs:
  - docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md
  - docs/architecture/diagrams/decision-kernel-flows-request-native.md
related_code:
  - kernel/scheduler/nodes_interaction.py
  - kernel/persistence/run_store.py
  - kernel/contracts/interaction.py
tags:
  - decision-kernel
  - handoff
  - resume
---

# Decision Kernel Request Flow 2 — Host or Human Handoff, Resume and Finalize

This is the second half of a kernel run. [Request Flow 1](decision-kernel-flows-request-native.md)
ended with a `waiting_host` or `waiting_human` envelope and a CLI process that exited normally.
This page shows how Claude Code serves the pending interaction, how `resume` validates the
answer before the graph moves, and how the run reaches a terminal state.

**Status: V0.** Interaction nodes and submission validation are phase P6. The RunService
implementation, CLI and skill are P7. The `host.*` operations are P8. Cancellation hardening is
P9 (design part 6).

The cycle repeats: one handoff at a time, because `max_concurrent_host` is 1 and only the queue
head is served (design part 3).

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant CC as Claude Code skill
    participant CLI as CLI python -m kernel
    participant SVC as RunService
    participant RR as Run root .leafcutter/kernel
    participant SCH as Scheduler LangGraph
    participant OWN as Owning capability

    SVC-->>CLI: RunEnvelope waiting_host or waiting_human with pending_interaction and state_revision
    CLI-->>CC: JSON on stdout, exit 0
    alt waiting_host
        Note over CC: perform only the named operation, read only the listed artifacts, use only allowed_operations
        CC->>CC: write JSON that conforms to output_json_schema, actor host claude_code
    else waiting_human
        CC->>U: AskUserQuestion with question, choices and consequences
        U-->>CC: answer
        CC->>CC: write human_answer.v1, actor human, relayed_by claude_code
    end
    CC->>CLI: resume --run-id RUN --response response.json --json
    CLI->>SVC: resume_run(run_id, InteractionSubmission)
    SVC->>RR: run.json not cancelled, queue head, submissions ledger
    SVC->>SVC: check interaction_id, state_revision, kind and actor, schema, semantic checks
    alt submission rejected
        SVC-->>CLI: error code plus current envelope, state unchanged
        CLI-->>CC: exit 3, the host repairs once using error details
    else submission accepted
        SVC->>RR: write ledger entry with sha256 of the submission
        SVC->>SCH: ainvoke Command resume with the submission
        Note over SCH: await_interaction re-validates and turns the submission into a CapabilityResult for the owning item
        Note over SCH: integrate - when every required child is terminal the parent is ready again
        SCH->>OWN: execute with continuation and child_outcomes
        OWN-->>SCH: completed, or waiting with a new child
        Note over SCH: a new host or human child starts the cycle again from message 1
        SCH->>SCH: finalize - root completed, output schema matches, no required item open
        SCH->>RR: report.json, report.md, terminal status in run.json, events
        SCH-->>SVC: terminal state
        SVC-->>CLI: RunEnvelope completed, partial, blocked or failed
        CLI-->>CC: JSON on stdout, exit 0
        CC-->>U: report_ref as written, evidence locators, limitations, gaps, trace URL
    end
```

Parent: [Decision Kernel and Colony Memory — Design Map](decision-kernel-flows-overview.md)

See also: [Request Flow 1](decision-kernel-flows-request-native.md) and
[Context: host, worker, human](decision-kernel-context-host-worker-human.md).

## Resume validation, in order

`RunService.resume_run` checks the submission before it touches the graph (design part 3).

| Check | Rejection code | Effect |
|---|---|---|
| `run.json` status is `cancelled` | `run_cancelled` | Stale resumes after a cancel are refused; cancellation provenance is kept |
| No pending interaction: an identical ledger hash replays the current envelope; anything else is refused | `stale_submission` | An identical duplicate is idempotent |
| `interaction_id` is the queue head and `expected_state_revision` matches | `stale_submission` | |
| A `human` interaction accepts only `human_answer.v1` from `actor.kind="human"`; a `host_work` interaction only its `output_schema_id` from `actor.kind="host"` | `kind_mismatch` | A generative result can never answer a human question |
| Schema through the catalog, then the semantic checks: cited ids exist, the selected option was supplied, the `choice_id` was offered | `schema_invalid`, `semantic_invalid` | State unchanged; the interaction stays pending; host repairs count against `host.max_repair_attempts` (1) |

The ledger entry is written before `Command(resume=…)`. A restart finds the ledger entry and
resumes the still-pending interaction. The P6 restart tests must cover a restart just before
and just after that write (spec §13.1, design part 3).

## What a submission becomes

| Submission | Becomes | Source |
|---|---|---|
| Host output (`options.v1`, `findings.v1`, `evidence_bundle.v1`) | `CapabilityResult(completed)`; host evidence carries `verification=host_reported`; options stay `proposal_status=proposed`; usage is `unavailable` unless the host reports it | design part 4, `conversion.py` |
| Human answer (`human_answer.v1`) | `Evidence(category=task_context, semantic_type=human_input, source.kind=human)`, with the actor and `relayed_by` in provenance | design part 4 |

Every host operation also records a `host_only` gap observation. That is the scout signal the
[learning loop](decision-kernel-flows-learning-loop.md) counts later (design part 4, ADR-056 §6).

## Other ways a run ends

- **Cancel.** `python -m kernel cancel --run-id RUN --actor human:<id>` writes `cancel` and
  `status=cancelled` to `run.json` and appends `run.cancelled`. A running process sees it through
  `cancel_probe()` between supersteps (design part 3). P9 still has to verify the
  `aupdate_state(as_node="finalize")` step (design part 6, risk 5).
- **Silence.** An unanswered human question keeps the run in `waiting_human` until someone
  cancels it. No answer is inferred from silence (spec §11.6).
- **Guards.** Budget, time, no-progress and depth guards end the run as `partial` or `blocked`
  with the unresolved question (design part 3).

## Tracing across processes

Each CLI process opens a trace segment (`leafcutter.run` or `leafcutter.run.resume`) on the same
`trace_id`, which is derived from `run_id`. A resumed run therefore appends to one trace.
Handoffs appear as `interaction.opened`, `submission.accepted` and `submission.rejected` events.
The host's own work is host-reported, not traced by the kernel (design part 5; ADR-058 §2).

Open points for this flow: OP-04, OP-12, OP-15 in [open points](decision-kernel-flows-open-points.md).

## Legend

| Element | Meaning |
|---|---|
| Solid arrow | A call or message |
| Dashed arrow | A return value |
| `alt` block | Mutually exclusive branches |
| Self-arrow | Work done inside one participant |

## Cross-Links

- Parent: [Design Map](decision-kernel-flows-overview.md)
- Sibling: [Request Flow 1](decision-kernel-flows-request-native.md)
- Client, CLI exit codes and skill body: [design part 5](../../analysis/2026-09-30-decision-kernel-design-5-client-observability.md)
- Host handoff contract: [spec part 5 §11](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md)
