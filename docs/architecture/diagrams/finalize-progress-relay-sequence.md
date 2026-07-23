---
title: "Finalize Progress Relay — In-Flight Delivery Sequence"
description: "L3 sequence diagram of how a finalize progress line travels from the background finalize-feature workflow, through the durable run-progress journal (BO-1000c-1a) and the /finalize-feature launcher's poll/relay loop (BO-1000c-1b), into the main conversation and on to the user — arriving while the run is in flight rather than only at the end (BO-1000c-2), including the mid-flight halt case (BO-1000c-2-i)."
type: architecture
diagram_type: sequence
status: draft
flight_level: L3-Component
created: 2026-07-23
last_updated: 2026-07-23
parent: docs/architecture/diagrams/c2-006-feature-to-merged-pr.md
source_ticket: tickets/00_inbox/epics/EPIC-InFlightVisibility/16_TICKET-20260720-BO-1000c-3.md
components:
  - build_orchestration
related_docs:
  - docs/architecture/diagrams/c2-006-feature-to-merged-pr.md
  - docs/architecture/diagrams/finalize-progress-narration-sequence.md
  - docs/architecture/components/build-orchestration.md
tags:
  - finalize
  - progress-relay
  - run-progress-journal
  - in-flight
  - live-progress
  - halt
---

# Finalize Progress Relay — In-Flight Delivery Sequence

This diagram shows how a **finalize progress line** travels from the background
`finalize-feature` workflow all the way to the user in the main conversation,
**while the run is still in flight**. It documents the full relay path stitched
together by the BO-1000c sub-tree:

- **BO-1000c-1a** — the background workflow appends each emitted line to a
  durable, pollable run-progress journal at the moment it is emitted.
- **BO-1000c-1b** — the `/finalize-feature` launcher polls that journal and
  relays each new line into the main conversation where the user already is.
- **BO-1000c-2** — the surfaced progress reflects the in-flight step and
  arrives over time (multiple distinct updates), not as a single end-of-run
  batch.
- **BO-1000c-2-i** — on a mid-flight halt, the last conversation line reflects
  the halting step, learned from the live stream rather than only the terminal
  halt result.

The load-bearing property is **in-flight ordering**: because the journal is
written append-as-you-go and the launcher relays new lines during the run, a
line for the step currently underway reaches the user *before* the run finishes.

> **Why a launcher relay and not a direct print.** A background workflow cannot
> inject into the main conversation. The journal (BO-1000c-1a) is the durable
> hand-off surface; the launcher's poll/relay loop (BO-1000c-1b) is the only
> participant that can write into the conversation the user is watching. The
> separate live-workflows view remains available but is not the delivery path.

---

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Launcher as /finalize-feature launcher (main loop)
    participant WF as Background finalize workflow (finalize-feature.js)
    participant Journal as Run-progress journal (append-only, run-keyed)
    participant Convo as Main conversation

    User->>Launcher: /finalize-feature <branch>
    Launcher->>WF: Start background run (detached)
    Note over Launcher,WF: The workflow runs detached; it cannot write into the conversation itself.

    par Background run emits progress as it happens
        loop For each in-flight step (start-of-step + per-step-outcome)
            WF->>Journal: appendJournal(line) at the moment it is emitted (BO-1000c-1a)
            Note right of WF: Append-as-you-go, emission order preserved — not a single end-of-run flush.
        end
    and Launcher relays over time while the run is in flight
        loop Poll while run is in flight (bounded interval, dedup)
            Launcher->>Journal: Poll for new lines since last relayed
            Journal-->>Launcher: New line(s) in emission order
            Launcher->>Convo: Relay each new line (incremental, no duplicates) (BO-1000c-1b)
            Convo-->>User: Progress for the in-flight step appears BEFORE the run finishes (BO-1000c-2)
        end
    end

    alt Run completes normally
        WF->>Journal: append terminal outcome line
        Launcher->>Journal: Final poll — flush remaining lines
        Launcher->>Convo: Relay final line, then end-of-run recap
        Convo-->>User: Full progress seen live; recap confirms completion
    else Run halts mid-flight (BO-1000c-2-i)
        WF->>Journal: halting step's line already appended (relies on BO-1000a-1-i)
        Note over WF,Journal: The halting step's start-of-step line reached the journal before the failure.
        Launcher->>Journal: On detecting halt, flush any unrelayed lines
        Launcher->>Convo: Relay halting-step line BEFORE surfacing the terminal halt result
        Convo-->>User: Last live line names where the run stopped — not only the returned halt payload
    end
```

Parent: [Feature to Merged PR — End-to-End Sequence Diagram](c2-006-feature-to-merged-pr.md)

See also: [Finalize Start-of-Step Narration — Emission Sequence](finalize-progress-narration-sequence.md)

---

## The relay path, participant by participant

| Participant | Role in the relay path |
|---|---|
| User | Stays in the main conversation; receives live progress there without opening the separate live-workflows view. |
| `/finalize-feature` launcher (main loop) | Starts the background run, then polls the run-progress journal at a bounded interval and relays each new line into the conversation in emission order, deduplicating already-relayed lines (BO-1000c-1b). The only participant that can write into the conversation. |
| Background finalize workflow (`finalize-feature.js`) | Runs the numbered finalize steps detached from the conversation. Its `narrate()` / `outcome()` calls append each progress line to the journal at emission time (BO-1000c-1a). |
| Run-progress journal | Durable, append-only record at a launcher-locatable path keyed by worktree/run id. One human-readable progress line per entry, in emission order, written incrementally while the run is in flight. The hand-off surface between the detached workflow and the launcher. |
| Main conversation | Where relayed lines surface for the user in real time. |

## Ordering guarantees

- **More than two participants, full relay path (AC-1):** the diagram spans
  workflow → journal → launcher → conversation → user, so progress is shown
  travelling the entire distance from the background run to the person.
- **In-flight ordering, not end-of-run batch (AC-2 / BO-1000c-2):** the
  `par` / `loop` structure shows the workflow appending and the launcher
  relaying *concurrently during the run*, so a line for the step currently
  underway appears in the conversation before the run finishes, and multiple
  distinct updates arrive over time.
- **Emission order preserved (BO-1000c-1a):** the journal is append-only and
  the launcher relays lines in the order it reads them, so the conversation
  reflects the true sequence of steps.
- **Halt reaches the conversation live (BO-1000c-2-i):** on a mid-flight halt
  the launcher flushes any unrelayed journal lines, so the halting step's line
  reaches the conversation *before* the terminal halt result — the user learns
  where the run stopped from the live stream, relying on BO-1000a-1-i (the
  halting step's start-of-step line is emitted before the failure).

## Cross-References

- [Feature to Merged PR — End-to-End Sequence Diagram](c2-006-feature-to-merged-pr.md) — parent flow; finalize is its terminal (merge/close) phase.
- [Finalize Start-of-Step Narration — Emission Sequence](finalize-progress-narration-sequence.md) — sibling diagram; the emission half of the path (step body → `narrate()` → `log()`) that this diagram picks up at the journal.
- [Build Orchestration](../components/build-orchestration.md) — the component that owns the finalize-feature workflow and its launcher surface.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-23 [architecture-diagram-author, EPIC-InFlightVisibility/16]:
  Initial creation (BO-1000c-3). Sequence of the live finalize progress relay:
  background finalize workflow (finalize-feature.js) -> durable run-progress
  journal (BO-1000c-1a) -> /finalize-feature launcher poll/relay loop
  (BO-1000c-1b) -> main conversation -> user. Five participants (>2 per AC-2).
  In-flight ordering depicted with a par/loop so updates arrive during the run
  rather than only at the end (BO-1000c-2); mid-flight halt shown in the alt
  branch with the halting-step line relayed before the terminal halt result
  (BO-1000c-2-i, relies on BO-1000a-1-i). Followed the established *-sequence.md
  directory convention (gates/probe/self-heal/finalize-progress-narration);
  scripts/scaffold/new_arch_doc.py is not deployed in this repo, so frontmatter
  matches the committed sibling finalize-progress-narration-sequence.md.
====================================================================
-->
