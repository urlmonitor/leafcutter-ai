---
title: "Agent Reference: business-analyst"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-13
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "tickets/09_done/EPIC-CodingAgents/Master_Plan.md"
  - "tickets/09_done/EPIC-CodingAgents/01_business_analyst_agent.md"
related_code:
  - ".claude/agents/business-analyst.md"
---

# Agent Reference: `business-analyst`

Implementing agent: `business-analyst` (internal, Sonnet).
Family: `coding/`.
Visibility class: **internal** — invoked by `create-ticket` only.

This doc explains **what the agent does**, **the structured payload it returns**,
**how clarifying questions work**, and how to read its output as a downstream
agent.

---

## 1. Role and Boundaries

`business-analyst` is the first stage in the ticket-creation pipeline. It runs
before any technical work (refinement, architectural review, or codebase
research) to answer one question:

> What outcome does the user actually want, and how will we know it is done?

It does **not**:
- Search the codebase (Grep / Glob / MCP tools are stripped from its allowlist).
- Write code, SQL, or config files.
- Make technical decisions or propose implementations.
- Call `refinement` or `architect-review` — those are the parent's responsibility.

It **may** spawn `research-agent` (via the Agent tool) for one narrowly scoped
purpose: estimating how many existing components a large request touches, to
calibrate `deliverables_count`. This is scoping, not design.

---

## 2. Five-Question Framing Template

The agent works through up to five framing dimensions. It skips any dimension
the user has already addressed.

| # | Question | Why it matters |
|---|---|---|
| 1 | Who benefits? | Grounds the outcome in a real stakeholder |
| 2 | What changes for them? | Forces the "so what" before any how |
| 3 | How do we know it worked? | Produces a verifiable success criterion |
| 4 | What is explicitly out of scope? | Prevents scope creep before refinement |
| 5 | What is the rough size? | Seeds `deliverables_count`; trips the epic route when > 3 |

The agent asks the questions it needs answered, waits for user responses, then
incorporates those answers into the final payload. It never returns
`deliverables_count` before question 5 is resolved when the count is genuinely
ambiguous.

---

## 3. Orchestration Sequence

The agent works through two sequential steps:

**Step 1 — Scope the request.** Apply the five-question framing template (§2)
to produce `summary`, `deliverables_count`, `routing_decision`, `files_touched`,
`success_criteria`, `open_questions`, and `agents` fields.

**Step 2 — Spawn test-planner.** After scoping deliverables, the BA always
spawns `test-planner` via the Agent tool. It passes the user request, the
`deliverables_count`, and the `files_touched` list. `test-planner` returns a
`test_requirements` JSON block (see §3a). The BA includes this verbatim in its
unified output payload.

**Graceful fallback**: if `test-planner` fails or returns a malformed payload,
the BA sets `test_requirements` to `{"rationale": "test-planner unavailable; test_requirements must be authored manually.", "tests": []}` and continues. It does NOT hard-fail.

---

## 3a. test-planner Spawn and test_requirements Schema

The `test_requirements` field in the BA payload is produced by `test-planner`.
It describes which tests should be written for this ticket.

```json
{
  "test_requirements": {
    "rationale": "<why these tests are needed or why none are needed>",
    "tests": [
      {
        "name": "test_<descriptive_name>",
        "description": "<one sentence: what observable behavior this test verifies>",
        "type": "unit|integration|manual",
        "target_dir": "unit_tests/<module>/",
        "covers": "<function, class, or behavior under test>"
      }
    ]
  }
}
```

| Field | Type | Rule |
|---|---|---|
| `rationale` | string | Always present. One sentence. |
| `tests` | array | May be empty (docs-only or config-only tickets). |
| `name` | string | Starts with `test_`. |
| `description` | string | One sentence; describes observable behavior. |
| `type` | string | Exactly `"unit"`, `"integration"`, or `"manual"`. |
| `target_dir` | string | Matches an existing `unit_tests/<key>/` or notes `"new directory needed"`. |
| `covers` | string | Specific function, class, or behavior. |

The BA sets `agents.test-writer: "needed"` when `test_requirements.tests` is
non-empty, and `"not_needed"` when the array is empty.

---

## 4. Structured Payload Schema

The agent always returns a fenced JSON block. `create-ticket` parses this
deterministically; prose around the block is ignored.

```json
{
  "intent": "<one sentence: the outcome the user wants>",
  "deliverables_count": <integer>,
  "routing_decision": "standard_ticket" | "epic",
  "routing_rationale": "<why this should be an epic or a single ticket>",
  "success_criteria": [
    "<verifiable signal 1>",
    "<verifiable signal 2>"
  ],
  "open_questions": [
    "<anything still ambiguous that the next agent should raise>"
  ],
  "test_requirements": {
    "rationale": "<see §3a>",
    "tests": [...]
  }
}
```

| Field | Type | Rule |
|---|---|---|
| `intent` | string | One sentence. Form: "The system/user can now \<verb\> \<object\>." |
| `deliverables_count` | integer ≥ 1 | Honest count of distinct shippable artifacts. Never invented; question 5 resolves ambiguity first. |
| `routing_decision` | string | MUST be exactly `"standard_ticket"` or `"epic"`. Drives the orchestrator routing. |
| `routing_rationale` | string | One sentence explaining the routing choice. |
| `success_criteria` | string[] | Verifiable signals. At least one entry always present. |
| `open_questions` | string[] | Unresolved ambiguities for downstream agents. `[]` when nothing is open. |
| `test_requirements` | object | Produced by `test-planner`. See §3a. Always present. |

---

## 5. Routing Decision Rule

Each of the following counts as **one** deliverable:
- A new table or schema change
- A SQL procedure or function
- A Python module or significant code addition
- A new endpoint or dashboard panel
- A migration script

The `business-analyst` holds explicit authority over whether the task should be treated as an `epic` or a `standard_ticket`. 
As a rule of thumb, `deliverables_count > 3` usually warrants an epic. However, the BA can override this based on task complexity (e.g., highly decoupled tasks) or if the user explicitly requests an epic or standard ticket. The parent orchestrator (`create-ticket`) strictly obeys the BA's `routing_decision`. See ticket 04 (`create-epic`) and ticket 05 (`create-ticket`) in `tickets/09_done/EPIC-CodingAgents/`.

---

## 6. Example Outputs

### 6.1 Small ticket — "I want a daily PnL email"

The agent recognises this as a single shippable thing (one scheduled job or
notification integration) with a clear beneficiary and a verifiable signal.
It may ask question 4 ("what is out of scope — e.g. are open positions excluded?")
and question 3 if the delivery mechanism is unspecified.

After answers:

```json
{
  "intent": "The on-call engineer can now receive a daily PnL summary email at 09:00 UTC.",
  "deliverables_count": 2,
  "success_criteria": [
    "A scheduled job sends an email containing realized PnL, win rate, and open position count once per day at 09:00 UTC.",
    "The email is absent when the live trader has no closed trades for that day."
  ],
  "open_questions": [
    "Which email address(es) should receive the report? Is this configurable per environment?"
  ]
}
```

`deliverables_count = 2` because the request implies a scheduled job (1) and an
email template (1). The parent routes to the small path (≤ 3).

### 6.2 Epic-sized request — "rework the strategy pipeline"

The agent recognises this as potentially large and spawns `research-agent` with
the question "which components does the strategy pipeline touch?" It receives a
summary naming the collector, enrichment procedures, backtest grid, evaluation
view, and live-trader match logic — five distinct areas.

It surfaces question 2 ("what changes for the system — faster evaluation,
different signals, or both?") and question 4 ("is live-trader match logic in
scope?"). After user answers:

```json
{
  "intent": "The system can now discover and evaluate strategies faster by replacing the sequential enrichment loop with a parallel procedure.",
  "deliverables_count": 5,
  "success_criteria": [
    "Enrichment run time for a 30-day window drops below 10 minutes on the production DB.",
    "All existing strategy signals continue to evaluate correctly after the rework.",
    "The live-trader match logic is unchanged (explicitly out of scope)."
  ],
  "open_questions": [
    "Should the parallel procedure use pg_background or a Python multiprocessing approach?",
    "Which enrichment indicators are candidates for parallelisation — all, or only the slow ones?"
  ]
}
```

`deliverables_count = 5 > 3`. `create-ticket` routes to `create-epic`.
`open_questions` flows into the epic's sub-ticket hardening passes.

---

## 7. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1),
  file layout (§2), internal visibility class (§3.3), tool allowlists (§4),
  strict research-delegation rule (§4.2).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) —
  upstream ADR: three-tier ladder (§2.1), tool allowlist + strict-research-
  delegation (§2.6).
- [`tickets/09_done/EPIC-CodingAgents/Master_Plan.md`](../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md) —
  locked design decisions; "business-analyst always runs first" rule; >3
  deliverables → create-epic routing rule.
- [`.claude/agents/business-analyst.md`](../../../.claude/agents/business-analyst.md) —
  the agent file itself (frontmatter + system prompt).
- [`.claude/agents/create-ticket.md`](../../../.claude/agents/create-ticket.md) —
  the parent orchestrator that spawns this agent.
- [Ticket 01](../../../tickets/09_done/EPIC-CodingAgents/01_business_analyst_agent.md) —
  the ticket that shipped this agent.
- [Ticket 04](../../../tickets/09_done/EPIC-CodingAgents/04_create_epic_agent.md) —
  `create-epic` (the route taken when `deliverables_count > 3`).
- [Ticket 05](../../../tickets/09_done/EPIC-CodingAgents/05_create_ticket_agent.md) —
  `create-ticket` (the orchestrator; routes on BA output).
- [`docs/agents/coding/test-planner.md`](../coding/test-planner.md) —
  `test-planner` (the sub-agent spawned by BA in Step 2; produces `test_requirements`).
- [`docs/testing/README.md`](../../testing/README.md) —
  portable testing conventions; source of truth for `testing_context` defaults.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
