---
title: "Agent Reference: sql-table-creator"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "docs/how-to/database/create-table.md"
  - "docs/database-domain.md"
  - "tickets/09_done/EPIC-CodingAgents/15_sql_table_creator.md"
  - "tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md"
related_code:
  - ".claude/agents/sql-table-creator.md"
  - "models/"
  - "alembic/versions/"
  - "sql_functions/schema/tables/"
---

# Agent Reference: `sql-table-creator`

Internal identifier: `sql-table-creator`.
Implementing agent: `.claude/agents/sql-table-creator.md` (Sonnet).
Family: `coding/` — dispatched by `sql-coder`.
Visibility: Internal — never auto-triggers; only invoked by `sql-coder`.

---

## 1. When `sql-coder` Dispatches Here

`sql-coder` dispatches to `sql-table-creator` whenever the user's request involves creating a **new table**. The routing rule from `sql-coder`'s system prompt:

> If the artifact type is "table (model + Alembic + component + docs)", dispatch to `sql-table-creator`.

Concrete triggers:

| User says | `sql-coder` dispatches |
|---|---|
| "create a new table called foo" | `sql-table-creator` |
| "add a queue_* table for X" | `sql-table-creator` |
| "I need a hypertable for Y" | `sql-table-creator` |
| "add a procedure to existing table" | NOT here — `sql-procedure-creator` |
| "add an index to existing table" | NOT here — `sql-index-creator` |

---

## 2. Inputs

`sql-coder` passes a **table spec** when it spawns this agent. The spec must include:

- Table name (snake_case, plural)
- Column list with types, nullability, and server defaults
- Constraints (unique, check, FK)
- Partial indexes (name, columns, WHERE predicate)
- `is_hypertable: true/false` — and if true: time column, partitioning column, chunk interval
- Owning component name in `docs/components.json` (or `none`)

If any field is missing, `sql-table-creator` returns an `## Anomalies` entry describing the gap and asks `sql-coder` to clarify before proceeding.

---

## 3. Outputs

`sql-table-creator` produces a structured payload listing every file it created or modified, plus the Alembic revision ID. `sql-coder` uses the revision ID to run `poetry run alembic upgrade head` and the file list to report what changed.

| Artifact | File | Always? |
|---|---|---|
| SQLAlchemy model | `models/<tablename>.py` | Yes |
| Alembic migration | `alembic/versions/<revision>_create_<tablename>_table.py` | Yes |
| `models/__init__.py` import | `models/__init__.py` | Yes |
| Idempotent schema SQL | `sql_functions/schema/tables/<tablename>.sql` | Recommended; skip for ephemeral queue tables unless instructed |
| `docs/components.json` entry | `docs/components.json` | Yes, if an owning component was specified |
| Hypertable SQL | `sql_functions/schema/hypertables/<tablename>.sql` | Only for hypertables |

---

## 4. Key Conventions (Summary)

The full rules are in `docs/how-to/database/create-table.md`. This section is a quick-reference for readers of this doc; the agent loads the how-to directly before writing.

### Naming

- File name = table name in snake_case (1:1 rule; known exception: `candle_relationship.py` → `candle_relationships`).
- Class name = PascalCase entity name.

### Column ordering (within model class)

1. Primary key (`id`)
2. Domain identity columns
3. Status / lifecycle columns
4. Optional metadata columns
5. Audit timestamps (`created_at`, `started_at`, `completed_at`, `error_message`)

### Migration idempotency

Every DDL op in `upgrade()` uses `IF NOT EXISTS`. Constraints use the `DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '...') THEN ALTER TABLE ... ADD CONSTRAINT ... END IF; END $$;` pattern. `downgrade()` is `DROP TABLE IF EXISTS <tablename>`.

### server_default rule

All timestamp columns that must be set by PostgreSQL use `server_default=text("NOW()")`, not Python `default=`.

---

## 5. Scope Boundaries

`sql-table-creator` authors files only. It does NOT:

- Apply the migration to any database (that is `sql-coder`'s role).
- Run tests (that is `sql-coder`'s role via `sql-test`).
- Create procedures, functions, or views that populate the new table (those go to `sql-procedure-creator` / `sql-function-creator`).
- Add standalone indexes to an existing table (that is `sql-index-creator`'s role).
- Dispatch back to `sql-coder` (no recursion).

---

## 6. Cross-Links

- [`docs/how-to/database/create-table.md`](../../how-to/database/create-table.md) — the canonical how-to the agent loads at runtime. Contains the full step-by-step, skeletons, and example commit references.
- [`docs/database-domain.md`](../../database-domain.md) — high-level hybrid-Alembic-vs-sql_functions rules (§ "Hybrid Schema Management").
- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1), tool allowlists (§4), internal visibility class (§3.3).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) — strict-research-delegation rule (§2.6); why search tools are absent from this agent's allowlist.
- [`tickets/09_done/EPIC-CodingAgents/15_sql_table_creator.md`](../../../tickets/09_done/EPIC-CodingAgents/15_sql_table_creator.md) — the ticket that shipped this agent.
- [`tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md`](../../../tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md) — the parent orchestrator (`sql-coder`) that dispatches here.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
