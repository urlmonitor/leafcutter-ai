---
title: "Finalize Start-of-Step Narration — Emission Sequence"
description: "L3 sequence diagram of how a start-of-step progress line travels from the beginning of each finalize-feature workflow step, through the shared narrate()/log() narration channel, to the live progress view — emitted before the step's own work (BO-1000a-1)."
type: architecture
diagram_type: sequence
status: draft
flight_level: L3-Component
created: 2026-07-21
last_updated: 2026-07-21
parent: docs/architecture/diagrams/c2-006-feature-to-merged-pr.md
source_ticket: tickets/00_inbox/epics/EPIC-InFlightVisibility/06_TICKET-20260720-BO-1000a-4.md
components:
  - build_orchestration
related_docs:
  - docs/architecture/diagrams/c2-006-feature-to-merged-pr.md
  - docs/architecture/components/build-orchestration.md
tags:
  - finalize
  - narration
  - start-of-step
  - live-progress
  - step-x-of-n
---

# Finalize Start-of-Step Narration — Emission Sequence

This diagram shows how a **start-of-step progress line** travels from the entry
of each numbered `finalize-feature` workflow step, through the shared narration
channel (`narrate()` → `log()`), to the live progress view — so an operator can
see which step is in flight the moment it begins.

The load-bearing property is **ordering**: the start-of-step line is emitted
*before* the step dispatches its own work (BO-1000a-1), so the in-flight step is
identifiable from the progress output alone even if that work later errors
(BO-1000a-1-i).

> **Every non-error step narrates.** A start-of-step line fires at the entry of
> all `STEP_COUNT` (= 9) numbered steps — carrying the `"Step X of 9"` position
> label (BO-1000a-2). A step whose outcome is already satisfied is **not**
> silently skipped: it still emits a start line reporting the skip and naming the
> already-satisfied condition (BO-1000a-3).

---

```mermaid
sequenceDiagram
    autonumber
    participant Step as Finalize step body (Step N)
    participant Narrate as narrate() helper
    participant Log as log() — E2 narration channel
    participant View as Live progress view
    participant Agent as Step sub-agent (agent())

    Note over Step,Agent: Each numbered step enters via phase('Step N') — X of STEP_COUNT (=9)

    Step->>Narrate: narrate("Step X of 9", "what this step is about to do")
    Note right of Step: Emitted BEFORE the step's own work is dispatched (BO-1000a-1 / BO-1000a-1-i)
    Narrate->>Log: log("Step X of 9: " + description)
    Log->>View: render start-of-step line
    View-->>Step: "Step X of 9: ..." now visible to the operator

    alt Step outcome already satisfied — skip case (BO-1000a-3)
        Step->>Log: log("Step X of 9: [skipped] <already-satisfied condition>")
        Log->>View: render skip line — step never silently omitted
    else Step performs its work
        Step->>Agent: await agent(...) — dispatch the step's work
        Agent-->>Step: result (ok / error / malformed)
        Note over Step,Agent: On error, the start-of-step line was already emitted → in-flight step identifiable from progress alone (BO-1000a-1-i)
    end
```

Parent: [Feature to Merged PR — End-to-End Sequence Diagram](c2-006-feature-to-merged-pr.md)

---

## The emission path, participant by participant

| Participant | Role in the emission path |
|---|---|
| Finalize step body (`Step N`) | The numbered step block in `finalize-feature.js`. On entry it calls `phase('Step N')` then invokes `narrate(...)` before its first `await agent(...)`. |
| `narrate()` helper | Shared start-of-step helper. Formats `progressText + ': ' + description` and forwards it to the narration channel. One helper keeps the `"Step X of N"` scheme uniform across all steps. |
| `log()` — E2 narration channel | The E2 engine global that writes onto the workflow's narration channel (the same channel used by `outcome()` and 20+ other call sites). Not a side channel. |
| Live progress view | Where the operator reads the streamed narration in real time. |
| Step sub-agent (`agent()`) | The step's actual work, dispatched *after* the start-of-step line. Shown to fix the ordering relative to the narration signal. |

## Ordering guarantees

- **Before the work (BO-1000a-1):** `narrate()` runs at the step's entry, before
  the first `await agent(...)` dispatch — never after the step returns.
- **Survives an error (BO-1000a-1-i):** because the start line is already on the
  channel, a subsequent error or malformed result cannot pre-empt it; the
  in-flight step is recoverable from the progress stream without relying on the
  error branch printing its own diagnostic line.
- **Skip still narrates (BO-1000a-3):** a step whose outcome is already satisfied
  still emits a start line reporting the skip and its cause; it is never a silent
  early return.

## Cross-References

- [Feature to Merged PR — End-to-End Sequence Diagram](c2-006-feature-to-merged-pr.md) — parent flow; finalize is its terminal (merge/close) phase.
- [Build Orchestration](../components/build-orchestration.md) — the component that owns the finalize-feature workflow surface.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-21 [architecture-diagram-author, EPIC-InFlightVisibility/06]:
  Initial creation (BO-1000a-4). Sequence of the start-of-step narration
  emission path in finalize-feature.js: step body -> narrate() -> log()
  (E2 narration channel) -> live progress view, with the start-of-step line
  emitted before the step's own agent() dispatch (BO-1000a-1 / BO-1000a-1-i),
  the "Step X of 9" framing (BO-1000a-2), and the skip-still-narrates case
  (BO-1000a-3) shown in the alt branch. Followed the established *-sequence.md
  directory convention (gates/probe/self-heal); scripts/scaffold/new_arch_doc.py
  is not deployed in this repo.
====================================================================
-->
