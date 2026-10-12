---
title: 'Agent Reference: test-runner'
type: reference
status: active
created: 2026-05-07
last_updated: 2026-09-28
components:
- infrastructure
- infrastructure
related_docs:
- docs/agents/conventions.md
- docs/architecture/adrs/ADR-033-agent-model-tiers.md
- unit_tests/README.md
- CLAUDE.md
related_code:
- .claude/agents/test-runner.md
- .claude/commands/test.md
description: 'Overview of Agent Reference: test-runner.'
---
# Agent Reference: `test-runner`

User-facing identifier: `/test` (slash command).
Implementing agent: `test-runner` (Sonnet).
Family: `coding/` — peer of `python-coder` and `sql-coder` in the implementation layer.

---

## 1. When to Use

| Trigger | Action |
|---|---|
| User types `/test` | `test-runner` auto-infers the right suite from `git diff` |
| User asks "run the tests" / "did I break anything?" | auto-triggers via description |
| `python-coder` or `sql-coder` needs inner-loop test feedback | spawn `test-runner` directly |
| User asks to run the SQL suite specifically | `/test sql-functions` |
| User wants to run everything | `/test all` |
| User wants a single file run | `/test single unit_tests/live_trader/test_foo.py` |

This agent owns the **mapping from changed files to test suite** and the
**failure-report structure**. It does NOT write or modify tests (that is
`python-coder` / `sql-coder`), does NOT deploy SQL (that is `database-agent`),
and does NOT own coverage reporting or continuous file-watching.

---

## 2. Routing Table

The agent inspects `git diff --name-only HEAD` (plus `git status --short` for
untracked files) and routes via this fixed table:

| Changed path pattern | Suite | Command |
|---|---|---|
| `live_trader/**` or `unit_tests/live_trader/**` | live-trader | `poetry run python -m unittest discover -s unit_tests/live_trader -t . -p "test_*.py"` |
| `sql_functions/**` or `unit_tests/sql_functions/**` | sql-functions | `poetry run python -m pytest unit_tests/sql_functions -v` |
| `trading_model/**` or `unit_tests/model_retriever/**` or `unit_tests/prediction_trader/**` | full-discover | `poetry run python -m unittest discover -s unit_tests -t . -p "test_*.py"` |
| Docs / tickets / config only | no-op | Asks user before running |
| Mixed (live_trader + sql_functions both changed) | both suites | live-trader first, then sql-functions |

The routing matches the canonical commands in `CLAUDE.md § "Run Tests"`. The
agent does not invent new commands — it maps to the existing surface.

---

## 3. Action Surface

```
/test [auto|live-trader|sql-functions|manual|all|single <path>]
```

| Action | Description |
|---|---|
| `auto` | Default — infer from diff |
| `live-trader` | Run live-trader suite unconditionally |
| `sql-functions` | Run SQL function suite (DB check first) |
| `manual` | Run `python -m pytest unit_tests/ -k "_MANUAL"` |
| `all` | Run both suites in order; warns about DB requirement |
| `single <path>` | Run one specific test file |

---

## 4. DB Pre-flight Check

For any suite that touches the database (`sql-functions`, `all`, `manual`),
the agent runs the shipped checker (`scripts/db_check/checker.py
--target-dir <project root>`) **before** invoking the suite. There is no
fixed host, port, or container — the checker resolves
`testing_context.db_connection_test` from the project's own
`skills_config.json` (against the project root, not the `.leafcutter`
install directory) and reports one of five statuses: `not_configured`,
`invalid`, `config_error`, `unreachable`, or `reachable`. It never prints a
password. On any status other than `reachable`, the test-runner stops before
running the suite and relays the checker's own report rather than composing
its own message, e.g.:

```
## DB Check Failed

<checker's reported status and message, relayed verbatim — one of
"not_configured", "invalid", "config_error", or "unreachable">

Rerun command once testing_context.db_connection_test is fixed and reachable:
  /test sql-functions
```

This satisfies the Gherkin AC: "on DB-not-running it stops with a clear
'start the database first' message instead of running the wrong suite" —
generalized to every non-`reachable` checker status, not only an unreachable
database.

---

## 5. Failure-Report Schema

Each failing test produces one record:

```
### Failure N: TestClass.test_name

File: relative/path/to/test_file.py
Failure type: assertion | import-error | setup-error | DB-fixture
Stacktrace excerpt:
  <last 5 lines of the traceback, trimmed to ≤120 chars per line>
Rerun command:
  poetry run python -m pytest <file>::<TestClass>::<test_name> -v
```

Failures are grouped by failure type. A combined summary follows:

```
## Summary

Suite: <suite-name>   Total failures: <N>
Suite rerun: <full suite command>
```

**Filtering rule:** structure removes stdout noise, not real failures. If a
failure cannot be cleanly parsed, a raw 20-line excerpt is included in the
record rather than suppressed.

---

## 6. No-op Rule

When `git diff` shows only docs, tickets, or config changes, the agent reports
"no test-relevant changes detected" and asks whether to run the full suite
instead of guessing. It does not auto-run any suite in this case.

---

## 7. Auto-trigger Note for python-coder / sql-coder

`python-coder` and `sql-coder` should invoke this agent after completing any
implementation pass that touches test-relevant paths. The agent is the inner-loop
gate: it selects the right suite, runs it, and hands back a structured failure
report or a clean pass. Implementation agents do not invoke `poetry run` or
`pytest` directly.

---

## 8. Relation to sql-test Skill

The `sql-test` skill (`.claude/skills/sql-test/SKILL.md`) is the canonical
reference for the SQL test commands. The `test-runner` agent's sql-functions
routing (`poetry run python -m pytest unit_tests/sql_functions -v`) is consistent
with that skill. The agent does not call the skill as a sub-process; it executes
the commands directly via Bash. The skill remains the user-facing reference for
manual SQL test runs.

---

## 9. Tool Allowlist Rationale

`tools: Bash, Read` — the Sonnet floor minus `Write` and `Edit`, which this
agent does not need (it does not modify test files). Search tools (`Grep`,
`Glob`, MCP tools) are removed per the strict-research-delegation rule
(`docs/agents/conventions.md §4.2`). For cross-file lookups, the user-facing
session routes through `research-agent`.

---

## 10. Cross-Links

- [`CLAUDE.md § "Run Tests"`](../../../CLAUDE.md) — canonical test commands.
- [`unit_tests/README.md`](../../../unit_tests/README.md) — test output rules
  (`tmp_path` / `test_output_dir`), no file output to project dirs, `_MANUAL`
  convention.
- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1),
  file layout (§2), tool allowlists (§4), strict-research-delegation (§4.2).
- [`docs/architecture/adrs/ADR-033-agent-model-tiers.md`](../../architecture/adrs/ADR-033-agent-model-tiers.md) — tier ladder (§2.1), tool policy (§2.6).
- [`.claude/skills/sql-test/SKILL.md`](../../../.claude/skills/sql-test/SKILL.md) — sql-test skill reference.
- [Ticket 26](../../../tickets/09_done/EPIC-CodingAgents/26_test_runner_agent.md) — the ticket that shipped this agent.
