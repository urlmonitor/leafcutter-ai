---
title: "Agent Reference: sql-coder"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "docs/database-domain.md"
related_code:
  - ".claude/agents/sql-coder.md"
  - ".claude/commands/sql-coder.md"
---

# Agent Reference: `sql-coder`

Implementing agent: `sql-coder` (Sonnet, user-facing, ORCHESTRATOR).
Family: `coding/`.

`sql-coder` is the user-facing entry point for SQL implementation. It does not
write SQL files itself — it dispatches to specialist sub-agents by artifact type
and owns the local-DB deploy + test-gate that turns "the file is written" into
"the change is verified."

---

## 1. When to Use

| User phrasing | Routes to |
|---|---|
| "create a procedure that …" | `sql-coder` → `sql-procedure-creator` |
| "I need a function for …" | `sql-coder` → `sql-function-creator` |
| "add an index on …" | `sql-coder` → `sql-index-creator` |
| "create a new table for …" | `sql-coder` → `sql-table-creator` |
| "make a continuous aggregate that …" | `sql-coder` → `sql-view-creator` |
| "refactor this procedure" | `sql-coder` (in-place edit, no specialist) |

For multi-artifact requests (e.g. "create a table + populating procedure +
index"), `sql-coder` dispatches to specialists sequentially in dependency order
and aggregates the manifests.

For Python-touching work (e.g. wiring a new procedure into a worker),
`sql-coder` owns the SQL portion and hands the Python part off to `python-coder`
via the Agent tool.

---

## 2. Required Pre-Flight Reads

Every run, before any specialist dispatch:

1. `docs/database-domain.md` — hybrid Alembic / `sql_functions/` rules,
   TimescaleDB specifics, observability surface.
2. Any ADR cited by the user.

The agent has no `Grep`, `Glob`, or MCP search tools. Cross-file lookups go
through `research-agent` per `docs/agents/conventions.md §4.2`.

---

## 3. Specialist Dispatch Contract

| Artifact | Specialist | How-to |
|---|---|---|
| Table | `sql-table-creator` | `docs/how-to/database/create-table.md` |
| Index | `sql-index-creator` | `docs/how-to/database/create-index.md` |
| Procedure | `sql-procedure-creator` | `docs/how-to/database/create-procedure.md` |
| Function | `sql-function-creator` | `docs/how-to/database/create-function.md` |
| View / CAG | `sql-view-creator` | `docs/how-to/database/create-view.md` |

Specialists return a structured manifest. They do not call back into
`sql-coder` — recursion is forbidden.

---

## 4. Local-DB Deploy Gate (Mandatory)

The local DB carries state across runs. Tests in `unit_tests/sql_functions/`
test the *previously-applied* version of an object. `sql-coder` always deploys
the changed SQL files to the local DB **before** running any test.

For procedures and functions:

```bash
poetry run python -c "from database import DatabaseManager; db = DatabaseManager('reload'); db.create_procedures()"
```

For other artifacts: see `docs/database-domain.md` § "SQL reload commands".

The deploy command output is included in the agent's final report.

---

## 5. Production Deploy Guardrail

`sql-coder` does NOT deploy to production. Prod deploys belong to the
`prod-deploy` agent (confirmation-gated, requires verbatim "yes deploy to prod").

If the user asks for a prod deploy:
1. Show the file diff.
2. Show before/after `pg_proc.length(prosrc)` if the change is a procedure.
3. Refuse to issue any `ssh root@brain.vierhenze.de` command.
4. Name `prod-deploy` as the correct entry point.

Cite `CLAUDE.md` § "Production Access" in the refusal.

---

## 6. Hand-Off to python-coder

When the ticket spans SQL + Python:
- `sql-coder` writes the SQL.
- `sql-coder` deploys locally + runs `sql-test`.
- `sql-coder` invokes `python-coder` via the Agent tool with a structured
  request naming the SQL artifacts and the integration point.
- `python-coder` writes the Python and returns.
- `sql-coder` produces the unified report.

`sql-coder` never edits Python files itself.

---

## 7. Final Report Schema

```
## Files Created / Modified
- <path> (created | modified) — <one-line purpose>

## Specialist Sub-Agents Invoked
- <name> — <artifact created>

## Local-DB Deploy
- Command, Result

## sql-test Results
- PASS / FAIL counts, failing test names

## Hand-Off
- python-coder: yes / no — what was handed off

## Anomalies
- (empty unless something warrants deeper review)
```

---

## 8. Cross-Links

- [`.claude/agents/sql-coder.md`](../../../.claude/agents/sql-coder.md) — the agent file.
- [`docs/database-domain.md`](../../database-domain.md) — canonical SQL rules.
- [`docs/agents/conventions.md`](../conventions.md) — frontmatter, tools, visibility.
- [`docs/agents/coding/python-coder.md`](python-coder.md) — hand-off counterpart.
- [`docs/agents/coding/database-agent.md`](database-agent.md) — local DB ops (apply migrations, reload, schema-check).
- [`docs/agents/coding/prod-deploy.md`](prod-deploy.md) — the prod-deploy agent this one defers to.
