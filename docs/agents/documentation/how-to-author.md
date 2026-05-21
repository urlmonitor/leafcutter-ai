---
title: "Agent Reference: how-to-author"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "docs/how-to/documentation/write-how-to.md"
  - "docs/README.md"
  - "tickets/09_done/EPIC-CodingAgents/21_how_to_author.md"
---

# Agent Reference: `how-to-author`

Implementing agent: `how-to-author` (Sonnet, internal).
Family: `coding/` — documentation specialist sub-agents.
Dispatched by: `documentation-expert` only.

This doc explains **when `documentation-expert` routes here**, **what the agent
expects as input**, **what it produces**, and **how the how-to and agent compose**.

---

## 1. When `documentation-expert` Routes Here

`documentation-expert` dispatches to `how-to-author` when it classifies a
request as Diataxis **"do"** intent — the user wants to accomplish a specific
task and needs a step-by-step recipe.

| User phrasing | Genre classification | Dispatched to |
|---|---|---|
| "write a how-to for X" | do | `how-to-author` |
| "document the steps to do Y" | do | `how-to-author` |
| "I need a guide for running Z" | do | `how-to-author` |
| "explain why X works this way" | understand | `explanation-author` (not here) |
| "write an API reference for X" | look up | `reference-author` (not here) |
| "record the decision to use X" | decide | `adr-author` (not here) |

Do **not** invoke `how-to-author` directly — it is internal and only triggered
by `documentation-expert`.

---

## 2. Inputs

`documentation-expert` passes a structured task spec:

```
Task: <verb phrase naming the task — becomes the H1 title>
User story: <"I need to X because Y" — the anchor that keeps the guide practical>
Source material: <file paths or raw content to draw facts from>
Existing location hint: <optional — documentation-expert's suggested path>
Related explanation doc: <path or "none">
Related reference doc: <path or "none">
```

All fields are consumed by the agent's execution loop. `Source material` is the
primary factual input — the agent reads the listed files and uses their content
as the basis for the guide. It does not search the codebase itself (no
Grep/Glob/MCP tools — removed per the strict-research-delegation rule in
`docs/agents/conventions.md §4.2`).

---

## 3. Location Decision Rule

The agent applies the rule from
`docs/how-to/documentation/write-how-to.md §Location Decision Rule` to decide
where the output file lands. The rule uses three questions:

1. **Who needs this guide?** A general contributor (→ `docs/how-to/`) or a
   contributor already working in a specific domain (→ topical folder)?
2. **Where will they look first?** The how-to index (`docs/how-to/README.md`)
   or a topical README (`docs/database/README.md`, etc.)?
3. **Does an existing topical folder cover this domain?** If yes, prefer the
   topical folder for domain-specific tasks. If no folder exists, use
   `docs/how-to/<domain>/<guide>.md` as an interim home.

| Location | Use when |
|---|---|
| `docs/how-to/<guide>.md` | General-purpose task — a contributor could need it from any context. |
| `docs/<topic>/<guide>.md` | Task almost always accessed in a specific domain; the topical folder is the natural discovery point. |

When in doubt, place in `docs/how-to/` and add a cross-link from the topical
README.

The agent validates any location hint from `documentation-expert` against this
rule and overrides with a documented reason if the rule disagrees.

---

## 4. Outputs

`how-to-author` produces one Markdown file per invocation, following the
canonical skeleton from `docs/how-to/documentation/write-how-to.md §How-To
Skeleton`:

1. **Frontmatter** — title, type: how-to, status, created, last_updated,
   components, related_docs.
2. **H1 title** — "How to \<Verb Phrase\>".
3. **One-sentence overview** — what the reader accomplishes and why.
4. **`## Prerequisites`** — environment, skills, prior-reading links. Tight
   bullets; links to the doc that explains each prerequisite rather than
   explaining it inline.
5. **`## Steps`** — one action per step. H3 (`### Step N — <Action>`) when the
   step has sub-content (code block, table, "What to look for" note). Language
   tag on every code fence. Full commands — no truncation.
6. **`## Verification`** — runnable command with exact expected output or clear
   shape of output. Clear fail signal. Link to Troubleshooting when applicable.
7. **`## Troubleshooting`** — only when known failure modes exist. Numbered
   cause → fix pairs.
8. **`## See Also`** — cross-links to sibling explanation/reference docs and
   `docs/README.md`.

Sections 7 and 8 are omitted when genuinely not applicable.

---

## 5. Response Payload

After writing the file, the agent returns a structured block to
`documentation-expert`:

```
## How-to produced

File: <absolute path written>
Location rationale: <one sentence citing the Location Decision Rule>
Sections present: Prerequisites, Steps (N steps), Verification[, Troubleshooting][, See Also]
README updated: <yes — path | no — not present | no — already listed>
Cross-links added:
  - explanation -> <path or "none">
  - reference   -> <path or "none">
Open questions: <ambiguities for documentation-expert or the user to resolve, or "none">
```

`documentation-expert` aggregates this payload into the user-facing response
when the overall request is multi-genre (e.g. explanation + how-to + reference
in one run).

---

## 6. How the How-To and Agent Compose

Two surfaces work together; each has a single responsibility:

| Surface | File | Responsibility |
|---|---|---|
| How-to | `docs/how-to/documentation/write-how-to.md` | Canonical rules: heading hierarchy, Prerequisites conventions, Steps + code-block rules, Verification conventions, Location Decision Rule, copy-pasteable skeleton. Single source of truth. |
| Agent | `.claude/agents/how-to-author.md` | Pins the model (Sonnet) and tool allowlist; mandates loading the how-to before writing; enforces the location decision and self-verification checklist; produces the structured response payload. |

The how-to is **never modified** by the agent. If the convention changes, the
change goes in the how-to only; the agent picks it up automatically on the next
invocation because it reads the how-to at runtime.

---

## 7. Constraints (What the Agent Will Not Do)

- Does not search the codebase (no `Grep`, `Glob`, `jcodemunch`, `serena`,
  `context7`). Per `docs/agents/conventions.md §4.2`, all cross-cutting search
  goes through `research-agent`. If source material is missing from the spec,
  it surfaces the gap in `Open questions` and stops.
- Does not spawn sub-agents independently. Research needs that were not provided
  are surfaced in `Open questions`.
- Does not write outside `docs/`.
- Does not modify `docs/how-to/documentation/write-how-to.md`.
- Does not drift into explanation or reference territory. If the request is
  better served by another specialist, it says so in `Open questions` and stops.
- Does not call back into `documentation-expert` (no recursion).
- One file per invocation.

---

## 8. Model and Tools

| Field | Value | Rationale |
|---|---|---|
| `model` | `sonnet` | Structured authoring from a clear spec and a loaded convention doc; no novel synthesis. Standard SWE tier per ADR-006 §2.1. |
| `tools` | `Bash, Read, Edit, Write, Agent` | Sonnet floor (Bash, Read, Edit, Write) + Agent for potential research delegation. Search tools removed per conventions §4.2. |
| `visibility` | internal | Invoked only by `documentation-expert`; description ends with `(internal — invoked by documentation-expert only)` per conventions §3.3. |

---

## 9. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1),
  file layout (§2), visibility classes (§3), tool allowlists (§4.2 — strict-
  research-delegation).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) —
  three-tier ladder (§2.1), strict-research-delegation rationale (§2.6).
- [`docs/how-to/documentation/write-how-to.md`](../../how-to/documentation/write-how-to.md) —
  the how-to this agent loads at runtime. Single source of truth for the
  heading hierarchy, Prerequisites conventions, Steps + code-block rules,
  Verification conventions, Location Decision Rule, and copy-pasteable skeleton.
- [`docs/README.md`](../../README.md) — Diataxis index defining the "do" genre.
- [`docs/agents/coding/documentation-expert.md`](./documentation-expert.md) —
  the orchestrator that dispatches to this agent. Classification table and
  dispatch contract live there.
- [`.claude/agents/how-to-author.md`](../../../.claude/agents/how-to-author.md) —
  the agent file itself: frontmatter + system prompt. (Fallback staging path:
  `docs/agents/coding/how-to-author.AGENT_FILE.md` when `.claude/agents/` write
  permission is unavailable.)
- [Ticket 21](../../../tickets/09_done/EPIC-CodingAgents/21_how_to_author.md) —
  the ticket that shipped this agent.
- [Ticket 20](../../../tickets/09_done/EPIC-CodingAgents/20_documentation_expert.md) —
  the `documentation-expert` orchestrator that dispatches here.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
