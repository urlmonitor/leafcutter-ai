---
title: 'Agent Reference: sql-function-creator'
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
- docs/how-to/database/create-function.md
- docs/database-domain.md
- tickets/09_done/EPIC-CodingAgents/18_sql_function_creator.md
- tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md
related_code:
- .claude/agents/sql-function-creator.md
- sql_functions/functions/
- unit_tests/sql_functions/
description: 'Overview of Agent Reference: sql-function-creator.'
---
# Agent Reference: `sql-function-creator`

Internal identifier: `sql-function-creator` (no slash command — internal only).
Implementing agent: `.claude/agents/sql-function-creator.md` (Sonnet).
Family: `coding/` — dispatched by `sql-coder`.

This doc explains **when sql-coder dispatches here**, **how the function vs.
procedure decision works**, **what the agent produces**, and where to find the
canonical how-to.

---

## 1. When sql-coder Dispatches Here

`sql-coder` dispatches `sql-function-creator` when the user's request requires
a SQL object that **returns a value** and can be called inside a `SELECT` or
`WHERE` clause.

| Signal in the request | sql-coder routes to |
|---|---|
| "I need a function that returns X" | `sql-function-creator` |
| "Create a helper that computes Y and can be used in queries" | `sql-function-creator` |
| "I need a SETOF / TABLE result from a query" | `sql-function-creator` |
| "I need a trigger function" | `sql-function-creator` (trigger function is still a function) |
| "I need a procedure that updates X" (side-effects, CALL) | `sql-procedure-creator` |
| "I need a batch runner that commits mid-flight" | `sql-procedure-creator` |

The dispatch decision is **deterministic**: if the caller needs the result in a
query, it is a function. If the caller runs it for side-effects with `CALL`, it
is a procedure.

`sql-function-creator` enforces this at Step 0 (dispatch guard) and will return
a redirect message if the request is actually a procedure.

---

## 2. Inputs

`sql-coder` passes the following context when spawning `sql-function-creator`:

1. The function specification (name, parameters, expected return type, business
   context / domain).
2. Any ticket or doc references that constrain the design.
3. The worktree path so the agent writes to the correct location.

---

## 3. Outputs

`sql-function-creator` produces exactly two files and one reload command:

| Output | Path |
|---|---|
| SQL function file | `sql_functions/functions/<subfolder>/<function_name>.sql` |
| Unit test | `unit_tests/sql_functions/test_<function_name>.py` |
| Reload command (in report) | `poetry run python -c "from database import DatabaseManager; db = DatabaseManager('reload'); db.create_functions()"` |

The agent also emits a structured design-decision record (language, volatility,
return type, idempotency choice) so `sql-coder` can verify the decisions are
correct before deploying.

---

## 4. How-To Reference

The canonical authoring guide is at:

```
docs/how-to/database/create-function.md
```

The agent loads this file at Step 1 of every invocation. Do not rely on
agent memory for the pattern rules — always read the how-to. Key sections:

| Section | What it covers |
|---|---|
| §2 — File Location | Which subdirectory to use for a given domain |
| §3 — File Header | Six mandatory fields; pre-commit enforces them |
| §4 — Idempotency | CREATE OR REPLACE vs. DROP + CREATE |
| §5 — Volatility | IMMUTABLE / STABLE / VOLATILE decision rules |
| §6 — Language | SQL vs. plpgsql vs. plpython3u — when each is appropriate |
| §7 — Return Type | Scalar / JSONB / TABLE / SETOF conventions |
| §8 — Decision History | Mandatory dated block at end of file |
| §9 — Reload Command | `db.create_functions()` — includes Python-generated functions |
| §10 — Test Pattern | setUp load + tearDown rollback; never session_scope() |
| §11 — Skeletons | Copy-paste templates for all three language choices |

---

## 5. Function vs. Procedure — Why This Matters for sql-coder

The two specialists are hard-separated because PostgreSQL's function/procedure
distinction has concrete consequences:

| Dimension | Function | Procedure |
|---|---|---|
| Called with | `SELECT fn()` or `WHERE fn() = X` | `CALL proc()` |
| Returns | A value (scalar, JSONB, TABLE, etc.) | Nothing (OUT params optional) |
| COMMIT inside | Not allowed | Allowed |
| IMMUTABLE allowed | Yes (if deterministic) | Never |
| Inline by planner | Yes (SQL IMMUTABLE functions) | No |
| Created in | `sql_functions/functions/` | `sql_functions/procedures/` |
| Reloaded with | `db.create_functions()` | `db.create_procedures()` |

Incorrect routing (procedure written as a function or vice versa) causes:
- Wrong reload command used, leaving stale objects in DB.
- COMMIT/ROLLBACK errors at runtime if a procedure's logic ends up in a function.
- Missed IMMUTABLE optimisation if a pure-computation function is wrongly typed
  as a procedure (procedures can never be IMMUTABLE).

---

## 6. Volatility — the Highest-Impact Decision

The agent explicitly cites a rule from `docs/how-to/database/create-function.md §5`
for every volatility marker it picks. The project conventions in brief:

- **IMMUTABLE**: result depends only on arguments — no DB reads, no clocks, no
  randomness. Example: `interval_to_duration`, `get_next_candle_start`, all
  `func_ft_*` text helpers, `func_translate_context_group`.
- **STABLE**: reads DB state but does not modify data; consistent within a
  transaction. Use when a function SELECTs from tables.
- **VOLATILE**: has side-effects, calls `random()`, reads sequences, or the
  result varies across calls with the same arguments. PLPython3u functions that
  call `plpy.execute()` are at minimum VOLATILE.

A wrong IMMUTABLE on a function that reads tables can cause stale query results
(the planner caches the result and does not re-evaluate). A wrong VOLATILE on a
pure-computation function defeats plan caching and constant folding.

---

## 7. Cross-Links

- `docs/how-to/database/create-function.md` — the authoritative pattern guide.
- `docs/database-domain.md` — hybrid schema overview and reload command reference.
- `.claude/agents/sql-function-creator.md` — the agent file (frontmatter + system prompt).
- `tickets/09_done/EPIC-CodingAgents/18_sql_function_creator.md` — the
  ticket that shipped this agent.
- `tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md` — the
  orchestrator that dispatches here.
- `docs/agents/coding/sql-procedure-creator.md` — sister specialist; see §5
  above for the function vs. procedure decision table.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
