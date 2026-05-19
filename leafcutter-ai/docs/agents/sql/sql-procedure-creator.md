---
title: "Agent Reference: sql-procedure-creator"
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
  - "docs/how-to/database/create-procedure.md"
  - "docs/database-domain.md"
  - "tickets/09_done/EPIC-CodingAgents/17_sql_procedure_creator.md"
related_code:
  - ".claude/agents/sql-procedure-creator.md"
  - "sql_functions/procedures/"
  - "unit_tests/sql_functions/"
---

# Agent Reference: `sql-procedure-creator`

Visibility class: **Internal** — only invoked by `sql-coder`.
Implementing agent: `sql-procedure-creator` (Sonnet).
Family: `coding/`.

This doc explains **when sql-coder routes here**, **what the agent produces**, **the constraints it operates under**, and **how to extend it**.

---

## 1. When sql-coder Routes Here

`sql-coder` dispatches to `sql-procedure-creator` when the user's request maps to creating or significantly changing a stored procedure in `sql_functions/procedures/`.

| User request (via sql-coder) | Routed here? |
|---|---|
| "Create a procedure that backfills X for all symbols" | Yes |
| "Add a new stored procedure for Y" | Yes |
| "Create a SQL function for Z" | No — `sql-function-creator` |
| "Add a database view for W" | No — `sql-view-creator` |
| "Create a table for V" | No — `sql-table-creator` |

`sql-coder` is the orchestrator. It dispatches here, then runs `db.create_procedures()` and `sql-test` on the files this agent produces. `sql-procedure-creator` does **not** deploy or test — it only authors.

---

## 2. Inputs (Spec Contract)

`sql-coder` must supply all of the following before dispatching:

| Input | Required | Example |
|---|---|---|
| Procedure name | Yes | `procedure_backfill_candle_scores` |
| Purpose (one sentence) | Yes | "Computes and inserts candle score rows for unprocessed 1m candles" |
| Parameters (names, types, defaults) | Yes | `p_symbol TEXT, p_batch_size INT DEFAULT 200` |
| Source table(s) | Yes | `candles` |
| Target table(s) | Yes | `candle_scores` |
| Caller context | Yes | "Called by CandleScoreWorker every 30 seconds" |
| Epic / business reason | Yes | "EPIC-CandleScores — enables threshold-based signal detection" |
| Existing overloads to drop | If applicable | `procedure_backfill_candle_scores(text, int)` |

If any required input is missing, `sql-procedure-creator` stops and asks before writing any file.

---

## 3. Outputs

The agent produces exactly two files per invocation:

| File | Path |
|---|---|
| Procedure SQL | `sql_functions/procedures/procedure_<verb>_<noun>.sql` |
| Test file | `unit_tests/sql_functions/test_<procedure_name>.py` |

It also returns a structured report containing the reload command, the test command, and a pre-commit checklist. `sql-coder` uses this report to drive the next steps.

---

## 4. The How-To Doc

The agent's first action on every invocation is to load:

```
docs/how-to/database/create-procedure.md
```

That document is the **single source of truth** for all procedure authoring rules. This reference doc summarises the rules; the how-to is authoritative on conflicts.

Key rules the agent enforces:

- Header with `Object Name:`, `Goal:`, `Business Context:`, `Architecture:` (enforced by `check-documentation` pre-commit hook).
- Mermaid diagram for any file with `CREATE TEMP TABLE` or `CALL` statements (verified by `verify_mermaid_diagram()` in `doc_validators.py`).
- `DECISION HISTORY` block at the bottom of every SQL file.
- Parameters prefixed `p_`, variables prefixed `v_`.
- `RAISE NOTICE` logging at START and DONE with `CLOCK_TIMESTAMP()`.
- `GET DIAGNOSTICS` after every row-modifying DML statement.
- Rollback-only test discipline — no `session.commit()` in tests.
- Python module docstring with `MODULE:`, `GOAL:`, `BUSINESS CONTEXT:`, `ARCHITECTURE:` in the test file.

---

## 5. Idempotency Rules

The agent chooses between two patterns (documented in the how-to §3):

- **Pattern A** (`CREATE OR REPLACE` only) — for new procedures and signature-stable edits.
- **Pattern B** (`DROP IF EXISTS` on every overload + `CREATE OR REPLACE`) — when the parameter signature changes. The agent checks for existing overloads via `Bash` if uncertain.

Both patterns are safe to re-run against a running database. Running workers (collector, trader) are not interrupted because the procedure is replaced atomically.

---

## 6. Tool Allowlist and Research Delegation

Per [ADR-006 §2.6](../../architecture/ADR-006-agent-model-tiers.md#26-tool-allowlist--strict-research-delegation) and the strict-research-delegation rule:

- `sql-procedure-creator` carries: `Bash, Read, Edit, Write, Agent`.
- `Grep`, `Glob`, and all MCP search tools are **removed**.
- Cross-file lookups (e.g. "does table X have column Y?") are delegated to `research-agent` via the `Agent` tool.

---

## 7. What sql-coder Does After Receiving the Report

After `sql-procedure-creator` returns:

1. `sql-coder` runs the reload command: `db.create_procedures()`
2. `sql-coder` invokes `sql-test` on the new test file.
3. `sql-coder` surfaces the combined result (files + deploy output + test outcome) to the user.

`sql-procedure-creator` does not participate in steps 1–3.

---

## 8. Extending This Agent

To update the procedure authoring rules (e.g. a new required header field or a new logging convention):

1. Update `docs/how-to/database/create-procedure.md` (the how-to is the source of truth).
2. The agent picks up the change on its next invocation automatically — it loads the how-to at runtime.
3. If the change affects what the agent *writes* (not just what it reads), update the agent's system prompt at `.claude/agents/sql-procedure-creator.md`.
4. Update this reference doc to reflect the new rule.

---

## 9. Cross-Links

- [docs/how-to/database/create-procedure.md](../../how-to/database/create-procedure.md) — canonical authoring rules loaded by this agent on every run.
- [docs/database-domain.md](../../database-domain.md) — hybrid schema management, reload commands, observability surface.
- [docs/agents/conventions.md](../conventions.md) — frontmatter schema (§1), tool allowlists (§4), strict-research-delegation (§4.2).
- [docs/architecture/adrs/ADR-006-agent-model-tiers.md](../../architecture/ADR-006-agent-model-tiers.md) — model tier policy; Sonnet rationale.
- [.claude/agents/sql-procedure-creator.md](../../../.claude/agents/sql-procedure-creator.md) — the agent file itself.
- [tickets/09_done/EPIC-CodingAgents/17_sql_procedure_creator.md](../../../tickets/09_done/EPIC-CodingAgents/17_sql_procedure_creator.md) — the ticket that shipped this agent.
- [tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md](../../../tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md) — the orchestrator that dispatches here.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
