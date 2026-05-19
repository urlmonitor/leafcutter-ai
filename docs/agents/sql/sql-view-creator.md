---
title: "Agent Reference: sql-view-creator"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
  - infrastructure
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "docs/how-to/database/create-view.md"
  - "docs/database-domain.md"
  - "tickets/09_done/EPIC-CodingAgents/19_sql_view_creator.md"
related_code:
  - ".claude/agents/sql-view-creator.md"
  - "sql_functions/views/"
  - "sql_functions/materialized_views/"
  - "unit_tests/sql_functions/"
---

# Agent Reference: `sql-view-creator`

Visibility class: **Internal** — only invoked by `sql-coder`.
Implementing agent: `sql-view-creator` (Sonnet).
Family: `coding/`.

This doc explains **when sql-coder routes here**, **what the agent produces**, **the three
flavours it handles**, and **how to extend it**.

---

## 1. When sql-coder Routes Here

`sql-coder` dispatches to `sql-view-creator` when the user's request maps to creating or
significantly changing a view of any kind.

| User request (via sql-coder) | Routed here? |
|---|---|
| "Create a view showing current trade status" | Yes — regular view |
| "Add a materialized view for daily candle statistics" | Yes — materialized view |
| "Create a continuous aggregate for 1h PnL per strategy" | Yes — CAG |
| "Add a new stored procedure for X" | No — `sql-procedure-creator` |
| "Create a SQL function for Y" | No — `sql-function-creator` |
| "Create a table for Z" | No — `sql-table-creator` |

`sql-coder` is the orchestrator. It dispatches here, then runs the appropriate reload command
and `sql-test`. `sql-view-creator` does **not** deploy or test — it authors files only.

---

## 2. Three Flavours

### 2.1 Regular View

- **File location**: `sql_functions/views/<view_name>.sql` (or domain subfolder)
- **Idempotency**: `CREATE OR REPLACE VIEW` — no DROP required unless the column set changes
- **Loaded by**: `db.create_views()`
- **Concrete examples**: `sql_functions/views/pnl_trades_v2.sql`, `sql_functions/views/strategies/01_view_strategy_metrics.sql`

### 2.2 Materialized View

- **File location**: `sql_functions/materialized_views/<mv_name>.sql`
- **Idempotency**: `DROP MATERIALIZED VIEW IF EXISTS <name> CASCADE; CREATE MATERIALIZED VIEW ... WITH NO DATA;`
- **Loaded by**: `db.create_materialized_views()`
- **Refresh owner**: always a Python worker or stored procedure — documented in the SQL file header
- **Concrete examples**: `sql_functions/materialized_views/candle_statistics_daily_mv.sql`, `sql_functions/materialized_views/mv_feature_usage_stats.sql`, `sql_functions/materialized_views/strategies/01_view_strategy_baselines.sql`

### 2.3 Continuous Aggregate (TimescaleDB CAG)

- **File location**: `sql_functions/caggs/<cagg_name>.sql`
- **Idempotency**: `remove_continuous_aggregate_policy (if_not_exists); DROP ... CASCADE; CREATE ... WITH (timescaledb.continuous); add_continuous_aggregate_policy;`
- **DDL mode**: AUTOCOMMIT required for the CREATE step
- **Loaded by**: manual AUTOCOMMIT pipe (no DatabaseManager loader yet — see Notes §6)
- **Refresh owner**: TimescaleDB background scheduler via `add_continuous_aggregate_policy`
- **Concrete examples** (dynamic, in code): `zz_candle_interval_{interval}_indicators_aggregates` in `database/view_creation/dynamic_views.py`

---

## 3. Inputs (Spec Contract)

`sql-coder` must supply all of the following before dispatching:

| Input | Required | Example |
|---|---|---|
| View name | Yes | `cagg_daily_pnl_summary` |
| Purpose (one sentence) | Yes | "Aggregates daily PnL per strategy" |
| Source table(s) | Yes | `pnl_trades_v2` |
| Business context | Yes | "Used by strategy-analytics workflow" |
| Epic / ticket reference | Yes | "EPIC-CandleContextMatches ticket 11" |
| For CAGs: bucket interval | Yes | `1 day` |
| For CAGs: refresh policy offsets | Yes or use defaults | `start_offset = 7 days, end_offset = 1 hour, schedule_interval = 1 day` |
| For mat views: refresh owner | Yes | "FeatureSyncWorker every 2h" |

If any required input is missing, `sql-view-creator` stops and asks before writing any file.

---

## 4. The How-To Doc

The agent's first action on every invocation is to load:

```
docs/how-to/database/create-view.md
```

That document is the **single source of truth** for all view authoring rules. This reference doc
summarises the rules; the how-to is authoritative on conflicts.

Key rules the agent enforces:

- Metadata header (`Object Name:`, `Dependencies:`, `Goal:`, `Business Context:`, `Performance Sensitivity:`, `Frequency:`, `Architecture:` mermaid). Enforced by `check-sql-dependencies` pre-commit hook.
- `DECISION HISTORY` block at the bottom of every SQL file.
- `WITH NO DATA` for materialized views (avoids blocking DB setup on initial schema load).
- `UNIQUE INDEX` on every materialized view and CAG (required for `CONCURRENTLY` refresh / CAG internal hypertable).
- CAG policy registration (`add_continuous_aggregate_policy`) is not optional.
- Test files follow rollback-only discipline; REFRESH and CAG create+refresh tests are `_MANUAL`.

---

## 5. Flavour-Decision Rubric and Error Protocol

The agent uses this rubric before writing any SQL:

| Signal in the request | Correct flavour |
|---|---|
| Query re-write over normal tables | Regular view |
| Aggregation over non-hypertable tables, refresh on demand/schedule | Materialized view |
| Aggregating time-series from a hypertable by `time_bucket()` | Continuous aggregate |

**Incompatible request protocol**: when the request cannot be satisfied by any flavour (e.g.
a CAG over a non-hypertable, or a CAG with LATERAL), the agent emits a structured `FLAVOUR ERROR`
and writes **no files**. This is the explicit guard against silently picking a regular view that
would scan the entire hypertable on every query.

---

## 6. Outputs

The agent produces exactly two files per invocation:

| File | Path |
|---|---|
| SQL file | Canonical location for the chosen flavour (see §2) |
| Test file | `unit_tests/sql_functions/test_<view_name>.py` |

It also returns a Completion Report with the reload command, pre-commit checklist, and any
caveats. `sql-coder` uses this report to drive the next steps.

---

## 7. Notes / Known Constraints

- **`sql_functions/caggs/` loader not yet in DatabaseManager.** The directory exists in the
  how-to as the canonical location for static CAG files, but `DatabaseManager` does not yet
  scan it. When the agent writes a CAG file there, it flags this in its Notes section.
  `sql-coder` is responsible for wiring the loader (a separate task, not this agent's scope).
- **Dynamic CAGs** (those built from Python configuration loops) live in
  `database/view_creation/dynamic_views.py` via `DynamicViewCreator` — they are not authored
  by this agent. If a request requires a dynamic CAG, route to `python-coder` for the
  `DynamicViewCreator` change.

---

## 8. Tool Allowlist and Research Delegation

Per [ADR-006 §2.6](../../architecture/ADR-006-agent-model-tiers.md#26-tool-allowlist--strict-research-delegation):

- `sql-view-creator` carries: `Bash, Read, Edit, Write, Agent`.
- `Grep`, `Glob`, and all MCP search tools are **removed**.
- Cross-file lookups (e.g. "is table X a hypertable?", "which worker refreshes MV Y?") are
  delegated to `research-agent` via the `Agent` tool.

---

## 9. What sql-coder Does After Receiving the Report

After `sql-view-creator` returns:

1. `sql-coder` runs the reload command appropriate for the flavour.
2. `sql-coder` invokes `sql-test` on the new test file (skipping `_MANUAL` tests).
3. `sql-coder` surfaces the combined result (files + deploy output + test outcome) to the user.

`sql-view-creator` does not participate in steps 1–3.

---

## 10. Cross-Links

- [docs/how-to/database/create-view.md](../../how-to/database/create-view.md) — canonical authoring rules loaded by this agent on every run.
- [docs/database-domain.md](../../database-domain.md) — hybrid schema management, reload commands, TimescaleDB specifics, observability surface.
- [docs/agents/conventions.md](../conventions.md) — frontmatter schema (§1), tool allowlists (§4), strict-research-delegation (§4.2).
- [docs/architecture/adrs/ADR-006-agent-model-tiers.md](../../architecture/ADR-006-agent-model-tiers.md) — model tier policy; Sonnet rationale.
- [docs/agents/coding/sql-view-creator.AGENT_FILE.md](sql-view-creator.AGENT_FILE.md) — the agent file itself (permission fallback location).
- [tickets/09_done/EPIC-CodingAgents/19_sql_view_creator.md](../../../tickets/09_done/EPIC-CodingAgents/19_sql_view_creator.md) — the ticket that shipped this agent.
- [tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md](../../../tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md) — the orchestrator that dispatches here.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
