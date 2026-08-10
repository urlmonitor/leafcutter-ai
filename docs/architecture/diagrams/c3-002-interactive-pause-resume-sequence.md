---
title: "Interactive Pause/Resume — Pause, Ask, Answer, Resume Sequence"
description: "L3 sequence diagram of the ADR-024 pause -> ask -> answer -> resume interaction between the workflow engine (E2 body / resolveGate), the agent-mediated persist/read agent, the durable pending-question store, and the answerer — including the wrong-shape re-prompt loop and cross-process resume via resumeFromRunId."
type: architecture
diagram_type: sequence
status: active
flight_level: L3-Component
created: 2026-07-21
last_updated: 2026-07-21
parent: docs/architecture/components/interactive-pause-resume-substrate.md
source_ticket: tickets/00_inbox/TICKET-20260720-BO-2300a-3.md
components:
  - build_orchestration
related_docs:
  - docs/architecture/components/interactive-pause-resume-substrate.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/diagrams/c3-001-interactive-pause-resume-run-lifecycle.md
  - docs/architecture/adrs/ADR-024-interactive-pause-resume.md
related_code:
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/finalize-feature.js
related_adrs:
  - ADR-024
tags:
  - pause-resume
  - interactive-gate
  - resolveGate
  - agent-mediated-io
  - resumeFromRunId
---

# Interactive Pause/Resume — Pause, Ask, Answer, Resume Sequence

This diagram documents the message-level interaction of the ADR-024 pause/resume
mechanism as implemented by the inline `resolveGate()` / `pauseAtGate()` in
`templates/workflows-js/plan-feature.js` and `templates/workflows-js/finalize-feature.js`.
It spans the initial headless PAUSE, the durable persist, the later RESUME
re-invocation, the wrong-shape re-prompt loop, and the three resume branches
(`nothing_to_resume`, `unresumable_stale`, and the successful resume).

> **The workflow body does NO filesystem I/O.** The E2 body cannot touch the
> filesystem, so the durable pending-question store is written and read *only*
> through `agent()` dispatches (`pause-persist` and `read-pause-record`, both
> `agentType: status-checker`). The agent carries the Bash/Write tools that
> perform the actual JSON read/write.

---

```mermaid
sequenceDiagram
    autonumber
    participant Engine as Workflow Engine<br/>(E2 body / resolveGate)
    participant Agent as Persist / Read Agent<br/>(status-checker; has fs tools)
    participant Store as Durable Store<br/>.leafcutter/paused_runs/&lt;run_id&gt;.json
    actor Answerer as Answerer<br/>(human/operator, re-invokes via args)

    Note over Engine,Store: PAUSE — first (headless) invocation
    Engine->>Engine: resolveGate(gateId, liveGateFn, args, context)
    Engine->>Engine: liveGateFn() returns null (no reachable answerer)
    Engine->>Agent: agent(pause-persist){question, context, run_id, gate_id}
    Agent->>Store: write pending-question record (run-keyed)
    Store-->>Agent: written
    Agent-->>Engine: persisted
    Engine-->>Answerer: return { status: paused_awaiting_input } — run ends

    Note over Engine,Answerer: RESUME — later, new process
    Answerer->>Engine: re-invoke workflow (resumeFromRunId + args.resume_answer)
    Engine->>Engine: resolveGate: args.resume_answer.gate_id === gateId ?
    Engine->>Engine: validateAnswerShape(answer, type)

    loop RE-PROMPT — wrong-shape / unparseable answer
        Engine-->>Answerer: return { status: paused_awaiting_input } — rejected, stays paused (no read, no apply)
        Answerer->>Engine: re-invoke with corrected resume_answer
        Engine->>Engine: validateAnswerShape(answer, type)
    end

    Note over Engine,Store: valid shape — check the durable record via agent
    Engine->>Agent: agent(read-pause-record){run_id, gate_id}
    Agent->>Store: read record
    Store-->>Agent: { exists, stale, stale_reason? }
    Agent-->>Engine: { exists, stale }

    alt exists === false
        Engine-->>Answerer: return { status: nothing_to_resume } — no-op
    else stale === true
        Engine-->>Answerer: return { status: unresumable_stale, reason } — committed stages kept
    else record present and fresh
        Engine->>Engine: applyAnswerByType(answer, type) returns gate decision
        Note over Engine: harness replays committed agent() calls (resumeFromRunId);<br/>completed stages are NOT re-run — cross-process resume
        Engine->>Engine: proceed past gate — run continues (resumed)
    end

    Note over Engine,Store: The workflow BODY does NO filesystem I/O —<br/>the store is written/read ONLY via agent() dispatches.
```

Parent: [Interactive Pause/Resume Substrate — Container Overview](../components/interactive-pause-resume-substrate.md)

See also: [Interactive Pause/Resume — Run Lifecycle State Diagram](c3-001-interactive-pause-resume-run-lifecycle.md) — the same mechanism viewed as run states and transitions.

---

## Interaction walk-through (as implemented)

1. **Headless gate → pause.** `resolveGate()` finds no matching
   `args.resume_answer`, calls `liveGateFn()`, and receives `null` (no reachable
   answerer). It falls through to `pauseAtGate()`.
2. **Agent-mediated persist.** `pauseAtGate()` dispatches the `pause-persist`
   agent with the `question` shape and `context` snapshot. The agent writes the
   run-keyed record to `.leafcutter/paused_runs/<run_id>.json`. `resolveGate`
   returns `{ status: "paused_awaiting_input" }` and the caller returns — the run
   ends cleanly without discarding committed stages.
3. **Resume re-invocation.** Later, the answerer re-invokes the same workflow
   with `resumeFromRunId` set and `args.resume_answer` (carrying `gate_id`,
   `type`, and the answer payload).
4. **Shape check + re-prompt loop.** `resolveGate()` matches
   `args.resume_answer.gate_id === gateId` and runs `validateAnswerShape()`. A
   wrong-shape or unparseable answer returns `paused_awaiting_input` immediately
   — no `read-pause-record`, no apply — so the run stays paused and the same
   question is re-presented; the answerer re-invokes with a corrected answer.
5. **Durable record check.** On a valid shape, `resolveGate()` dispatches the
   `read-pause-record` agent, which reads the durable file and returns
   `{ exists, stale }`:
   - `exists === false` → `nothing_to_resume` (no-op).
   - `stale === true` → `unresumable_stale` with a reason (committed stages kept).
   - otherwise → `applyAnswerByType()` returns the effective gate decision and
     execution proceeds past the gate (the run is `resumed`).
6. **Cross-process resume.** Because `resolveGate` consults the answer *before*
   the live `agent()` call (ADR-024 Rule 4), the harness replays the committed
   `agent()` calls via `resumeFromRunId` and completed stages are not re-run —
   resume is correct and idempotent across a fresh process.

## Cross-References

- [Build Orchestration — Epic & Ticket Dispatch Sequencing](../components/build-orchestration.md) — the component that owns the engine workflow files carrying `resolveGate()` / `pauseAtGate()`.
- [Interactive Pause/Resume — Run Lifecycle State Diagram](c3-001-interactive-pause-resume-run-lifecycle.md) — the companion state diagram.
- [Interactive Pause/Resume Substrate — Container Overview](../components/interactive-pause-resume-substrate.md) — the parent L2 container.
- [ADR-024 — Interactive Gates Pause and Persist Instead of Cancelling When Headless](../adrs/ADR-024-interactive-pause-resume.md) — the design of record.
