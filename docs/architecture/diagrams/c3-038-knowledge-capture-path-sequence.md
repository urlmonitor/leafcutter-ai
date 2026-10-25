---
title: "Knowledge Capture Path — Sequence Diagram"
description: "L3 sequence diagram of the knowledge-capture path end to end: a phase agent at the signoff §7 step, emit_knowledge.py, the knowledge-emission sink, emit_event.py and the operational telemetry stream; the success, cannot-complete and nothing-to-record branches; and the boundary where the agent's obligation ends and the routing step begins."
type: architecture
diagram_type: sequence
flight_level: L3-Component
status: draft
parent: docs/architecture/agent_knowledge_system.md
created: 2026-10-25
last_updated: 2026-10-25
source_ticket: "tickets/00_inbox/epics/EPIC-ALearningAnAgentHasTodayActuallyGets/07_TICKET-20261016-INF-700b-4.md"
components:
  - knowledge_system
  - infrastructure
related_docs:
  - docs/architecture/agent_knowledge_system.md
  - docs/architecture/adrs/ADR-034-knowledge-write-ownership.md
  - docs/architecture/components/knowledge-system.md
  - docs/reference/knowledge-routing-step.md
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-4.yaml
tags:
  - knowledge-capture
  - INF-700b-4
---

# Knowledge Capture Path — Sequence Diagram

This page follows one phase agent through the `signoff` §7 knowledge-capture step,
from the end of its sign-off to the record that step leaves behind. It shows the
three branches the step can take and where each one leaves its trace. The field
table, the capture-attempt outcomes and the routing paths are in the parent
[Agent Knowledge System](../agent_knowledge_system.md) reference.

> **Two streams, two artefacts.** A learning ends as a `knowledge_captured` record in
> the knowledge-emission sink. A capture that cannot complete ends as a `failed`
> `capture_attempt` record on the operational telemetry stream. Nothing that failed
> is written to the sink.

```mermaid
sequenceDiagram
    autonumber
    participant PA as Phase agent
    participant S7 as signoff §7<br/>knowledge-capture step
    participant EK as scripts/knowledge/<br/>emit_knowledge.py
    participant SINK as knowledge-emission sink<br/>(knowledge_emission_sink)
    participant EE as templates/skills/agent-telemetry/<br/>scripts/emit_event.py
    participant TEL as operational telemetry stream<br/>(operational_telemetry_stream)
    participant HV as harvest_learnings.py<br/>(knowledge-harvester agent)
    participant HR as capture_health_report.py

    PA->>S7: atomic sign-off written (signoff §2)
    S7-->>PA: did you learn something future-you would have needed at the start?
    alt Success path: a learning to record
        PA->>EK: one command with --agent --component --destination --entry-kind --text
        EK->>SINK: append one knowledge_captured record carrying text
        EK->>EE: --event capture_attempt --outcome recorded
        EE->>TEL: capture_attempt record, outcome recorded
    else Cannot-complete path: the learning could not be recorded
        alt emit_knowledge.py exited non-zero (missing script 2, crash or import error 1)
            PA->>EK: the same one command
            EK-->>PA: non-zero exit, nothing appended to the sink
            PA->>EE: the "Failed capture attempt" command (agent-telemetry SKILL.md)
            EE->>TEL: capture_attempt record, outcome failed, missing_target = the emit_knowledge.py path
        else the sink append failed (OSError)
            PA->>EK: the same one command
            EK->>EE: --event capture_attempt --outcome failed --missing-target &lt;sink path&gt;
            EE->>TEL: capture_attempt record, outcome failed, missing_target = the sink path
            EK-->>PA: exit 0 with a warning, so the agent adds no record
        end
        Note over SINK,TEL: An incomplete capture leaves its trace here: one failed record on the telemetry stream, no knowledge record in the sink
    else Nothing to record
        PA->>EE: the "Nothing-to-record capture attempt" command (agent-telemetry SKILL.md)
        EE->>TEL: capture_attempt record, outcome nothing-to-record
    end

    Note over PA,TEL: The agent's obligation ends here (ADR-034). It does not classify the learning, pick a surface or write to one.
    rect rgba(128, 128, 128, 0.12)
        Note over SINK,HV: Routing step begins here. This diagram does not say when it runs (manual invoke, or wired on some routes, see the parent's §4)
        HV->>SINK: read knowledge_captured records
        HV->>HV: set aside records without usable text, write each other record to its destination knowledge surface
    end
    HR->>TEL: read capture_attempt records for a --since / --until window
    HR->>HR: one verdict per period (capture-path-broken on any failed attempt)
```

Parent: [Agent Knowledge System](../agent_knowledge_system.md)

<!-- Doc Links:
- docs/architecture/agent_knowledge_system.md
Doc Links end: read by check_doc_links.py -->

## Walk-through

1. **The step.** After the atomic sign-off write (`signoff` §2), the agent runs the
   `signoff` §7 knowledge-capture step and asks whether it learned something
   future-it would have needed at the start.
2. **Success.** The agent runs `emit_knowledge.py` as one command. The helper appends
   one `knowledge_captured` record carrying `text` to the knowledge-emission sink, then
   runs `emit_event.py` once to write a `recorded` capture attempt. The agent never
   writes `recorded` itself.
3. **Cannot complete, agent side.** When the `emit_knowledge.py` command exits
   non-zero, nothing reached the sink. The agent runs the `Failed capture attempt`
   command from the `agent-telemetry` skill, and `missing_target` is the
   `emit_knowledge.py` path it tried to run.
4. **Cannot complete, helper side.** When the sink append fails, the helper writes the
   `failed` attempt itself, with `missing_target` set to the sink path, and exits `0`.
   The agent adds no second record, so each failure leaves at most one `failed`
   attempt.
5. **Nothing to record.** The agent runs the `Nothing-to-record capture attempt`
   command. No knowledge record is written.
6. **The boundary.** The agent's whole obligation is one command per branch. Writing a
   learning to its knowledge surface is the harvester's job, and this page does not
   say when that happens. The parent's §4 lists the routes that carry a routing step
   and the ones where the harvester is run by hand.
7. **The reader.** `capture_health_report.py` reads only the telemetry stream and gives
   one verdict per period. It does not read the sink.

If `agent-telemetry/SKILL.md` or its script cannot be read, no capture attempt can be
written and the failure stays on stderr and in the agent's sign-off comment (parent §3).

## Legend

| Element | Meaning |
|---|---|
| Participant box | One party on the path: the phase agent, the `signoff` §7 step, a script, a stream, or the harvester |
| Numbered solid arrow (`->>`) | A command run, a write or a read, in order |
| Dashed arrow (`-->>`) | A reply or an exit status going back |
| Arrow from a participant to itself | Work inside one script with no other party involved |
| `alt` / `else` block | Branches that exclude each other. Only one of them happens |
| `rect` block | The routing step, which starts where the agent's obligation ends |
| `Note over` | A fact about the step, or where a branch leaves its trace |

## Cross-Links

- Parent: [Agent Knowledge System](../agent_knowledge_system.md), with the record fields (§2), capture attempts (§3) and routing paths (§4)
- Decision: [ADR-034: Knowledge Write Ownership](../adrs/ADR-034-knowledge-write-ownership.md)
- Component page: [Knowledge System](../components/knowledge-system.md)
- Routing step: [Knowledge Routing Step](../../reference/knowledge-routing-step.md)
- Requirement: [INF-700b-4](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-4.yaml)

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-25 [architecture-diagram-author, INF-700b-4]: Initial creation.
  Placed in its own file because the parent reference was ~273 body lines and
  the diagram would have pushed it past the 300-line doc-length limit; the
  parent's reserved "Sequence Diagram" section links here. Number 038 from
  scripts/next_diagram_seq.py 3, re-checked against a freshly fetched
  origin/main. scripts/scaffold/new_arch_doc.py does not exist in this
  repository, so the frontmatter and Legend were written by hand following the
  shape of c3-036. Parent agent_knowledge_system.md is L2-Container, so the
  L3 child satisfies ARCH-LEVEL-ORDER; it lists this file in children:. Eight
  participants, 20 messages. Every name was checked against the package at
  this branch's head; the retired step names are not used.
====================================================================
-->
