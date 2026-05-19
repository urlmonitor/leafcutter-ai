---
title: "Architecture Doc Frontmatter Reference"
type: reference
status: active
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
components: []
---

# Architecture Doc Frontmatter Reference

Every architecture doc in `docs/architecture/` requires YAML frontmatter between
`---` delimiters as its very first block. This file is the canonical reference for
every field, its allowed values, and when it is required.

> [!NOTE]
> The enum tables in this file are injected at build time from
> `leafcutter/config/doc_types.json`,
> `leafcutter/config/diagram_types.json` (if present), and
> `leafcutter/config/paths.json`. Do not edit the injected sections
> manually — re-run `build.py` to regenerate them.

## Required Fields (all architecture docs)

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Human-readable document title. Noun phrase for diagrams; "Decision: X" not allowed for ADRs — use a noun phrase there too. |
| `type` | enum | Document type. See **Doc Type Enum** below. |
| `status` | enum | `active` \| `draft` \| `deprecated` \| `migrating` |
| `created` | date | ISO 8601 date the document was first authored (`YYYY-MM-DD`). |
| `last_updated` | date | ISO 8601 date of the most recent substantive edit. |
| `components` | list | Component IDs from `docs/components.json`. Must be a registered ID — do not invent tokens. |

## Fields for Diagram Docs (architecture type)

| Field | Type | Required? | Description |
|-------|------|-----------|-------------|
| `flight_level` | enum | Yes | C4 zoom level. See **Flight Level Enum** below. |
| `diagram_type` | enum | Yes | Nature of the diagram. See **Diagram Type Enum** below. |
| `parent` | string\|null | Yes | Path to the parent diagram (one zoom level up), or `null` for the root. |
| `children` | list | Yes | Paths to child diagrams (one zoom level down). `[]` when none. |
| `root` | bool | No | `true` only on the single L1 system-context doc. Omit or `false` on all others. |
| `related_adrs` | list | No | Paths to ADRs that govern this diagram. Bidirectional — the ADR must list this file in `affects_diagrams`. |
| `related_code` | list | No | Source file paths that implement what this diagram describes. |
| `related_surfaces` | list | No | Observability surfaces (dashboards, metrics, traces) relevant to this diagram. |

## Fields for ADR Docs (adr type)

| Field | Type | Required? | Description |
|-------|------|-----------|-------------|
| `affects_diagrams` | list | Yes | Paths to architecture diagrams this ADR governs. `[]` when the ADR does not affect a diagram. Bidirectional — each listed diagram must list this ADR in `related_adrs`. |
| `related_docs` | list | No | Other ADRs, how-tos, or references that this decision cross-references. |
| `related_code` | list | No | Source file paths most directly affected by this decision. |

## Doc Type Enum

<!-- INJECT:DOC_TYPES_TABLE -->
| Value | Description |
|-------|-------------|
| `how_to` | Task-oriented procedure: "how do I do X?" Step-by-step, narrow scope. |
| `reference` | Lookup-oriented: API tables, schema dictionaries, configuration enums. Comprehensive and dry. |
| `explanation` | Understanding-oriented: "why does X work this way?" Discusses context, tradeoffs, history. |
| `tutorial` | Learning-oriented: hand-holds a beginner through a contained skill. |
| `adr` | Architecture Decision Record: captures a decision, its context, alternatives, consequences. |
| `architecture` | Descriptive architecture doc: system design, component diagram, data flow doc with Mermaid. |
| `retro` | Retrospective: post-epic learnings, blocker patterns, rule changes proposed. |
<!-- END:DOC_TYPES_TABLE -->

## Flight Level Enum

| Value | C4 Level | Description |
|-------|----------|-------------|
| `L1-Context` | System Context | The system as a black box, with external actors and systems. One per project. |
| `L2-Container` | Container | Services, databases, message queues, and the relationships between them. |
| `L3-Component` | Component | Modules and packages within a single container. |
| `L4-Code` | Code | Class-level UML (rarely used; prefer ADRs for design decisions). |

## Diagram Type Enum

| Value | When to use |
|-------|-------------|
| `context` | L1 system-context diagrams showing external actors. |
| `container` | L2 container diagrams showing services and infrastructure. |
| `component` | L3 component diagrams showing modules within one container. |
| `sequence` | Temporal message-passing flows between participants. |
| `erd` | Entity-relationship diagrams for data models. |
| `state` | State-machine diagrams for event-driven logic. |
| `dataflow` | Data-pipeline or event-stream flow diagrams. |
| `none` | For architecture docs without a Mermaid diagram (prose-only). |

## Paths Reference

Architecture docs may reference folder locations using `{paths.<group>.<key>}` placeholder
syntax. The canonical values are resolved from `leafcutter/config/paths.json`
at build time. Common paths:

| Placeholder | Resolves to |
|-------------|-------------|
| `{paths.docs.architecture}` | `docs/architecture/` |
| `{paths.docs.architecture_adrs}` | `docs/architecture/adrs/` |
| `{paths.docs.root}` | `docs/` |
| `{paths.package.root}` | `leafcutter/` |

For the full list of registered paths, run:

```bash
python leafcutter/scripts/path_resolver.py --list
```

## See Also

- `README.md` — architecture folder overview and conventions
- `adrs/ADR-template.md` — template for new ADRs
- `adrs/README.md` — ADR folder guide
