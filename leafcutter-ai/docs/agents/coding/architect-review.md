---
title: "Agent Reference: architect-review"
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
  - "tickets/09_done/EPIC-CodingAgents/03_architect_review_agent.md"
related_code:
  - ".claude/agents/architect-review.md"
  - ".claude/agents/architect-review-deep.md"
---

# Agent Reference: `architect-review`

Pattern: Gatekeeper Escalation (see [conventions.md §5.3](../conventions.md#53-gatekeeper-escalation)).
Implementing agents: `architect-review` (Sonnet gatekeeper) + `architect-review-deep` (Opus sub-agent).
Family: `coding/`.
Visibility: internal — invoked by `create-ticket` only.

---

## 1. When to Use

`architect-review` is an **internal** agent. Users do not invoke it directly.
`create-ticket` spawns it (in parallel with `refinement`) whenever
`business-analyst` returns `deliverables_count <= 3` for the small path, and
whenever any path requires architectural sign-off.

Do **not** invoke `architect-review` directly. Use `/create-ticket` as the
entry point.

---

## 2. Decision Flow

```
create-ticket
  └─ (parallel) architect-review   ← you are here
       ├─ 1. spawn research-agent  → blast-radius findings
       ├─ 2. classify: small | large  (rubric below)
       ├─ small → write inline note (Sonnet only)
       └─ large → spawn architect-review-deep (Opus)
                   └─ returns full plan + suggested ADR
```

---

## 3. Impact Classification Rubric

These thresholds are the canonical source. The agent file quotes them verbatim;
if the two ever diverge, this document wins.

The `research-agent` blast-radius call uses:

- `mcp__jcodemunch__get_blast_radius` — per-symbol affected-file list.
- `mcp__jcodemunch__get_dependency_graph` — module-boundary crossing.

### 3.1 Always-Large Triggers

Any one of the following forces **large** classification, bypassing all file and
component thresholds:

| Trigger flag | What it means |
|---|---|
| `has_alembic_migration: true` | Ticket requires a new or modified Alembic migration under `alembic/versions/`. |
| `has_hypertable_change: true` | Any schema change to a TimescaleDB hypertable (compression policy, chunk interval, retention policy, continuous aggregate). |
| `has_public_api_change: true` | Any change to the FastAPI public surface: `api/api.py`, request/response models, or endpoint paths. |
| `has_adr_contract_change: true` | Any modification to a file under `docs/architecture/adrs/ADR-*`, or to a data contract that an ADR names as binding. |

### 3.2 Threshold Rules

Applied **only** when no always-large trigger fires.

| Criterion | Small threshold | Large threshold |
|---|---|---|
| Affected files | ≤ 5 files | > 5 files |
| Affected components | 1 component | ≥ 3 components |
| Cross-module boundary | No — single top-level package | Yes — crosses package boundary (e.g. `live_trader/` + `models/`) |

**Component definitions** (project's top-level service boundaries):

| Component name | Covers |
|---|---|
| `live_trader` | `live_trader/` tree |
| `collector` | `app_setup.py`, `app_launcher.py`, and supporting collector modules |
| `dashboards` | `dashboards/` tree |
| `api` | `api/` tree |
| `model_trainer` | `trading_model/` tree |
| `trades_aggregator` | `trades_aggregator/` tree |
| `sql_functions` | `sql_functions/` tree |
| `models` | `models/` tree (SQLAlchemy ORM layer) |
| `alembic` | `alembic/` tree |

Two files in the same component = single-component; still small by this
criterion.

### 3.3 Suggested-ADR Trigger

When the change introduces a new cross-cutting policy decision not already
covered by an existing ADR (new abstraction, new constraint, new cross-component
contract), `architect-review` (or `architect-review-deep` for large cases)
recommends a new ADR file path:

```
docs/architecture/adrs/ADR-{NNN}-{kebab-topic}.md
```

NNN = highest existing ADR number + 1. Check `docs/architecture/` for the
current high-water mark (currently ADR-006).

---

## 4. Output Contract

`architect-review` always returns a structured JSON payload plus a mandatory
`## Escalation` section.

```json
{
  "architectural_note": "<one-paragraph note (small) or Opus plan summary (large)>",
  "acceptance_adjustments": ["<AC bullet>", "..."],
  "escalation": "none" | "opus",
  "escalation_reason": "<empty string when none; rubric trigger when opus>",
  "suggested_adr": "<docs/architecture/adrs/ADR-NNN-topic.md or null>"
}
```

The `## Escalation` section is **mandatory on every run** — even when no
escalation occurred. Callers (e.g. `create-ticket`) parse this section to log
the routing decision without re-reading the payload.

---

## 5. Worked Examples

### 5.1 Small-impact ticket — "Add --dump-positions CLI flag"

**Ticket summary:** Add a `--dump-positions` flag to `live_trader/main.py` that
prints open positions as JSON and exits.

**Research-agent findings:**

```json
{
  "affected_files": ["live_trader/main.py", "live_trader/cli.py"],
  "affected_components": ["live_trader"],
  "has_alembic_migration": false,
  "has_hypertable_change": false,
  "has_public_api_change": false,
  "has_adr_contract_change": false,
  "summary": "Two files in live_trader; no cross-component impact."
}
```

**Classification:** Small. 2 files ≤ 5; 1 component; no always-large trigger.

**architect-review output (Sonnet only):**

```json
{
  "architectural_note": "Two-file change confined to live_trader/. The flag should be handled at the CLI layer (live_trader/cli.py) rather than inside main() to keep the entry-point clean. No migration, no API surface, no ADR impact.",
  "acceptance_adjustments": [
    "Flag must be mutually exclusive with --live to prevent accidental trade execution during a dump run."
  ],
  "escalation": "none",
  "escalation_reason": "",
  "suggested_adr": null
}
```

```
## Escalation

Branch: none
Reason: 2 files in one component (live_trader/); no always-large trigger fired.
```

---

### 5.2 Large-impact ticket — "Add CME gap context pipeline"

**Ticket summary:** Add a new `cme_gap_context` table (hypertable), a
populator procedure, a live enrichment hook in `live_trader/`, a new API
endpoint, and a Dash panel.

**Research-agent findings:**

```json
{
  "affected_files": [
    "alembic/versions/0042_add_cme_gap_context.py",
    "models/cme_gap_context.py",
    "sql_functions/procedures/populate_cme_gap_context.sql",
    "live_trader/enrichment.py",
    "live_trader/strategy_matcher.py",
    "api/api.py",
    "dashboards/web_app.py",
    "dashboards/panels/cme_gap.py"
  ],
  "affected_components": ["alembic", "models", "live_trader", "sql_functions", "api", "dashboards"],
  "has_alembic_migration": true,
  "has_hypertable_change": true,
  "has_public_api_change": true,
  "has_adr_contract_change": false,
  "summary": "New hypertable, Alembic migration, public API endpoint, live_trader enrichment hook, and dashboard panel. Six components touched."
}
```

**Classification:** Large. Three always-large triggers fire simultaneously
(`has_alembic_migration`, `has_hypertable_change`, `has_public_api_change`).

**architect-review spawns `architect-review-deep` with the following prompt:**

---

#### Escalation Prompt Template (used for Opus sub-agent)

```
You are architect-review-deep, the deep architectural reviewer.

## Ticket

<full ticket text verbatim>

## Research-Agent Findings

<research-agent JSON findings block verbatim>

## Why This Exceeds the Small-Case Bar

<one-paragraph framing from architect-review>

Example: "Three always-large triggers fire: Alembic migration required
(has_alembic_migration=true), new TimescaleDB hypertable
(has_hypertable_change=true), and a new public FastAPI endpoint
(has_public_api_change=true). Six components are touched: alembic, models,
live_trader, sql_functions, api, dashboards. This is a cross-cutting pipeline
change that requires sequenced rollout and explicit API versioning."

## Your Task

Produce a full architectural plan per your instructions:
1. Impact summary
2. Risks (per-file/per-contract specifics)
3. Design decisions (preferred + one rejected alternative per risk)
4. Revised acceptance criteria ([added] bullets for new items)
5. ADR recommendation (or "No new ADR required.")
6. Implementation sequence (ordered for minimum blast radius)

Return the plan under those headings, followed by the structured JSON summary.
```

---

**architect-review output after receiving Opus plan:**

```json
{
  "architectural_note": "<Opus plan summary paragraph>",
  "acceptance_adjustments": ["<revised AC from Opus>", "..."],
  "escalation": "opus",
  "escalation_reason": "has_alembic_migration=true, has_hypertable_change=true, has_public_api_change=true — three always-large triggers; 6 components touched: alembic, models, live_trader, sql_functions, api, dashboards",
  "suggested_adr": "docs/architecture/adrs/ADR-007-cme-gap-context-pipeline.md"
}
```

```
## Escalation

Branch: opus
Reason: has_alembic_migration=true, has_hypertable_change=true,
has_public_api_change=true — three always-large triggers fired simultaneously;
escalated to architect-review-deep.
```

---

## 6. Cross-Links

- [`docs/agents/conventions.md §5.3`](../conventions.md#53-gatekeeper-escalation) —
  Gatekeeper Escalation pattern rules (model pin, Opus sub-agent file naming,
  mandatory `## Escalation` section).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md §2.3`](../../architecture/ADR-006-agent-model-tiers.md) —
  upstream ADR worked example for `architect-review`.
- [`tickets/09_done/EPIC-CodingAgents/03_architect_review_agent.md`](../../../tickets/09_done/EPIC-CodingAgents/03_architect_review_agent.md) —
  the ticket that shipped this agent.
- [`.claude/agents/architect-review.md`](../../../.claude/agents/architect-review.md) —
  agent file (Sonnet gatekeeper). **Fallback path during EPIC-CodingAgents
  worktree: `docs/agents/coding/architect-review.AGENT_FILE.md`.**
- [`.claude/agents/architect-review-deep.md`](../../../.claude/agents/architect-review-deep.md) —
  agent file (Opus sub-agent). **Fallback path during EPIC-CodingAgents
  worktree: `docs/agents/coding/architect-review-deep.AGENT_FILE.md`.**

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
