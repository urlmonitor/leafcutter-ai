---
title: 'Agent Reference: create-ticket'
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
- infrastructure
- infrastructure
related_docs:
- docs/agents/conventions.md
- docs/architecture/adrs/ADR-033-agent-model-tiers.md
- tickets/09_done/EPIC-CodingAgents/Master_Plan.md
- tickets/09_done/EPIC-CodingAgents/05_create_ticket_agent.md
related_code:
- .claude/agents/create-ticket.md
- .claude/commands/create-ticket.md
- .claude/skills/create-ticket/SKILL.md
description: 'Overview of Agent Reference: create-ticket.'
---
# Agent Reference: `create-ticket`

User-facing identifier: `/create-ticket` (slash command).
Implementing agent: `create-ticket` (Sonnet orchestrator).
Family: `coding/` — first occupant of this family.

This doc explains **when to use** the agent, **the routing table**, **the depth
contract**, **how the slash command and skill compose**, and where the canonical
authoring rules live.

---

## 1. When to Use

Fire `/create-ticket` (or describe your request in prose) whenever you want to
capture a feature, fix, or task in `tickets/`. You do not need to pre-classify
whether your request is "a ticket" or "an epic" — the agent decides.

| Trigger | What happens |
|---|---|
| User types `/create-ticket <description>` | Agent spawns; BA runs first |
| User says "create a ticket for X" | Agent auto-fires via description |
| User says "I need a ticket to add Y" | Agent auto-fires via description |
| User describes a feature/fix/task | Agent auto-fires via description |

Do **not** invoke `create-epic`, `business-analyst`, `refinement`, or
`architect-review` directly — those are internal agents. `create-ticket` is the
only entry point.

---

## 2. Routing Table

The routing decision is made after the business-analyst returns
`deliverables_count`.

| `deliverables_count` | `current_depth` | Route |
|---|---|---|
| ≤ 3 | any | Small path: spawn `refinement` + `architect-review` in parallel, then finalise one ticket via the create-ticket skill. |
| > 3 | < 3 | Large path: defer to `create-epic` with `current_depth + 1`. |
| > 3 | ≥ 3 | Depth-cap error: refuse, return structured error, stop. |

---

## 3. Depth Contract

The agent passes and reads a `current_depth` integer on every invocation.

| Depth | Who invoked this instance |
|---|---|
| 1 | User directly (the default when absent) |
| 2 | `create-epic` fanout (one sub-ticket hardening pass) |
| 3 | Nested `create-epic` inside a depth-2 `create-epic` |

The **hard cap is 3**. At depth 3, if the business-analyst classifies the
request as >3 deliverables, the agent returns a structured error block instead
of calling `create-epic` again. The error names the cap, the depth it was
reached at, and points at the Master_Plan section that explains why.

This cap prevents unbounded recursion in the
`create-ticket → create-epic → N × create-ticket` cycle that is how epics
are scaffolded.

---

## 4. How the Slash Command and Skill Compose

Three surfaces work together; each has a single responsibility:

| Surface | File | Responsibility |
|---|---|---|
| Slash command | `.claude/commands/create-ticket.md` (junction at `.claude/commands/create-ticket.md`) | One-liner forwarding `$ARGUMENTS` to the agent. Does nothing else. |
| Agent | `.claude/agents/create-ticket.md` | Pins the model (Sonnet), pins the tool allowlist, and runs the orchestration sequence (BA → branch → finalise). |
| Skill | `.claude/skills/create-ticket/SKILL.md` | Canonical file-writing rules: frontmatter schema, folder routing, naming conventions, body structure, hook requirements. The agent defers to this skill for all write-side work. |

The skill is **never modified** by the agent. If the file-writing rules change,
they change in the skill only; the agent picks them up automatically on the next
invocation because it loads the skill at runtime.

The slash command is **never modified** by the agent. It is a stable forwarding
surface; any improvements to behaviour go in the agent file.

---

## 5. Example Flows

### 5.1 Single-ticket flow ("add a CLI flag to dump open positions")

1. User types: `/create-ticket add a CLI flag to dump current open positions`
2. `create-ticket` spawns `business-analyst`. BA returns:
   ```json
   {
     "summary": "Add --dump-positions CLI flag to the trader bot",
     "deliverables_count": 1,
     "open_questions": [],
     "success_criteria": ["Flag prints open positions as JSON and exits"]
   }
   ```
3. `deliverables_count = 1` → small path. `create-ticket` spawns `refinement`
   and `architect-review` in a single parallel batch.
4. Both return quickly ("no further questions / no structural concerns").
5. Agent loads `.claude/skills/create-ticket/SKILL.md` and writes:
   `tickets/00_inbox/TICKET-20260507-DumpOpenPositions.md`
6. One ticket is produced. No `create-epic` call is made.

### 5.2 Epic flow ("build a full CME gap context pipeline")

1. User says: "create a ticket to build the full CME gap context pipeline"
2. `create-ticket` spawns `business-analyst`. BA returns:
   ```json
   {
     "summary": "CME gap context: schema, populator, enrichment, live hook, dashboard",
     "deliverables_count": 7,
     "open_questions": [
       "Which timeframes should the gap context cover?",
       "Should gaps be pre-computed or computed on-demand?"
     ],
     "success_criteria": ["..."]
   }
   ```
3. `deliverables_count = 7 > 3`. `current_depth = 1 < 3`.
4. Agent surfaces BA's open questions to the user. User answers.
5. Agent spawns `create-epic` with `current_depth: 2` and the enriched context.
6. `create-epic` scaffolds `tickets/00_inbox/epics/EPIC-CMEGapContext/` with a
   `Master_Plan.md` and N stub tickets, then fans out N parallel `create-ticket`
   calls at depth 2 to harden each sub-ticket. It merges open questions from all
   sub-tickets into one consolidated prompt back to the user.
7. `create-ticket` (depth 1) returns `create-epic`'s output verbatim. It does
   not itself spawn `refinement` or `architect-review` — `create-epic` owns that
   fanout.

---

## 6. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1),
  file layout (§2), visibility classes (§3), tool allowlists (§4), nesting depth
  soft cap (§5.4).
- [`docs/architecture/adrs/ADR-033-agent-model-tiers.md`](../../architecture/adrs/ADR-033-agent-model-tiers.md) —
  upstream ADR: three-tier ladder (§2.1), tool allowlist + strict-research-
  delegation (§2.6), nesting depth (§2.7).
- [`tickets/09_done/EPIC-CodingAgents/Master_Plan.md`](../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md) —
  locked design decisions section; routing rules verbatim; dependency order.
- [`.claude/agents/create-ticket.md`](../../../.claude/agents/create-ticket.md) —
  the agent file itself.
- [`.claude/skills/create-ticket/SKILL.md`](../../../.claude/skills/create-ticket/SKILL.md) —
  canonical skill for file-writing rules. Not modified by this agent.
- [`.claude/commands/create-ticket.md`](../../../.claude/commands/create-ticket.md) —
  the slash-command body (one-liner forwarder). Surfaced at
  `.claude/commands/create-ticket.md` via the Windows junction.
- [Ticket 05](../../../tickets/09_done/EPIC-CodingAgents/05_create_ticket_agent.md) —
  the ticket that shipped this agent.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
