---
title: "Decision Kernel Split — Components"
description: "L3 component view of splitting a bundled request, placed inside the kernel's existing containers: the new host operation host.decompose_goal beside the existing host.* handoffs; detection at routing and at a work item; the quote check that sets proposals aside; the person's split gate; the part scheduler; the run report's split section; and the split record in the run root with its links to the parts' staged decision records."
type: architecture
flight_level: L3-Component
diagram_type: component
status: draft
parent: docs/architecture/diagrams/c2-007-decision-kernel-flows-overview.md
created: 2026-10-10
last_updated: 2026-10-10
source_ticket: "tickets/00_inbox/epics/EPIC-ABundledRequestThatRoutingTurnsAwayIs/17_TICKET-20261006-DK-400c-4.md"
components:
  - decision_kernel
related_adrs:
  - ADR-067
related_docs:
  - docs/architecture/components/decision-kernel.md
  - docs/architecture/adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md
  - docs/reference/kernel-request-splitting.md
  - docs/reference/kernel-request-splitting-2-conversion-gate-runs-config.md
  - docs/architecture/diagrams/c3-014-decision-kernel-flows-request-handoff.md
  - docs/decisions/dec-b10271ebb40b9eaa.yaml
related_code:
  - kernel/scheduler/nodes_split.py
  - kernel/scheduler/nodes_route.py
  - kernel/scheduler/state.py
  - kernel/split/detect.py
  - kernel/split/convert.py
  - kernel/split/gate.py
  - kernel/split/text.py
  - kernel/contracts/split.py
  - kernel/capabilities/host/decompose_goal.py
  - kernel/service_envelope.py
  - kernel/memory/staging.py
  - config/capability_registry.json
tags:
  - decision-kernel
  - split
  - host-handoff
---

# Decision Kernel Split — Components

This page shows where each piece of a split sits among the kernel's existing containers, from
detecting a bundled request to the split record and the parts' decision records in the run root.

**Status: in progress, not on main.** The pieces without "planned" in their technology line are
built on the DK-400 E1 epic branch (DK-400a-1 to DK-400c-3). The pieces marked planned are
decided by [ADR-067](../adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md) and
built in later DK-400 epics. `split.enabled` stays false on main until DK-400e-1 turns it on
(ADR-067 §11), so a split does not reach a run on main yet.

The split adds no new container. Each piece is drawn inside one of the containers that
[Decision Kernel — Container Overview](../components/decision-kernel.md) already names.

```mermaid
C4Component
    title Decision Kernel Split — Components

    Person(person, "Person", "The only one who answers the split gate")
    Container(skill, "Claude Code or Codex skill + CLI", "kernel/adapters, python -m kernel", "Performs host.decompose_goal, relays the split gate, resumes the run")
    Container(svc, "RunService", "kernel/service.py", "Checks every submission before the graph moves, envelope carries splits")
    Container(jev, "Jev port", "langchain-typesafe", "Answers the bundle noul kernel.split.bundled")
    ContainerDb(reg, "Capability registry", "config/capability_registry.json", "host.decompose_goal entry: host_handoff, routing fixed, decision_ref ADR-067")

    Container_Boundary(sched, "Kernel scheduler") {
        Component(det_route, "Detection at routing", "nodes_split.SplitStep, kernel/split/detect.py", "Gates, then the bundle question. Triggers jev_none, ambiguous, bundled_accepted")
        Component(det_item, "Detection at a work item", "planned, DK-400b-2", "found_at mid_run, no trigger. Dormant: only a test producer reaches it")
        Component(convert, "Quote check and conversion", "kernel/split/convert.py", "Sets unquoted proposals aside, releases their dependants, counts, cuts to five")
        Component(gate, "Split gate", "kernel/split/gate.py, answer planned DK-400d-1", "HumanQuestion built from the record, answered with split_answer.v1")
        Component(parts, "Part scheduler", "planned, DK-400e-1", "Runs the approved parts one at a time in dependency order")
        Component(report, "Report split section", "finalize, planned DK-400f-2", "One line per part in report.md, taken from report_lines")
    }

    Container_Boundary(caps, "Capabilities: host.* handoffs") {
        Component(decompose, "host.decompose_goal", "kernel/capabilities/host/decompose_goal.py, new", "goal_decomposition_request.v1 in, goal_decomposition.v1 out. Allows propose_split only")
        Component(hosts, "Existing host handoffs", "kernel/capabilities/host/", "host.generate_options, host.synthesize, host.research, host.formulate_question, host.query_build")
    }

    Container_Boundary(rr, "Run root .leafcutter/kernel") {
        ComponentDb(record, "Split record", "Decomposition, leafcutter.decomposition.v1, checkpointed in splits", "dcp- id. State null until the proposal, then one of eight states")
        ComponentDb(staged, "Parts' staged decision records", "runs/RUN/staged/decisions, planned DK-400e-2", "One record per decided part. Decision.split_part derived from parts[].decision_id")
    }

    Rel(det_route, jev, "bundle noul rides the intent or routing batch")
    Rel(det_route, record, "checkpoints the record, state null")
    Rel(det_route, decompose, "parks the root on it: waiting_host")
    Rel(det_item, record, "starts a split, found_at mid_run")
    Rel(decompose, reg, "bound by its fixed-routing entry")
    Rel(skill, svc, "resume with goal_decomposition.v1 or split_answer.v1")
    Rel(svc, skill, "RunEnvelope waiting_host or waiting_human")
    Rel(svc, decompose, "refuses cycles, unknown ids, disallowed capabilities")
    Rel(decompose, convert, "accepted proposal")
    Rel(convert, record, "state proposed: parts, dropped, not_covered")
    Rel(convert, gate, "offered parts")
    Rel(gate, record, "built from the record, gate_answer, gate_by, gate_at")
    Rel(person, skill, "keeps, rewords, leaves out or rejects parts")
    Rel(svc, gate, "accepted split_answer.v1")
    Rel(gate, parts, "approved parts")
    Rel(parts, record, "each part's outcome and decision_id")
    Rel(parts, staged, "stages each decided part's record through stage_decision")
    Rel(record, staged, "parts[].decision_id links each record")
    Rel(report, record, "reads report_lines and decision_ids")
```

Parent: [Decision Kernel and Colony Memory — Design Map](c2-007-decision-kernel-flows-overview.md)

See also: [Request Flow 2 — Host or Human Handoff](c3-014-decision-kernel-flows-request-handoff.md)
for how any host handoff, `host.decompose_goal` included, is served and resumed. The order of the
split's steps over time is the subject of the DK-400c-5 sequence diagram (planned).

## Where each piece sits

| Piece | Inside container | Code | Status |
|---|---|---|---|
| `host.decompose_goal` | Capabilities, beside the five existing `host.*` handoffs | `kernel/capabilities/host/decompose_goal.py`; its entry in `config/capability_registry.json` accepts `leafcutter.goal_decomposition_request.v1` and produces `leafcutter.goal_decomposition.v1` | Built (DK-400a-1, DK-400c-1) |
| Detection at routing | Kernel scheduler, route node | `SplitStep` in `kernel/scheduler/nodes_split.py`; gates and threshold in `kernel/split/detect.py` | Built (DK-400a-1, DK-400a-1-i, DK-400a-2) |
| Detection at a work item | Kernel scheduler | None yet; `FoundAt.MID_RUN` exists in `kernel/contracts/split.py` | Planned (DK-400b-2); dormant, only an injected test producer reaches it (ADR-067 §11) |
| Refusing an unsound proposal | RunService submission check, through the host operation | `DecomposeGoal.submission_violations` calls `dependency_problems` and `capability_problems`; a refusal exits 3 and changes nothing | Built (DK-400c-1-ii) |
| Quote check and conversion | Kernel scheduler, route node (`open_gate`) | `convert_proposal` in `kernel/split/convert.py`; `normalize_text` in `kernel/split/text.py` | Built (DK-400c-1-i, DK-400c-2, DK-400c-3) |
| Split gate | Kernel scheduler | `gate_proposal` in `kernel/split/gate.py` | Question built (DK-400c-1). The `leafcutter.split_answer.v1` answer, keep, reword and leave out are planned (DK-400d-1) |
| Gate relay | Claude Code or Codex skill + CLI | `kernel/adapters/claude_code/SKILL.md`, `kernel/adapters/codex/SKILL.md` | Planned (DK-400d-1-ii) |
| Part scheduler | Kernel scheduler | None yet | Planned (DK-400e-1) |
| Report split section | Kernel scheduler, `finalize` | `report_lines` on the split record | Planned (DK-400f-2) |
| Split record | Run root, checkpointed state key `splits` | `Decomposition` in `kernel/contracts/split.py`; `splits` in `kernel/scheduler/state.py` | Built (DK-400a-1). DK-400d-1 and DK-400e-1 fill the gate fields and part outcomes |
| Parts' staged decision records | Run root, `runs/<run_id>/staged/decisions/` | The existing staging gate, `kernel/memory/staging.py` | Planned (DK-400e-2) |
| Envelope `splits` | RunService | `kernel/service_envelope.py` | Built (DK-400a-1). The progress block is planned (DK-400f-1) |

## The split record and the parts' decision records

The split record is `leafcutter.decomposition.v1`, one per split work item, with an id of `dcp-`
plus 16 hex digits derived from the work item. Detection checkpoints it in the run root before the
run returns `waiting_host`, so a resumed run never creates a second split.

- **States.** `state` is null while the host's proposal is awaited. After that it is one of the
  eight states: `proposed`, `approved`, `in_progress`, `completed`, `ended_partial`, `rejected`,
  `rejected_clarify` and `rejected_kept_whole` ([spec §4.3](../../reference/kernel-request-splitting.md#43-leafcutterdecompositionv1-the-split-record)).
  The run is `waiting_host` while the proposal is awaited and `waiting_human` while the gate is
  open.
- **Set-aside and cut parts.** A proposal whose quote is not a verbatim span of the subject moves
  to `dropped[]` and counts for nothing. Parts beyond the five-part cap or the run's part
  allowance move to `not_covered[]` (ADR-067 §5).
- **Links to the parts' decision records (planned, DK-400e-2).** Each decided part stages its own
  record through the existing staging gate, with the record schema unchanged. The part's
  `parts[].decision_id` names that record, `Decision.split_part` is derived from it, and the run
  envelope's `decision_ids` lists every decided part's record (ADR-067 §9). A person publishes
  each record with `python -m kernel decisions publish`, as for any staged record.

## Containers in this view

Every container drawn here is a row of the
[container overview](../components/decision-kernel.md#containers):

| Drawn as | Container overview row |
|---|---|
| Claude Code or Codex skill + CLI | Claude Code or Codex skill + CLI |
| RunService | RunService |
| Jev port | Jev port |
| Capability registry | Capability registry |
| Kernel scheduler (boundary) | Kernel scheduler |
| Capabilities: host.* handoffs (boundary) | Capabilities |
| Run root .leafcutter/kernel (boundary) | Run root |

The decision store does its staging inside the run root and is named only on the
`stage_decision` arrow. Observability is left out because the split adds no trace of its own
beyond its `split.*` run events.

## Legend

| Element | Meaning |
|---|---|
| `Person` | A human actor. Here, the person who answers the split gate |
| `Container` | A container of the kernel's container overview, drawn whole. Here: the skill and CLI, RunService and the Jev port |
| `ContainerDb` | A container that holds data. Here, the capability registry |
| `Container_Boundary` | A container of the kernel's container overview, opened to show the split's components inside it. Here: the kernel scheduler, the capabilities and the run root |
| `Component` | A split piece inside its container: the module or class in the technology line, then what it does |
| `ComponentDb` | Data held inside a container. Here, the split record and the parts' staged decision records in the run root |
| `Rel` arrow and label | A call, a hand-off or a data link, read from the source to the target |
| "planned" in a technology line | A piece that ADR-067 decides but that is not built yet, with the AC that builds it |

## Cross-Links

- Parent: [Decision Kernel and Colony Memory — Design Map](c2-007-decision-kernel-flows-overview.md)
- Containers: [Decision Kernel — Container Overview](../components/decision-kernel.md)
- Sibling: [Request Flow 2 — Host or Human Handoff](c3-014-decision-kernel-flows-request-handoff.md), the existing host handoffs
- Decision: [ADR-067](../adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md); full rules in the companion specification, [part 1](../../reference/kernel-request-splitting.md) and [part 2](../../reference/kernel-request-splitting-2-conversion-gate-runs-config.md)

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-10 [architecture-diagram-author, EPIC-ABundledRequestThatRoutingTurnsAwayIs/17]:
  Initial creation (DK-400c-4). Scaffold-free pass authorised by the user in
  decision dec-b10271ebb40b9eaa (approved 2026-10-10). The scaffold
  scripts/scaffold/new_arch_doc.py that write-c4-diagram step 4 requires is
  missing from this repository, so the frontmatter and the Legend were
  authored by hand under that authorisation. The frontmatter takes the shape of
  the existing L3 component diagrams (knowledge-management.md,
  self-heal-component.md) and the kernel siblings c3-013 to c3-022. The Legend
  has one entry per notation element used here; its general meanings follow
  the key of knowledge-management.md. No skill text was edited. INF-1300
  (TICKET-20261010-ScheduleArchDocScaffold) schedules the scaffold.
====================================================================
-->
