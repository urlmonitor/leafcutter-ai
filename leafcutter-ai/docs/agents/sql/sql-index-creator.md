---
title: "Agent Reference: sql-index-creator"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-08
components:
  - "infrastructure"
  - infrastructure
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "docs/how-to/database/create-index.md"
  - "docs/database-domain.md"
  - "tickets/09_done/EPIC-CodingAgents/16_sql_index_creator.md"
  - "tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md"
related_code:
  - ".claude/agents/sql-index-creator.md"
  - "sql_functions/schema/indexes/"
---

# Agent Reference: `sql-index-creator`

Visibility class: **Internal** — only invoked by `sql-coder`.
Implementing agent: `sql-index-creator` (Sonnet).
Family: `coding/`.

This doc explains **when sql-coder routes here**, **what the agent requires**,
**what it produces**, **the constraints it operates under**, and **how to
extend it**.

---

## 1. When sql-coder Routes Here

`sql-coder` dispatches to `sql-index-creator` when the user's request maps to
creating a new database index on an existing table.

| User request (via sql-coder) | Routed here? |
|---|---|
| "Create an index on table X column Y" | Yes |
| "The query filtering by symbol and open_time is slow — add an index" | Yes |
| "Add a GIN index on the divergence JSONB column" | Yes |
| "Create a SQL function for Z" | No — `sql-function-creator` |
| "Create a stored procedure for W" | No — `sql-procedure-creator` |
| "Create a new table" | No — `sql-table-creator` |

`sql-coder` is the orchestrator. It dispatches here, then runs the reload
command and surfaces the result to the user. `sql-index-creator` only authors
— it does not deploy.

---

## 2. Inputs (Spec Contract)

`sql-coder` must supply all of the following before dispatching:

| Input | Required | Example |
|---|---|---|
| Table name | Yes | `strategy_evaluation_cursors` |
| Column(s) + sort direction | Yes | `(symbol, historical_cursor_time DESC NULLS LAST, source_pipeline)` |
| Purpose (one sentence) | Yes | "Short-circuit ORDER BY + LIMIT in the live strategy matching hot path" |
| Caller / business context | Yes | "Called by LiveTrader every tick" |

If any required input is missing, the agent stops and returns a structured
"missing inputs" block before writing any file.

---

## 3. Outputs

The agent produces exactly **one file** per invocation (unless the target file
already exists, in which case it extends it):

| Output | Path |
|---|---|
| Index SQL file | `sql_functions/schema/indexes/<filename>.sql` |
| Structured report (in response) | Lists file path, index name, type, CONCURRENTLY decision, reload commands |

The agent does **not** produce a unit test file. Index files are applied
declaratively and verified by running the reload command against the database.

---

## 4. The How-To Doc

The agent's first action on every invocation is to read:

```
docs/how-to/database/create-index.md
```

That document is the **single source of truth** for all index authoring rules.
This reference doc summarises the rules; the how-to is authoritative on any
conflict.

Key sections the agent enforces:

| How-to section | What it covers |
|---|---|
| §1 — Confirmed Pattern | File-based, not Alembic; `IF NOT EXISTS`; location |
| §2 — File Naming | `<table>.sql` vs `<index>.sql`; `idx_<abbrev>_<purpose>` |
| §3 — File Header | Six required keys enforced by `documentation_guard.py` |
| §4 — Index Type Selection | BTREE / GIN / BRIN / partial / CONCURRENTLY rules |
| §5 — CONCURRENTLY Rules | When required; transaction-block restriction |
| §6 — Reload Mechanism | `execute_sql_from_directory`; pre-commit auto-apply |
| §7 — File Skeleton | Copy-paste template with all required sections |
| §8 — Pitfalls | GIN bloat, partial predicate IMMUTABLE rule, column order |

---

## 5. Idempotency Rules

Every `CREATE INDEX` statement must include `IF NOT EXISTS`. This is enforced
by the agent because the file is re-executed on every
`create_database_full_setup()` call. A plain `CREATE INDEX` will error on a
re-run against a database that already has the index.

For hot tables (>~100k rows in production), the agent uses `CREATE INDEX
CONCURRENTLY IF NOT EXISTS`, which builds the index without an
`AccessExclusiveLock`. CONCURRENTLY cannot run inside a transaction block —
the agent will flag this if the reload context requires a transaction.

---

## 6. Index Type Selection Summary

| Type | When to use | Codebase example |
|---|---|---|
| BTREE (default) | Equality, range, ORDER BY + LIMIT | `idx_csp_symbol_cursor_pipeline.sql` |
| GIN | JSONB `@>` containment, array overlap | `candle_context.sql` |
| BRIN | Append-only hypertable time columns | (rarely needed — hypertable chunking usually suffices) |
| Partial BTREE | Fixed `WHERE` predicate on stable column value | `idx_queue_strategy_mining.sql` (status = 'pending') |

See `docs/how-to/database/create-index.md §4` for full selection rules and
TimescaleDB-specific gotchas (compression `segmentby` overlap, UNIQUE index
partitioning column requirement).

---

## 7. Tool Allowlist and Research Delegation

Per [ADR-006 §2.6](../../architecture/ADR-006-agent-model-tiers.md#26-tool-allowlist--strict-research-delegation)
and the strict-research-delegation rule:

- `sql-index-creator` carries: `Bash, Read, Edit, Write, Agent`.
- `Grep`, `Glob`, and all MCP search tools are **removed**.
- Cross-file lookups (e.g. "does table X have column Y?", "is column Z already
  a compression segment key?") are delegated to `research-agent` via the
  `Agent` tool.

---

## 8. What sql-coder Does After Receiving the Report

After `sql-index-creator` returns:

1. `sql-coder` runs the reload command from the report:
   `db.execute_sql_from_directory('sql_functions/schema', recursive=True)`.
2. `sql-coder` surfaces the file path, index name, and deploy output to the
   user.

`sql-index-creator` does not participate in steps 1–2.

---

## 9. Extending This Agent

To update the index authoring rules (e.g. a new required header field, a new
pitfall, or a change in CONCURRENTLY thresholds):

1. Update `docs/how-to/database/create-index.md` (the how-to is the source of
   truth).
2. The agent picks up the change on its next invocation automatically — it
   reads the how-to at runtime.
3. If the change affects the agent's step logic (not just the content it
   writes), update the agent's system prompt at
   `.claude/agents/sql-index-creator.md`.
4. Update this reference doc to reflect the new rule.

---

## 10. Cross-Links

- [docs/how-to/database/create-index.md](../../how-to/database/create-index.md) —
  canonical authoring rules loaded by this agent on every run.
- [docs/database-domain.md](../../database-domain.md) —
  hybrid schema management overview, reload commands, observability surface.
- [docs/agents/conventions.md](../conventions.md) —
  frontmatter schema (§1), tool allowlists (§4), strict-research-delegation (§4.2).
- [docs/architecture/adrs/ADR-006-agent-model-tiers.md](../../architecture/ADR-006-agent-model-tiers.md) —
  model tier policy; Sonnet rationale.
- [.claude/agents/sql-index-creator.md](../../../.claude/agents/sql-index-creator.md) —
  the agent file itself.
- [tickets/09_done/EPIC-CodingAgents/16_sql_index_creator.md](../../../tickets/09_done/EPIC-CodingAgents/16_sql_index_creator.md) —
  the ticket that shipped this agent.
- [tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md](../../../tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md) —
  the orchestrator that dispatches here.
- [docs/agents/coding/sql-procedure-creator.md](sql-procedure-creator.md) —
  sister specialist for stored procedures.
- [docs/agents/coding/sql-function-creator.md](sql-function-creator.md) —
  sister specialist for SQL functions.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
