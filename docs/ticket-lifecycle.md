# Ticket Lifecycle

This document shows how tickets flow through the system from creation to completion.

## Ticket State Transitions

```mermaid
stateDiagram-v2
    [*] --> inbox: /create-ticket
    inbox --> todo: /build-feature (epic) or\nmanual promotion
    todo --> in_progress: ticket-supervisor picks up
    in_progress --> done: all agents signed_off\nmove to done/
    in_progress --> blocked: question-class blocker\nuser resolves
    blocked --> in_progress: user resolves +\n/build-feature resumes
    todo --> rejected: explicitly cancelled
    inbox --> rejected: explicitly cancelled

    inbox: 00_inbox/\n(proposed)
    todo: 01_todo/\nor EPIC-*/\n(active)
    in_progress: in_progress\n(ticket-supervisor driving)
    done: done/\n(all agents signed_off)
    blocked: blocked\n(awaiting user input)
    rejected: 99_rejected/\n(cancelled)
```

## Folder Structure

```mermaid
graph TD
    T[tickets/] --> I[00_inbox/\nProposed tickets\nand epics]
    T --> TO[01_todo/\nActive tickets\nand EPIC-*/ folders]
    T --> D[99_done/\nCompleted standalone tickets]
    T --> R[99_rejected/\nCancelled tickets]
    T --> TPL[templates/\nTicket and epic templates]

    TO --> EP[EPIC-Name/\nMaster_Plan.md\n01_sub.md...\ndone/\n99_done/]
    I --> EPI[epics/\nEPIC-Name/\nMaster_Plan.md\nsub-tickets]
```

## Agent Sign-off Sequence

```mermaid
flowchart LR
    N[needed] -->|agent runs, passes| SO[signed_off]
    N -->|agent runs, fails| F[failed]
    F -->|supervisor retries| N
    F -->|cap exhausted| B[blocked\nuser input needed]
    SO -->|all agents done| DONE[ticket done\nmove to done/]
    NN[not_needed] --> DONE
```

## Strict Workflow Rules

To maintain the integrity of the ticket lifecycle, the following rules apply:
- **No Untracked Code Changes**: Never change code without asking the user or having an explicit ticket assigned.
- **No Spontaneous Implementation**: If functionality is discovered missing during an epic, do not spontaneously implement it. Add new tickets for the missing features.
- **Lifecycle Integrity**: This ensures all changes properly trigger documentation updates, code splitting, architecture diagrams, and unit tests as mandated by the ticket lifecycle.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-22 [AI]: Added Strict Workflow Rules to enforce ticket-driven development and prevent untracked code modifications.
====================================================================
-->
