---
title: "Agent Reference: adr-author"
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
  - "docs/how-to/documentation/write-adr.md"
  - "tickets/09_done/EPIC-CodingAgents/22_adr_author.md"
related_code:
  - ".claude/agents/adr-author.md"
  - "docs/architecture/"
---

# Agent Reference: `adr-author`

Internal identifier: `adr-author` (Sonnet specialist).
Dispatched by: `documentation-expert`.
Family: `coding/`.

This doc explains **when `documentation-expert` routes here**, **what inputs
the agent expects**, **what it produces**, and the **conventions it enforces**.

---

## 1. When `documentation-expert` Routes Here

`documentation-expert` classifies incoming requests by Diataxis genre. It
dispatches to `adr-author` when the intent is **"decide-record"**: the user
wants to capture an architectural decision that:

- Affects multiple components or cross-cuts the architecture.
- Has rejected alternatives that matter.
- Is binding — it constrains future implementation choices.

Requests that produce *descriptive* content (data-flow diagrams, component
registries, design overviews with no committed choice) go to `architecture-author`
instead. See the dispatch table in `.claude/agents/documentation-expert.md`.

**Do not invoke `adr-author` directly.** It is an internal agent; only
`documentation-expert` spawns it.

---

## 2. Inputs

`documentation-expert` passes a decision specification to `adr-author`. The
minimum required fields:

| Field | Example | Notes |
|---|---|---|
| `decision_summary` | "Use advisory locks for concurrency control" | One sentence, present tense. |
| `context` | "Workers were causing OOM via lock saturation…" | The problem motivating the decision. |
| `decision_body` | "We will use pg_try_advisory_lock…" | The committed choice, in "will / MUST" language. |
| `consequences` | `{positive: [...], negative: [...]}` | Expected effects. |
| `alternatives` | `[{name: "PgBouncer", rejection: "…"}, …]` | Each with a name and rejection reason. |
| `originating_ticket` | "tickets/00_inbox/epics/EPIC-Foo/01_bar.md" | Optional; used for cross-links. |
| `related_code` | `["sql_functions/...", "models/..."]` | Optional; used in frontmatter. |

Missing fields cause the agent to ask for clarification before writing.

---

## 3. What the Agent Produces

A single file at `docs/architecture/adrs/ADR-NNN-<slug>.md` where `NNN` is the
next free ADR number determined by listing the directory at execution time.

**Required sections (in order):**

1. Status metadata table (Status, Date, Author, Supersedes)
2. Context
3. Decision
4. Consequences
5. Alternatives

**Frontmatter** — YAML header with `title`, `type: adr`, `status`, `created`,
`related_docs`, `related_code`.

**Response payload** — after writing the file, the agent emits:

```
## ADR Authored

- **File:** docs/architecture/adrs/ADR-NNN-<slug>.md
- **ADR number:** NNN
- **Status:** Proposed
- **Decision summary:** <one sentence>
- **Sections present:** Status, Context, Decision, Consequences, Alternatives
- **Cross-links added:** <list>
```

---

## 4. Numbering Convention

The agent **always** runs `ls docs/architecture/adrs/ADR-*.md | sort` before
choosing a number. It never hard-codes or assumes the next number. This is the
project's guard against duplicate ADR numbers when two ADRs are authored
close together (the orchestrator dispatches sequentially; the listing lookup
closes any gap).

The zero-padded pattern is `NNN` — three digits: `001`, `007`, `010`, `100`.

As of the last corpus audit (2026-05-07):

| ADR | Topic |
|---|---|
| ADR-001 | Advisory Lock Concurrency Control |
| ADR-002 | Scheduled Tasks vs Background Workers |
| ADR-003 | Strategy Re-Evaluation Lifecycle |
| ADR-004 | Win Rate Floor for Strategy Routing |
| ADR-005 | candle_context GIN Index Strategy |
| ADR-006 | Agent Model Tiers and Gatekeeper Escalation |

The next ADR at time of authoring this reference doc would be **ADR-007** (but
confirm at execution time — the corpus may have grown).

---

## 5. Conventions Enforced

All conventions are grounded in the existing ADR corpus (ADR-001 through
ADR-006) and documented in `docs/how-to/documentation/write-adr.md`. The agent
loads that how-to at runtime; the how-to is the single source of truth.

Key rules applied on every run:

| Rule | Source |
|---|---|
| Filename: `ADR-NNN-<slug>.md`, zero-padded | how-to §2 |
| Next-free-number lookup via `ls` at runtime | how-to §3 |
| Section order: Status, Context, Decision, Consequences, Alternatives | how-to §4 |
| Status values: Proposed / Accepted / Superseded / Deprecated | how-to §5 |
| Decision language: "will" / "MUST", not "may" | how-to §6 |
| Alternatives: name + rejection reason, bullet or table format | how-to §7 |
| Cross-links: originating ticket, related ADRs, related code | how-to §8 |

---

## 6. What This Agent Does NOT Do

- Does not edit or supersede existing ADRs. Superseding an ADR is a separate
  request that `documentation-expert` must classify differently.
- Does not call `research-agent` autonomously — `documentation-expert` is
  responsible for pre-loading any codebase research the decision requires before
  dispatching.
- Does not write any file outside `docs/architecture/` unless the decision spec
  explicitly includes cross-reference targets.
- Does not dispatch back to `documentation-expert` (no recursion).

---

## 7. Cross-Links

- [`docs/how-to/documentation/write-adr.md`](../../how-to/documentation/write-adr.md) —
  the how-to guide the agent loads at runtime; grounded in ADR-001 through ADR-006.
- [`docs/agents/conventions.md`](../conventions.md) — agent authoring conventions
  (frontmatter schema, visibility classes, tool allowlists).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) —
  upstream policy ADR; strict-research-delegation rule (§2.6) governs the tool
  allowlist used by this agent.
- [`.claude/agents/adr-author.md`](../../../.claude/agents/adr-author.md) —
  the agent file itself.
- [Ticket 22](../../../tickets/09_done/EPIC-CodingAgents/22_adr_author.md) —
  the ticket that shipped this agent.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
