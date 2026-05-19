---
title: "Agent Reference: architecture-author"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "docs/how-to/documentation/write-architecture-doc.md"
  - "tickets/09_done/EPIC-CodingAgents/23_architecture_author.md"
  - "tickets/09_done/EPIC-CodingAgents/20_documentation_expert.md"
related_code:
  - ".claude/agents/architecture-author.md"
---

# Agent Reference: `architecture-author`

Implementing agent: `architecture-author` (Sonnet, internal).
Family: `coding/` — dispatched by `documentation-expert`.

This doc explains when the agent is dispatched, what it expects as input, what it produces, how it delegates research, and where the authoring rules live.

---

## 1. When It Is Used

`documentation-expert` dispatches `architecture-author` when it classifies the request as **"design / data flow / component"** — the descriptive architecture genre. The key distinction:

| If the request says... | Genre | Specialist |
|---|---|---|
| "document how X works" / "describe the data flow for Y" / "draw the component diagram for Z" | Descriptive architecture | `architecture-author` (this agent) |
| "record the decision to adopt X" / "write an ADR for Y" | Decision record (ADR) | `adr-author` |

Do **not** invoke `architecture-author` directly. It is an internal agent. `documentation-expert` is the only caller.

---

## 2. Inputs

`documentation-expert` passes a description spec. Required fields:

| Field | Description |
|---|---|
| `subject` | The system, component, data flow, or pipeline to describe |
| `scope` | Which services / layers / phases to cover |
| `target_folder_hint` | Optional: `docs/architecture/` or a topical folder path |
| `audience_hint` | Optional: `cross-cutting` vs `domain-specific` |

If a required field is missing and cannot be inferred from context, `architecture-author` asks one clarifying question before proceeding.

---

## 3. Outputs

The agent returns a structured payload:

| Field | Description |
|---|---|
| `file_path` | Absolute path of the architecture doc written |
| `diagram_files` | List of `.mmd` companion files written (empty if all diagrams are inline) |
| `location_decision` | One sentence: which location rule (section 1 of the how-to) was applied |
| `adr_links` | List of ADRs cross-linked in the document |
| `open_questions` | Any follow-up items (e.g. "a decision record may also be needed") |

---

## 4. How It Delegates Research

`architecture-author` does not carry `Grep`, `Glob`, or MCP search tools (strict-research-delegation rule — `docs/agents/conventions.md §4.2`). All cross-file lookups — what tables a procedure touches, what ADRs govern the subject, what workers call a function — go through `research-agent` via the `Agent` tool.

Spawn depth: `documentation-expert (depth N)` → `architecture-author (depth N+1)` → `research-agent (depth N+2)`. The soft cap of 3 applies; `architecture-author` must not spawn further sub-agents beyond `research-agent`.

---

## 5. Authoring Rules

The agent loads `docs/how-to/documentation/write-architecture-doc.md` before writing. That how-to is the single source of truth for:

- **Location decision** (§1): `docs/architecture/` vs topical folder, with a decision table and concrete examples.
- **Filename convention** (§2): snake_case; `.mmd` + `.svg` companion pairs for large diagrams.
- **Frontmatter** (§3): required YAML fields (`type: "reference"`, `status`, `components`, `related_docs`).
- **Section order** (§4): Purpose → High-Level Overview → per-component detail → Key Design Principles (optional) → Cross-References → Decision History.
- **Diagram conventions** (§5): Mermaid inline vs `.mmd` file; `classDef` colour coding; `subgraph` grouping; `> [!IMPORTANT]` callouts.
- **Terminology rules** (§6): service / worker / procedure / function / component / container — canonical meanings codified against existing files.
- **Cross-linking** (§7): ADRs via `> [!TIP]` callout blocks; related docs via Cross-References bullet list; code objects via Markdown links to source files.
- **Skeleton** (§8): copy-pasteable template covering all required sections.

---

## 6. Refusal Behaviour

`architecture-author` refuses and returns a structured error if the request is a decision record rather than a description (signals: "we will adopt X", "decide between A and B", "record why we chose"). The error instructs `documentation-expert` to re-route to `adr-author`.

---

## 7. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1), file layout (§2), visibility classes (§3), tool allowlists (§4), strict-research-delegation (§4.2).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) — upstream policy: three-tier ladder (§2.1), tool allowlist (§2.6), nesting depth (§2.7).
- [`docs/how-to/documentation/write-architecture-doc.md`](../../how-to/documentation/write-architecture-doc.md) — the how-to this agent loads at runtime; the single source of truth for architecture-doc conventions.
- [`.claude/agents/architecture-author.md`](../../../.claude/agents/architecture-author.md) — the agent file itself.
- [`tickets/09_done/EPIC-CodingAgents/23_architecture_author.md`](../../../tickets/09_done/EPIC-CodingAgents/23_architecture_author.md) — the ticket that shipped this agent.
- [`tickets/09_done/EPIC-CodingAgents/20_documentation_expert.md`](../../../tickets/09_done/EPIC-CodingAgents/20_documentation_expert.md) — the orchestrator that dispatches to this agent.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
