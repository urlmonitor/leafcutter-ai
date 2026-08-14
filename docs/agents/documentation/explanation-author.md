---
title: 'Agent Reference: explanation-author'
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
- infrastructure
related_docs:
- docs/agents/conventions.md
- docs/architecture/adrs/ADR-033-agent-model-tiers.md
- docs/how-to/documentation/write-explanation.md
- docs/README.md
- tickets/09_done/EPIC-CodingAgents/25_explanation_author.md
description: 'Overview of Agent Reference: explanation-author.'
---
# Agent Reference: `explanation-author`

Internal identifier: `explanation-author` (Sonnet sub-agent).
Family: `coding/` — documentation specialist sub-agents.
Dispatched by: `documentation-expert` only.

This doc explains **when `documentation-expert` routes here**, **what the agent produces**, **the genre guard**, and **how the how-to and agent compose**.

---

## 1. When `documentation-expert` Routes Here

`documentation-expert` dispatches to `explanation-author` when it classifies a request as Diataxis "understand" — the user wants to build a mental model of why something works the way it does.

| User phrasing | Genre classification | Dispatched to |
|---|---|---|
| "explain why X works this way" | understand | `explanation-author` |
| "write a concept doc for Y" | understand | `explanation-author` |
| "why did we design Z like this?" | understand | `explanation-author` |
| "document the architecture of X" | describe | `architecture-author` (not here) |
| "write a how-to for X" | do | `how-to-author` (not here) |
| "record the decision to use X" | decide | `adr-author` (not here) |

Do **not** invoke `explanation-author` directly — it is internal and only triggered by `documentation-expert`.

---

## 2. Inputs

`documentation-expert` passes:

- The concept spec: a description of the concept to explain (name, scope, what questions the reader should be able to answer after reading).
- Optionally: paths to related how-to, reference, or ADR docs for cross-linking.
- Optionally: the target location if the orchestrator has already classified it (e.g. "this is a `docs/logic/` domain concept").

---

## 3. Outputs

`explanation-author` produces:

1. **The explanation file** at the chosen location, structured as:
   - Frontmatter (title, type: explanation, status, created, related_docs).
   - H1 noun-phrase title.
   - Opening "why it exists" section.
   - Background / context section.
   - Discussion body (subsections, tables, callouts, optional Mermaid diagrams).
   - Trade-offs section (at least one rejected alternative).
   - `## See Also` with cross-links to the how-to, reference, and ADR siblings.
   - Optional `<!-- DECISION HISTORY -->` block.

2. **A structured response payload** naming:
   - The file path.
   - The location rationale (one line citing the decision rule).
   - Whether each sibling cross-link (how-to / reference / ADR) was found or is missing.
   - Whether the relevant README was updated.

---

## 4. Genre Guard

Before writing, the agent applies a three-way decision tree to confirm the request is "understand" and not another genre:

| Test | If true | Action |
|---|---|---|
| Request records a decision made at a point in time | ADR territory | Hand back: "invoke `adr-author`" |
| Request describes component structure, service ports, or data flow | Architecture territory | Hand back: "invoke `architecture-author`" |
| Request builds mental model via motivation + trade-offs + context | Explanation territory | Proceed |

This guard prevents the most common drift: an explanation that decides (should have been an ADR) or an explanation that describes structure (should have been an architecture doc).

---

## 5. Location Decision Rule

The agent applies the rule from `docs/how-to/documentation/write-explanation.md` §Location Decision Rule:

| Location | Condition |
|---|---|
| `docs/explanation/<doc>.md` | Cross-cutting or architectural concept — spans multiple domains or applies to any contributor. |
| `docs/<topic>/<doc>.md` | Domain-specific concept — only relevant in a specific domain folder already used as a discovery point (e.g. `docs/logic/`, `docs/database/`). |

The response payload always states which location was chosen and why.

---

## 6. How the How-To and Agent Compose

Two surfaces work together:

| Surface | File | Responsibility |
|---|---|---|
| How-to | `docs/how-to/documentation/write-explanation.md` | Canonical rules: structure, voice, location decision, genre distinctions, copy-pasteable skeleton. Single source of truth for the explanation convention. |
| Agent | `.claude/agents/explanation-author.md` | Pins the model (Sonnet) and tool allowlist; mandates loading the how-to before writing; enforces genre guard; produces the structured response payload. |

The how-to is **never modified** by the agent. If the convention changes, the change goes in the how-to only; the agent picks it up on the next invocation because it reads the how-to at runtime.

---

## 7. Tool Allowlist

```
tools: Bash, Read, Edit, Write, Agent
```

`Agent` is required because the agent may delegate cross-file lookups to `research-agent`. The following tools are **absent** per the strict-research-delegation rule (`docs/agents/conventions.md` §4.2): `Grep`, `Glob`, all `mcp__jcodemunch__*`, all `mcp__plugin_serena_serena__*`, all `mcp__plugin_context7_context7__*`.

---

## 8. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1), file layout (§2), visibility classes (§3), tool allowlists (§4).
- [`docs/architecture/adrs/ADR-033-agent-model-tiers.md`](../../architecture/adrs/ADR-033-agent-model-tiers.md) — upstream ADR: three-tier ladder, strict-research-delegation rule.
- [`docs/how-to/documentation/write-explanation.md`](../../how-to/documentation/write-explanation.md) — the how-to this agent loads at runtime. Single source of truth for explanation conventions.
- [`docs/README.md`](../../README.md) — Diataxis index defining the "understand" genre.
- [Ticket 25](../../../tickets/09_done/EPIC-CodingAgents/25_explanation_author.md) — the ticket that shipped this agent.
- [Ticket 20](../../../tickets/09_done/EPIC-CodingAgents/20_documentation_expert.md) — the `documentation-expert` orchestrator that dispatches here.
