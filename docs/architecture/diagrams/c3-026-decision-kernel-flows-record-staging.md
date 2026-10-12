---
title: "Decision Record Staging — From the Decision Executor to the Staged Record and the Publish Notice"
description: "L3 sequence of staging a decision record as built on main: the decision executor detects a resolved decision, the record builder builds the record and refuses it unless a human approved it, the file backend writes it under the run folder, and the completed run tells you the staged path and the publish command through the /leafcutter skill. The no-approval exit stages nothing, and no participant writes to the repository."
type: architecture
flight_level: L3-Component
diagram_type: sequence
status: draft
parent: docs/architecture/diagrams/c2-007-decision-kernel-flows-overview.md
created: 2026-10-10
last_updated: 2026-10-10
source_ticket: "tickets/00_inbox/TICKET-20261010-DecisionLifecycleDocs.md"
components:
  - decision_kernel
related_diagrams:
  - docs/architecture/diagrams/c3-025-decision-kernel-flows-decision-states.md
  - docs/architecture/diagrams/c3-027-decision-kernel-flows-record-publishing.md
  - docs/architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md
related_docs:
  - docs/architecture/components/decision-kernel.md
  - docs/architecture/components/colony-memory.md
  - docs/architecture/diagrams/c3-014-decision-kernel-flows-request-handoff.md
  - docs/architecture/diagrams/c3-020-decision-kernel-flows-learning-loop.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/product-truth/flows/leafcutter/decision-staging.flow.json
  - docs/how-to/file-and-reuse-decisions-with-the-kernel.md
related_code:
  - kernel/capabilities/decision/executor.py
  - kernel/capabilities/decision/publish_command.py
  - kernel/memory/staging.py
  - kernel/memory/builder.py
  - kernel/memory/file_store.py
  - kernel/adapters/claude_code/SKILL.md
tags:
  - decision-kernel
  - decision-lifecycle
  - decision-store
---

# Decision Record Staging — From the Decision Executor to the Staged Record and the Publish Notice

When a decision resolves, the kernel files what you approved as a record, but only inside the
run's own folder. This page shows that hand-off (DK-600c-1 to DK-600c-4). Publishing the record
into `docs/decisions/` is a separate command that a person runs
([Record publishing](c3-027-decision-kernel-flows-record-publishing.md)).

**Status: built on main.** [Request Flow 2](c3-014-decision-kernel-flows-request-handoff.md)
shows the run around this hand-off: finalize, the envelope and the skill. The
[learning loop](c3-020-decision-kernel-flows-learning-loop.md) shows where the record goes next.
This page draws only the staging messages.

```mermaid
sequenceDiagram
    autonumber
    participant DEC as Decision executor
    participant RB as Record builder
    participant FB as File backend (ColonyMemory)
    participant SK as /leafcutter skill (Claude Code)
    actor U as You

    Note over DEC: _stage - a completed result with a resolved decision (resolved gate, your ranked choice, or a precedent reuse)
    DEC->>RB: stage_decision_record, then build_decision_record with options, criteria, evidence refs, ranking, precedents, provenance
    alt no human approval - resolved by the host alone, approved_by not a human, or no approved_at
        RB-->>DEC: refused by builder._approval (NotApproved, a record is never self-authorized)
        Note over DEC: staging returns None, the result is unchanged - no staged path, no publish command
    else a human approved the resolved decision
        RB-->>DEC: DecisionRecord - evidence as locators and content hashes, no evidence text
        DEC->>FB: stage_decision(record) through the ColonyMemory port
        FB->>FB: write runs/RUN/staged/decisions/DEC-ID.yaml under the run root
        FB-->>DEC: StagedRecord with the decision id and the path
        DEC->>DEC: add the limitation - decision record staged, the path, the folder publish writes into, the publish command
    end
    DEC-->>SK: completed RunEnvelope with its limitations (finalize, RunService and CLI, see c3-014)
    SK->>U: the record is ready, where publish will write it, and the publish command
    Note over SK,U: the skill shows the command but never runs it. No participant writes docs/decisions during a run
```

Parent: [Decision Kernel and Colony Memory — Design Map](c2-007-decision-kernel-flows-overview.md)

See also: [Record publishing](c3-027-decision-kernel-flows-record-publishing.md) (the next step)
and [Record lifecycle](c3-028-decision-kernel-flows-record-lifecycle.md) (the record's states).

## Notes per step

Step numbers are the diagram's message numbers.

| Step | What the code does | Where |
|---|---|---|
| Note, 1 | `_stage` runs for every completed decision result. A resolved decision reaches it from the resolved gate (`_combine`), from your ranked choice (`_load`) or from a precedent reuse (`_reuse_precedent`) | `kernel/capabilities/decision/executor.py` |
| 2 | `_approval` refuses unless the decision is `resolved` with a selected option, `approval_status` is `approved`, `approved_by` is a human (`human` or `human:<id>`), and `approved_at` is set. An actor id naming a host, Jev, a service or a model is never treated as a human (`human_actor`). The refusal is logged at info level and never fails the decision | `kernel/memory/builder.py`, `kernel/memory/staging.py` |
| 3 | The record holds evidence as references (`evidence_ref`): id, locator, category, content hash, verification and source version. No evidence text is copied | `kernel/memory/builder.py` |
| 4–6 | `FileColonyMemory.stage_decision` writes under the run root, never under the repository. A write failure returns None and the decision still completes. With `memory.backend: null`, `NullColonyMemory` stages nothing | `kernel/memory/file_store.py`, `kernel/memory/port.py` |
| 7 | The limitation reads `decision record staged: <path>; publish writes it into <folder> (the kernel checkout); publish it for review with: <command>`. The command names the interpreter the kernel runs under and `scripts/run_kernel.py`, so it runs as printed from any shell | `kernel/capabilities/decision/publish_command.py` |
| 8–9 | The skill reports the completed run. When a limitation names a staged record, it tells you the record is ready and shows the command. It must not run it: `decisions publish` is yours to run | `kernel/adapters/claude_code/SKILL.md` |

The staged file sits at `<run_root>/runs/<run_id>/staged/decisions/<dec-id>.yaml`. The run root
defaults to `.leafcutter/kernel/`. Later runs look up precedent only through the published index
in `docs/decisions/`, so a record that stays staged is never found as precedent
([Record lifecycle](c3-028-decision-kernel-flows-record-lifecycle.md)).

## Legend

| Element | Meaning |
|---|---|
| `participant` | A part of the kernel or the client that takes part in staging |
| `actor` | You, the person who reads the notice |
| Solid arrow | A call or a message |
| Dashed arrow | A returned result |
| Self-arrow | Work done inside one participant |
| `alt` block | The two exclusive outcomes: refused, or staged |
| `autonumber` | The message numbers used in "Notes per step" |
| `Note` | What a participant decides, or a rule that holds on every path |

## Cross-Links

- Parent: [Decision Kernel and Colony Memory — Design Map](c2-007-decision-kernel-flows-overview.md)
- Containers: [Decision Kernel — Container Overview](../components/decision-kernel.md),
  [Colony Memory — Container Overview](../components/colony-memory.md)
- The run around it: [Request Flow 2](c3-014-decision-kernel-flows-request-handoff.md)
- Siblings: [Decision states](c3-025-decision-kernel-flows-decision-states.md),
  [Record publishing](c3-027-decision-kernel-flows-record-publishing.md),
  [Record lifecycle](c3-028-decision-kernel-flows-record-lifecycle.md)
- Decision: [ADR-060](../adrs/ADR-060-source-of-truth-and-approval-authority.md) (only a human
  approval creates a record; the kernel never writes the repository during a run)
- Product truth: [decision-staging flow](../../product-truth/flows/leafcutter/decision-staging.flow.json)
- Doing it: [How to file and reuse decisions with the kernel](../../how-to/file-and-reuse-decisions-with-the-kernel.md)

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-10 [architecture-diagram-author, TICKET-20261010-DecisionLifecycleDocs]:
  Initial creation (DK-600c-5-ii). Scaffold-free pass authorised by the user
  in decision dec-b10271ebb40b9eaa (approved 2026-10-10, the standing pass
  for every blocked diagram until a scaffold exists). The scaffold
  scripts/scaffold/new_arch_doc.py that write-c4-diagram step 4 requires is
  missing from this repository, so the frontmatter and the Legend were
  authored by hand under that authorisation. The frontmatter takes the shape
  of the sibling L3 sequence diagram c3-014. The Legend has one entry per
  notation element used here. No skill text was edited.
====================================================================
-->
