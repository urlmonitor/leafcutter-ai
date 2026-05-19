---
title: "Agent Reference: create-epic"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "tickets/09_done/EPIC-CodingAgents/Master_Plan.md"
  - "tickets/09_done/EPIC-CodingAgents/04_create_epic_agent.md"
related_code:
  - ".claude/agents/create-epic.md"
  - ".claude/agents/create-ticket.md"
  - ".claude/skills/create-ticket/SKILL.md"
---

# Agent Reference: `create-epic`

Internal identifier: `create-epic` (Haiku scaffolder).
Caller: `create-ticket` only — users never invoke this agent directly.
Family: `coding/`.

This doc explains **when create-epic is invoked**, **the four phases it runs**,
**the depth contract**, and **a worked 5-deliverable example**.

---

## 1. When create-epic is Invoked

`create-epic` is **never user-facing**. It is spawned by `create-ticket`
automatically when the `business-analyst` returns `deliverables_count > 3`. The
user's entry point is always `/create-ticket`; `create-epic` is an internal
implementation detail of the large-request path.

| Condition | Action |
|---|---|
| `deliverables_count <= 3` | `create-ticket` handles inline (no `create-epic`) |
| `deliverables_count > 3` AND `current_depth < 3` | `create-ticket` spawns `create-epic` |
| `deliverables_count > 3` AND `current_depth >= 3` | `create-ticket` returns a depth-cap error; `create-epic` is never called |

---

## 2. The Four Phases

### Phase 1 — Scaffold

`create-epic` first checks whether the target folder already exists. If it does,
it refuses and returns an error — it will never overwrite an existing epic.

If the folder is clear, it:

1. Creates `tickets/00_inbox/epics/EPIC-<Name>/` via `mkdir -p`.
2. Writes `Master_Plan.md` with valid `type: epic` frontmatter, a one-paragraph
   summary, and a pre-populated sub-ticket table.
3. Writes N stub ticket files (`01_<slug>.md` … `NN_<slug>.md`), each with
   valid frontmatter (satisfying the `ticket_frontmatter_guard` hook) and a
   sentence-long Goal. `depends_on` chains are pre-computed in sequential order:
   stub 02 depends on stub 01, stub 03 on stub 02, etc. This is done before
   fanout so children only harden within their assigned slot — they do not
   re-negotiate dependencies.

### Phase 2 — Fanout

After all stubs pass the `ticket_frontmatter_guard`, `create-epic` issues N
**simultaneous** Agent calls to `create-ticket` — one per stub. All N calls are
issued in a single parallel batch; none waits for another to finish first.

Each child `create-ticket` invocation receives:
- The stub file path.
- `current_depth: <create-epic's depth + 1>`.
- The original intent, so BA can frame the sub-ticket in context.

The depth counter propagates through the chain. `create-epic` at depth 2 sends
children at depth 3. At depth 3, `create-ticket` can harden the sub-ticket (BA
+ refinement + architect-review) but **cannot** call `create-epic` again —
doing so would exceed the depth cap.

### Phase 3 — Consolidate Open Questions

Each child `create-ticket` response may include an `open_questions` list.
`create-epic` collects all non-empty lists, deduplicates near-identical
questions, and groups them by ticket into a **single consolidated user prompt**.

This is the **one user touchpoint** for the whole epic: instead of answering
N separate question prompts (one per sub-ticket), the user answers once. The
prompt is clearly structured so each question names its owning ticket.

If all children return zero open questions, this phase is skipped and the epic
is complete.

### Phase 4 — Final Hardening Pass

With the user's answers in hand, `create-epic` re-invokes `create-ticket` for
each ticket that had open questions, passing the relevant answers and a
`final_pass: true` flag. The `create-ticket` agent runs only the `refinement`
step at this stage — `business-analyst` and `architect-review` do not re-run.

Tickets with zero open questions are left untouched (they were already complete
after Phase 2).

---

## 3. Depth Contract

| Depth | Meaning |
|---|---|
| 2 | Standard: `create-epic` spawned by a depth-1 `create-ticket` |
| 3 | Nested: `create-epic` spawned by a depth-2 `create-ticket` inside an inner epic |

At depth 3, Phase 2 (fanout) is **skipped**. Stubs are written to disk but not
hardened automatically. The agent returns a depth-cap warning naming each stub
file so the user can manually invoke `/create-ticket` on each one from a
depth-1 context.

This is the same soft cap defined in `docs/agents/conventions.md §5.4` and
`ADR-006 §2.7`.

---

## 4. Worked Example — 5-Deliverable Input

### Input

```
intent:        "Build a CME gap context pipeline"
epic_name:     "CMEGapContext"
deliverables:
  - "Schema migration — add ctx_cme_gaps JSONB column"
  - "Gap calculator — compute CME gaps from raw data"
  - "Enrichment procedure — populate ctx_cme_gaps on candle_context"
  - "Live hook — integrate gap context into live_trader"
  - "Dashboard widget — show gap context on monitoring page"
current_depth: 2
```

### Phase 1 — Folder Layout After Scaffold

```
tickets/00_inbox/epics/EPIC-CMEGapContext/
  Master_Plan.md            (type: epic, sub-ticket table pre-populated)
  01_schema_migration.md    (depends_on: [])
  02_gap_calculator.md      (depends_on: [01_schema_migration.md])
  03_enrichment_procedure.md (depends_on: [02_gap_calculator.md])
  04_live_hook.md           (depends_on: [03_enrichment_procedure.md])
  05_dashboard_widget.md    (depends_on: [04_live_hook.md])
```

Each stub has valid frontmatter (`status: todo`, `components`, `created`,
`depends_on`) and passes the `ticket_frontmatter_guard` hook before fanout
begins.

### Phase 2 — Parallel Fanout

Five simultaneous `create-ticket` calls (depth 3):

```
Agent call 1: create-ticket intent="Harden 01_schema_migration.md" depth=3
Agent call 2: create-ticket intent="Harden 02_gap_calculator.md"   depth=3
Agent call 3: create-ticket intent="Harden 03_enrichment_procedure.md" depth=3
Agent call 4: create-ticket intent="Harden 04_live_hook.md"        depth=3
Agent call 5: create-ticket intent="Harden 05_dashboard_widget.md" depth=3
```

All five are issued simultaneously. Each child runs BA + refinement +
architect-review internally (since `deliverables_count` for each sub-ticket
will be ≤ 3 after scoping to a single deliverable).

### Phase 3 — Consolidated Prompt

Suppose children 02, 04, and 05 return open questions:

```
## Open Questions — CMEGapContext

### Ticket 02: Gap Calculator
1. Should gaps be pre-computed on a schedule or computed on-demand at query time?
2. Which timeframes should gap detection cover (1d only, or also 4h)?

### Ticket 04: Live Hook
1. Should the live hook block trade execution when gap context is missing, or
   degrade gracefully?

### Ticket 05: Dashboard Widget
1. Should the widget show the raw gap value or a normalised score?

Please answer each question. When done, I will run the final hardening pass.
```

One prompt. The user answers once.

### Phase 4 — Final Hardening Pass

`create-epic` re-invokes `create-ticket` for tickets 02, 04, and 05 with the
relevant answers and `final_pass: true`. Refinement re-runs for those three.
Tickets 01 and 03 (no open questions) are left as-is.

### Final Output

```
## Epic Scaffold Complete: EPIC-CMEGapContext

Folder: tickets/00_inbox/epics/EPIC-CMEGapContext/
Master_Plan: tickets/00_inbox/epics/EPIC-CMEGapContext/Master_Plan.md
Stubs written: 5
Hardened: 5

Sub-tickets:
- 01_schema_migration.md — Schema Migration — [hardened]
- 02_gap_calculator.md — Gap Calculator — [hardened]
- 03_enrichment_procedure.md — Enrichment Procedure — [hardened]
- 04_live_hook.md — Live Hook — [hardened]
- 05_dashboard_widget.md — Dashboard Widget — [hardened]

Open questions resolved: 4 questions across 3 tickets.
```

---

## 5. Guardrails

| Guardrail | Behaviour |
|---|---|
| Existing epic folder | Refuses; returns error; writes nothing |
| Depth cap (>= 3) | Skips Phase 2 fanout; returns depth-cap warning listing each stub |
| Guard hook failure on stub | Fixes frontmatter before proceeding to fanout |
| Search needs | Delegates to `research-agent` via Agent tool; never uses Grep/Glob/MCP directly |
| Final-pass scope | Only `refinement` re-runs; BA and architect-review do not re-run |

---

## 6. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1),
  file layout (§2), visibility classes (§3), tool allowlists (§4.4 exception
  comment rule), nesting depth soft cap (§5.4).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) —
  upstream ADR: three-tier ladder (§2.1), tool allowlist (§2.6), nesting
  depth (§2.7).
- [`tickets/09_done/EPIC-CodingAgents/Master_Plan.md`](../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md) —
  locked design decision: hybrid fanout for epic generation; max nesting
  depth 3; create-ticket as the single user entry.
- [`.claude/agents/create-ticket.md`](../../../.claude/agents/create-ticket.md) —
  the only legitimate caller of `create-epic`.
- [`.claude/skills/create-ticket/SKILL.md`](../../../.claude/skills/create-ticket/SKILL.md) —
  canonical file-writing rules loaded by `create-ticket` children; not
  modified by `create-epic`.
- [Ticket 04](../../../tickets/09_done/EPIC-CodingAgents/04_create_epic_agent.md) —
  the ticket that shipped this agent.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
