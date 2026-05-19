---
title: "Agent Reference: documentation-expert"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "docs/README.md"
  - "tickets/09_done/EPIC-CodingAgents/20_documentation_expert.md"
related_code:
  - ".claude/agents/documentation-expert.md"
  - ".agents/workflows/documentation.md"
---

# Agent Reference: `documentation-expert`

Implementing agent: `documentation-expert` (Sonnet orchestrator).
Family: `coding/`.
Visibility: user-facing — auto-triggers on "write/update a doc" requests; also
invoked via `/documentation`.

This doc explains the classification logic, the dispatch contract, the
aggregation rules, and the no-recursion guard that governs this orchestrator
and its five specialist sub-agents (tickets 21-25).

---

## 1. Overview

`documentation-expert` is the single user-facing entry point for all
documentation authoring. The user never needs to know which Diataxis genre
applies or which specialist to invoke — the orchestrator classifies the intent
and routes automatically.

Specialists it dispatches to:

| Ticket | Agent | Diataxis genre | When dispatched |
|---|---|---|---|
| 21 | `how-to-author` | how-to | "do / how to" — step-by-step task |
| 22 | `adr-author` | ADR | "decide-record" — binding architectural decision |
| 23 | `architecture-author` | architecture (descriptive) | "design / data flow / component" |
| 24 | `reference-author` | reference | "look up" — API, schema, enum, glossary |
| 25 | `explanation-author` | explanation | "understand / why" — concept explanation |

---

## 2. Classification Table

The orchestrator applies this table on every request:

| User intent signal | Diataxis genre | Specialist |
|---|---|---|
| "write a how-to for X"; "step-by-step guide for Y"; "explain how to do Z" | how-to | `how-to-author` |
| "record the decision to use X"; "write an ADR for Y"; "document why we chose Z" | ADR | `adr-author` |
| "document how X works"; "describe the data flow"; "draw the component diagram" | architecture | `architecture-author` |
| "write the API reference for X"; "document the schema of Y"; "parameter table for Z" | reference | `reference-author` |
| "explain why X works this way"; "concept doc for Y"; "why did we design Z like this?" | explanation | `explanation-author` |

When a request spans multiple genres (e.g. "document this new feature
end-to-end"), all matching genres are identified and dispatched sequentially.

---

## 3. Dispatch Contract

The orchestrator dispatches each specialist via the `Agent` tool, passing a
structured spec block whose fields vary by specialist. Each specialist's
reference doc (in `docs/agents/coding/`) lists the required fields.

The orchestrator itself does **not** write or edit any doc file. It delegates
all authoring to specialists and aggregates their responses.

---

## 4. Multi-Genre Dispatch Order

When more than one specialist is dispatched in a single run, the order is:

1. `architecture-author` (structural context)
2. `explanation-author` (conceptual context)
3. `how-to-author` (task guide)
4. `reference-author` (lookup table)
5. `adr-author` (decision record)

This dependency-friendly order ensures that cross-links from downstream docs
(how-to, reference) can point at upstream docs (explanation, architecture)
already written.

---

## 5. Aggregation Rules

After all specialists complete, `documentation-expert` emits a unified payload:

```
## Documentation Produced

Genres: <list>
Specialists invoked: <list in dispatch order>

### Files Written

| File | Genre | Specialist |
|---|---|---|
| <path> | <genre> | <specialist> |

### Open Questions

<Unresolved ambiguities; empty if none.>
```

Specialist errors and refusals are surfaced in the payload, never swallowed
silently.

---

## 6. No-Recursion Guard

Specialists 21-25 never call back into `documentation-expert`. The orchestrator
is the root of the dispatch tree for documentation work. Any specialist response
that attempts to invoke `documentation-expert` is treated as an error and surfaced
in `Open Questions`.

Nesting depth for a typical multi-genre run:

```
user-facing session (depth 0)
  documentation-expert (depth 1)
    architecture-author (depth 2)
      research-agent (depth 3) -- within soft cap
    how-to-author (depth 2)
    reference-author (depth 2)
```

Depth 3 is the soft cap per ADR-006 §2.7. Specialists must not spawn further
sub-agents beyond `research-agent`.

---

## 7. Slash Command

The `/documentation` slash command is the explicit invocation surface for this
agent. The command resolves to `.agents/workflows/documentation.md` via the
`.claude/commands/` Windows junction. Prose intent matching ("document this
feature") also auto-triggers the agent via its `description` field.

---

## 8. Out of Scope

- **Tutorials** (Diataxis "learn" genre) — not in this initial set; can be
  added as a `tutorial-author` specialist later.
- **Editing or superseding existing docs** outside of what a specialist
  naturally does when updating a doc it authored.
- **Automated doc lint or rebuild** beyond what `doc-enforcer` already covers.

---

## 9. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1),
  file layout (§2), visibility classes (§3), tool allowlists (§4), patterns (§5).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) —
  upstream policy: three-tier ladder (§2.1), Multi-Skill Dispatcher pattern (§2.4),
  strict-research-delegation (§2.6), nesting depth (§2.7).
- [`docs/README.md`](../../README.md) — Diataxis index; loaded by the orchestrator
  on every run.
- [`.claude/agents/documentation-expert.md`](../../../.claude/agents/documentation-expert.md) —
  the agent file itself: frontmatter + system prompt.
- [`.agents/workflows/documentation.md`](../../../.agents/workflows/documentation.md) —
  the slash-command workflow body for `/documentation`.
- [`docs/agents/coding/adr-author.md`](./adr-author.md) — specialist reference.
- [`docs/agents/coding/architecture-author.md`](./architecture-author.md) — specialist reference.
- [`docs/agents/coding/reference-author.md`](./reference-author.md) — specialist reference.
- [`docs/agents/coding/explanation-author.md`](./explanation-author.md) — specialist reference.
- `docs/agents/coding/how-to-author.md` — specialist reference (ticket 21).
- [Ticket 20](../../../tickets/09_done/EPIC-CodingAgents/20_documentation_expert.md) —
  the ticket that shipped this agent.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
