---
title: "Knowledge System — Cross-Session Learning Persistence"
description: "Knowledge harvesting and context file maintenance system that persists learnings across agent sessions for improved future-invocation quality."
flight_level: L3-Component
diagram_type: component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-22
components:
  - knowledge_system
  - knowledge_system
---

# Knowledge System

## Overview

The Knowledge System captures learnings discovered during ticket execution and routes them to persistent storage so future agent invocations benefit from prior experience. It is the implementation of the post-execution knowledge capture described in the Agent Knowledge System architecture.

## Knowledge-Map Surfaces

The knowledge map is the cross-surface knowledge graph assembled by
`scripts/knowledge_query.py` from every surface declared in
`config/paths.json`. Each declared surface contributes nodes and edges to the
map. The **acceptance-criteria store** (`docs/acceptance-criteria/`, declared as
the `acs` surface) is one such surface, feeding the map alongside the other
declared surfaces (agents, skills, tickets, docs, ADRs, hooks, and any further
surfaces added to `paths.json`). New surfaces are picked up from configuration —
the map is not built against a fixed surface count.

The diagram below focuses on the acceptance-criteria store's contribution. An
acceptance criterion contributes four kinds of relationship edge into the map:

- **`implemented_by`** → the source files that implement the criterion.
- **`covered_by`** → the tests that cover the criterion.
- **`depends_on`** → the other acceptance criteria it depends on.
- **`component_membership`** (from its `components` field) → the component hub
  nodes it belongs to.

```mermaid
C4Component
    title Knowledge Map — Acceptance-Criteria Store as a Surface

    Container_Boundary(map, "Knowledge Map (knowledge_query.py)") {
        Component(acs, "Acceptance-Criteria Store", "acs surface — docs/acceptance-criteria/", "Each AC file contributes one node and its relationship edges.")
        Component(others, "… other declared surfaces", "agents, skills, tickets, docs, ADRs, hooks, … (read from config/paths.json)", "Additional surfaces feed the same map; the set is open-ended.")
        Component(srcfiles, "Source File Nodes", "implemented_by targets", "Files that implement a criterion.")
        Component(tests, "Test Nodes", "covered_by targets", "Tests that cover a criterion.")
        Component(hubs, "Component Hub Nodes", "component_membership targets", "Shared hubs that transitively connect surfaces.")
    }

    Rel(acs, srcfiles, "implemented_by")
    Rel(acs, tests, "covered_by")
    Rel(acs, acs, "depends_on (AC → AC)")
    Rel(acs, hubs, "component_membership")
    Rel(others, hubs, "feed the same map")
```

Parent: [Agent Knowledge System](../agent_knowledge_system.md)

## Requirement-to-Code Traversal

The sequence diagram below shows how a reader follows a single acceptance
criterion from its identifier to the source files and tests that deliver it.
The traversal is driven by `knowledge_query.py`, which reads `config/paths.json`
to discover all surfaces, indexes their nodes and edges in one pass, and then
resolves the four outbound edge kinds an AC node can carry.

```mermaid
sequenceDiagram
    autonumber
    actor Reader
    participant paths as config/paths.json
    participant kq as knowledge_query.py
    participant acs as AC Store<br/>(docs/acceptance-criteria/)
    participant src as Source File Nodes<br/>(implemented_by targets)
    participant tests as Test Nodes<br/>(covered_by targets)
    participant deps as Sibling AC Nodes<br/>(depends_on targets)
    participant hubs as Component Hub Nodes<br/>(component_membership targets)

    Reader->>kq: name a criterion (e.g. KM-EX-010)
    kq->>paths: load_surfaces_with_meta()
    paths-->>kq: surface registry<br/>(path + edge_fields per surface)

    Note over kq,acs: Build the map — one pass over all surfaces

    kq->>acs: glob **/*.yaml, parse each AC node
    acs-->>kq: NodeRecord(id, surface="acs", title, description, path)
    kq->>kq: extract_edges() for each AC node<br/>using edge_fields=[implemented_by, covered_by,<br/>depends_on, components]

    Note over kq: Resolve the four edge kinds<br/>for the named criterion

    kq->>src: edge_type="implemented_by"<br/>→ file-path targets (exempt from phantom filter)
    src-->>kq: source files that deliver the criterion

    kq->>tests: edge_type="covered_by"<br/>→ file-path targets (exempt from phantom filter)
    tests-->>kq: test files that prove the criterion

    kq->>deps: edge_type="depends_on"<br/>→ sibling AC node IDs (stem-resolved)
    deps-->>kq: predecessor criteria this one depends on

    kq->>hubs: edge_type="component_membership"<br/>→ component hub node IDs
    hubs-->>kq: component hubs the criterion belongs to

    kq-->>Reader: "Which code file delivers KM-EX-010?"<br/>→ implemented_by edges → source file paths
```

### Reading the diagram

| Step | What happens |
|------|--------------|
| 1–2 | The reader names a criterion; `knowledge_query.py` loads `config/paths.json` to discover all surfaces and their `edge_fields`. |
| 3–5 | `knowledge_query.py` traverses the `acs` surface (`docs/acceptance-criteria/`), yields one `NodeRecord` per `.yaml` file, and calls `extract_edges()` with the four declared edge fields. |
| 6–7 | `implemented_by` edges are emitted; targets are file paths (not graph node IDs) and are therefore **exempt from the phantom-edge filter** — they are never silently dropped even when the path is not itself a knowledge-graph node. |
| 8–9 | `covered_by` edges are emitted; same phantom-filter exemption applies. |
| 10–11 | `depends_on` edges are emitted; path values are stem-resolved to bare AC IDs before becoming `target_id` values. |
| 12–13 | `component_membership` edges are emitted; `components` field values become hub node IDs (synthetic hub nodes are created for any component that has no existing node). |
| 14 | The reader's question — "which code file delivers this criterion?" — is answered by reading the `implemented_by` edge targets from the indexed graph. |

## Responsibilities

- Harvest learnings from agent sign-off sessions via `harvest_learnings.py`
- Maintain context files that agents receive at invocation time
- Route new learnings to the appropriate knowledge surface

## Entry Points

- `scripts/knowledge/harvest_learnings.py` — learning harvester
- `scripts/knowledge/context_file_maintenance.py` — context file updater
- `scripts/knowledge/init_component_readme.py` — component README seeder

## Integration

The signoff skill §7 Knowledge Capture Step invokes the `route-learning` and `capture-learning` skills, which ultimately persist entries that `harvest_learnings.py` consolidates across sessions.

The acceptance-criteria store feeds the knowledge map via the `acs` surface declared in `config/paths.json`; surface declaration is implemented in ticket `KM-KGS-100a-1` and the four relationship-edge kinds in `KM-KGS-100a-3`.

## Cross-Links

- Parent: [Agent Knowledge System](../agent_knowledge_system.md) — the L2 container view of how learnings are classified, routed, and persisted.
- [Knowledge Query skill](../../../templates/skills/knowledge-query/SKILL.md) — the cross-surface query/skill that reads the surfaces feeding the knowledge map.

## Legend

| Element | Meaning |
|---|---|
| `Container_Boundary` | The knowledge map assembled by `knowledge_query.py` |
| `Component` (acs surface) | The acceptance-criteria store feeding the map |
| `Component` (other surfaces) | Any further surface declared in `config/paths.json`; the set is open-ended |
| `Rel` labels (`implemented_by`, `covered_by`, `depends_on`, `component_membership`) | The four relationship-edge kinds an acceptance criterion contributes |
| Self-loop `depends_on (AC → AC)` | An edge from one acceptance criterion to another |
