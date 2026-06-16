---
title: "AC Authoring Pipeline — Sequence Diagram"
type: architecture
status: active
created: 2026-06-05
last_updated: 2026-06-05
flight_level: L2
parent: agent_delivery_workflows.md
components:
  - ac-store
  - ticket-creation
related_docs:
  - docs/architecture/diagrams/ac-readiness-states.md
  - docs/architecture/diagrams/build-ac-flow.md
  - docs/architecture/diagrams/ac-driven-pipeline.md
  - docs/how-to/ac-driven-development.md
---

# AC Authoring Pipeline — Sequence Diagram

This diagram shows how a new feature request moves through the three-agent
authoring pipeline — `product-owner`, `business-analyst`, and
`it-po` — before an AC reaches the User for final approval and the
scanner can pick it up.

The readiness state written to each AC YAML at each step is annotated in
square brackets alongside the arrow label.

---

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant PO as product-owner
    participant BA as business-analyst
    participant ITPO as it-po

    User->>PO: Describe feature / new capability
    Note over PO: Writes L0 and L1 AC YAML files<br/>Sets readiness: draft, priority: medium<br/>Includes documentation_triggers on L1 ACs

    PO-->>User: L0/L1 draft ACs [readiness: draft]

    User->>BA: Forward L1 ACs with documentation_triggers
    Note over BA: Decomposes L1 into L2/L3 behavioural ACs<br/>Sets readiness: draft on all new ACs<br/>Inherits priority from parent<br/>Produces documentation ACs for each trigger type

    BA-->>ITPO: L2/L3 draft ACs + documentation ACs [readiness: draft]

    Note over ITPO: Enriches ACs with technical fields:<br/>assigned_agent, estimated_complexity<br/>delivers_to / expects_from<br/>Checks documentation coverage gate<br/>Sets readiness: reviewed when gate passes

    ITPO-->>User: Reviewed ACs [readiness: reviewed]

    Note over User: Inspects ACs; may edit priority<br/>Promotes each approved AC manually<br/>or via /build-ac prompt
    User-->>User: Sets readiness: approved, confirms priority
    Note over User: Scanner (scan_ac_store.py) may now<br/>pick up ACs with readiness: approved
```

---

## Readiness State at Each Stage

| Stage | Actor | readiness written |
|---|---|---|
| L0/L1 authoring | product-owner | `draft` |
| L2/L3 decomposition + doc ACs | business-analyst | `draft` |
| Technical enrichment | it-po | `reviewed` |
| User approval | User | `approved` |
| Ticket built and merged | mark_ac_done.py | `done` |

Only ACs with `readiness: approved` are visible to the scanner. ACs at
`draft` or `reviewed` are excluded from ticket generation entirely.

---

## documentation_triggers Flow

When `product-owner` sets a non-empty `documentation_triggers` field on
an L1 AC, `business-analyst` must produce a documentation AC for each
trigger type:

| Trigger value | Documentation AC assigned_agent |
|---|---|
| `how-to` | `documentation-expert` |
| `sequence-diagram` | `architecture-diagram-author` |
| `state-diagram` | `architecture-diagram-author` |
| `component-diagram` | `architecture-diagram-author` |
| `reference-doc` | `reference-author` |

`it-po` will not promote a batch to `reviewed` unless all triggered
documentation ACs are present.

---

## Cross-References

- [AC readiness state machine](ac-readiness-states.md) — stateDiagram-v2
  for all five states and their transitions.
- [/build-ac execution flow](build-ac-flow.md) — what happens after an AC
  reaches `approved`.
- [AC-driven pipeline component diagram](ac-driven-pipeline.md) — all
  scripts and data flows end-to-end.
- [How to use the AC-driven development system](../../how-to/ac-driven-development.md) — task-oriented guide.
