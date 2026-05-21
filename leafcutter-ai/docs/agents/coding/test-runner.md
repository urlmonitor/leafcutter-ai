---
title: "Agent Reference: test-runner"
type: reference
status: active
created: 2026-05-13
last_updated: 2026-05-13
components:
  - infrastructure
related_docs:
  - "docs/agents/conventions.md"
  - "docs/agents/coding/test-writer.md"
  - "docs/testing/README.md"
related_code:
  - "leafcutter/templates/agents/test-runner.md"
---

# Agent Reference: `test-runner`

Visibility class: **phase** — dispatched by `ticket-supervisor`.
Implementing agent: `test-runner` (Sonnet).
Family: `coding/`.

This doc explains **what the agent does**, **its dispatch position**, **the
routing table it uses**, and **its output contract**.

---

## 1. Role and Boundaries

`test-runner` is a **pure executor**. It decides which test suite to run,
runs it, and returns structured output.

It does **not**:
- Write test files (that is `test-writer`'s job).
- Author code fixes.
- Search the codebase (Grep/Glob are not in its allowlist — see §5).

---

## 2. Dispatch Position

```
architect-review → python-coder → test-writer → test-runner → documentation-expert → pr-reviewer → commit → pull-request
```

`test-runner` runs **after `test-writer`**. When dispatched by
`ticket-supervisor`, it should check `git diff --name-only HEAD` for new
`test_*.py` files added by `test-writer` and include those files in its
routing decision — routing to the suite matching their directory even if no
non-test source files changed in that directory.

---

## 3. Routing Table

| Changed path pattern | Suite | Command |
|---|---|---|
| `live_trader/**` OR `unit_tests/live_trader/**` | live-trader | `poetry run python -m unittest discover -s unit_tests/live_trader -t . -p "test_*.py"` |
| `sql_functions/**` OR `unit_tests/sql_functions/**` | sql-functions | `poetry run python -m pytest unit_tests/sql_functions -v` |
| `trading_model/**` OR `unit_tests/model_retriever/**` | full-discover | `poetry run python -m unittest discover -s unit_tests -t . -p "test_*.py"` |
| Docs / tickets / config only | no-op | *(see No-op rule)* |
| Mixed (live_trader + sql_functions) | both suites | Run live-trader first, then sql-functions |

---

## 4. Actions

| Action | Meaning |
|---|---|
| `auto` (default) | Infer suite from `git diff` using the routing table. |
| `live-trader` | Run the live-trader suite unconditionally. |
| `sql-functions` | Run the SQL function suite (check DB first). |
| `manual` | Run `python -m pytest unit_tests/ -k "_MANUAL"`. |
| `all` | Run live-trader, then sql-functions. |
| `single <path>` | Run one specific test file. |

---

## 5. Delegation Rule

`test-runner` has no search tools (`Grep`, `Glob`, MCP tools are not in its
allowlist). For cross-file or symbol-level questions, it surfaces the question
to the user-facing session and asks them to route it through `research-agent`.

---

## 6. Output Contract

### Success

```
## Test Results — <suite-name>

Status: PASS
Tests run: <N>   Failures: 0   Errors: 0   Skipped: <S>
Elapsed: <T>s
```

### Failure

```
### Failure <N>: <TestClass.test_name>

File: <relative/path/to/test_file.py>
Failure type: <assertion | import-error | setup-error | DB-fixture>
Stacktrace excerpt:
  <last 5 lines of the traceback, trimmed to ≤120 chars per line>
Rerun command:
  poetry run python -m pytest <file>::<TestClass>::<test_name> -v
```

---

## 7. Sign-off Contract

`test-runner` is a phase agent with `signoff: true`. On success it updates:
- Frontmatter: `test-runner: needed → signed_off`
- `## Sign-offs`: `- [ ] test-runner → - [x] test-runner — YYYY-MM-DD HH:MM`
- Appends a `## Comments` entry with `(status: ok)`.

---

## 8. Cross-Links

- [docs/agents/coding/test-writer.md](test-writer.md) — writes the test files that test-runner runs.
- [docs/agents/coding/test-planner.md](test-planner.md) — produces the test spec consumed by test-writer.
- [docs/testing/README.md](../../testing/README.md) — portable testing conventions.
- [leafcutter/templates/agents/test-runner.md](../../../templates/agents/test-runner.md) — the agent template itself.
