---
title: "Agent Reference: reference-author"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "docs/how-to/documentation/write-reference.md"
---

# Agent Reference: `reference-author`

Implementing agent: `reference-author` (Sonnet, internal).
Family: `coding/` — dispatched by `documentation-expert`.
Visibility: internal (invoked by `documentation-expert` only — never auto-triggers).

This doc explains **when `documentation-expert` dispatches here**, **what inputs
the agent expects**, **what it produces**, and **where reference docs land**.

---

## 1. When to Use (from documentation-expert's perspective)

`documentation-expert` dispatches to `reference-author` when it classifies the
user's request as Diataxis **"look up"** intent:

| User phrasing | Dispatched to |
|---|---|
| "write an API reference for X" | `reference-author` |
| "document the schema of table Y" | `reference-author` |
| "create a parameter reference for the config keys" | `reference-author` |
| "document this enum / glossary / column list" | `reference-author` |
| "I need a lookup table for Z" | `reference-author` |

Do **not** invoke `reference-author` directly. It is internal. The user entry
point is `documentation-expert` (via `/documentation` or prose intent matching).

---

## 2. Inputs

`documentation-expert` passes a structured reference spec block:

```
Subject: <what is being documented — table name, API, parameter set, config key, etc.>
Content type: <schema | api | glossary | config | enum | other>
Existing location hint: <optional — "probably docs/database/" or "probably docs/reference/">
Source material: <file paths or raw content to draw from>
Related explanation doc: <path if it exists, or "none">
Related how-to doc: <path if it exists, or "none">
```

All six fields are consumed by the agent's execution loop. `Source material` is
the primary research input — the agent reads the listed files and uses their
content as the factual basis for the reference doc. It does not search the
codebase itself (no Grep/Glob/MCP tools — those are removed per the
strict-research-delegation rule in `docs/agents/conventions.md §4.2`).

---

## 3. Location Decision Rule

The agent applies the rule from
`docs/how-to/documentation/write-reference.md §1` to decide where the output
file lands:

| Content type | Canonical home |
|---|---|
| Cross-cutting vocabulary, registry schemas, enum definitions | `docs/reference/` |
| Agent frontmatter, routing tables, classification inventories | `docs/agents/<family>/` |
| Database schema docs for a specific table or table group | `docs/database/` |
| Parameter / config reference scoped to a subsystem | topical folder closest to the subsystem |

Default: `docs/reference/` when no topical folder is clearly more appropriate.

The agent validates any location hint from `documentation-expert` against this
rule and overrides with a documented reason if the rule disagrees.

---

## 4. Output: Reference Doc Structure

The agent produces one Markdown file per invocation, following the canonical
entry structure from `docs/how-to/documentation/write-reference.md §2`:

1. **Definition** — one factual sentence.
2. **Signature / Shape** — type signature, DDL excerpt, or JSON schema (when applicable).
3. **Parameters / Columns Table** — column order: name / type / nullable / default / description.
4. **Return Value / Side Effects** — for functions and procedures only.
5. **Examples** — at least one concrete, runnable example.
6. **Cross-links** — links to matching explanation doc (the *why*) and how-to
   doc (the *do*).

Sections 2, 4, and 6 are omitted when genuinely not applicable (e.g. a glossary
has no function signature; a config enum has no side effects).

---

## 5. Response Payload

After writing the file, the agent returns a structured block to
`documentation-expert`:

```
## Reference doc produced

File: <absolute path written>
Location rationale: <one sentence citing the §1 decision rule>
Entry structure used: <list of sections present>
Cross-links added:
  - explanation -> <path or "none">
  - how-to -> <path or "none">
Open questions: <ambiguities for documentation-expert or the user to resolve>
```

`documentation-expert` aggregates this payload into the user-facing response when
the overall request is multi-genre (e.g. explanation + how-to + reference in one
run).

---

## 6. Constraints (What the Agent Will Not Do)

- Does not search the codebase (no `Grep`, `Glob`, `jcodemunch`, `serena`,
  `context7`). Per `docs/agents/conventions.md §4.2`, all cross-cutting search
  goes through `research-agent`.
- Does not spawn sub-agents independently. If research is needed that was not
  provided in the spec, it surfaces the need in `Open questions` and stops.
- Does not write outside `docs/`.
- Does not modify `docs/how-to/documentation/write-reference.md` (the how-to is
  the source of truth, not a target).
- Does not drift into explanation or how-to territory (enforced by the
  stay-narrow rule in `docs/how-to/documentation/write-reference.md §7`).
- Does not call back into `documentation-expert` (no recursion).

---

## 7. Model and Tools

| Field | Value | Rationale |
|---|---|---|
| `model` | `sonnet` | Structured authoring from clear factual inputs; no novel synthesis. Standard SWE tier per ADR-006 §2.1. |
| `tools` | `Bash, Read, Edit, Write, Agent` | Sonnet floor (Bash, Read, Edit, Write) + Agent for potential sub-agent dispatch via documentation-expert. Search tools removed per conventions §4.2. |
| `visibility` | internal | Invoked only by `documentation-expert`; description ends with `(internal — invoked by documentation-expert only)` per conventions §3.3. |

---

## 8. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1),
  visibility classes (§3), tool allowlists (§4.2 — strict-research-delegation).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) —
  three-tier ladder (§2.1), strict-research-delegation rationale (§2.6).
- [`docs/how-to/documentation/write-reference.md`](../../how-to/documentation/write-reference.md) —
  the how-to this agent loads before writing. Single source of truth for
  location rules, entry structure, table conventions, ordering rules, and
  cross-link conventions.
- [`docs/agents/coding/documentation-expert.md`](./documentation-expert.md) —
  the orchestrator that dispatches to this agent. Classification table and
  dispatch contract live there.
- [`.claude/agents/reference-author.md`](../../../.claude/agents/reference-author.md) —
  the agent file itself: frontmatter + system prompt.
- [Ticket 24](../../../tickets/09_done/EPIC-CodingAgents/24_reference_author.md) —
  the ticket that shipped this agent.
