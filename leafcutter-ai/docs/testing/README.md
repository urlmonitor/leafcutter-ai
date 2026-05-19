---
title: "Portable Testing Conventions"
type: reference
status: active
created: 2026-05-13
last_updated: 2026-05-13
components:
  - infrastructure
related_docs:
  - "docs/agents/coding/test-planner.md"
  - "docs/agents/coding/test-writer.md"
  - "docs/agents/coding/test-runner.md"
  - "leafcutter/config/skills_config.default.json"
---

# Portable Testing Conventions

This document describes the test infrastructure conventions that the
`test-planner`, `test-writer`, and `test-runner` agents rely on. All three
agents read this knowledge from the `testing_context` block in
`skills_config.json` at runtime, so adopters can customize per-project.

> **Adopter note**: Copy `leafcutter/config/skills_config.default.json`
> into your project as `.claude/skills_config.json` and edit the
> `testing_context` block to match your test layout.

---

## Test Directory Structure

```
unit_tests/
  live_trader/          framework: unittest  db_required: false
  sql_functions/        framework: pytest    db_required: true
  model_retriever/      framework: unittest  db_required: false
  README.md             primary test reference (read by test-planner at runtime)
  sql_functions/
    README.md           SQL-specific test conventions
```

The `testing_context.directories` map in `skills_config.json` encodes this
structure. Agents use it to pick the correct framework and setUp/tearDown
pattern for each directory.

---

## Adding New Tests

### Naming Convention

All test files must match `test_*.py`. Test function and class names must also
start with `test_` (for unittest) or `test` (for pytest).

Pattern: `test_<module>_<behavior>.py`

Examples:
- `test_candle_score_worker_filter.py`
- `test_strategy_matcher_partial_fill.py`

### Directory Placement

Map the source module to the nearest matching `unit_tests/` subdirectory:

| Source module | Test directory |
|---|---|
| `live_trader/**` | `unit_tests/live_trader/` |
| `sql_functions/**` | `unit_tests/sql_functions/` |
| `trading_model/**` | `unit_tests/model_retriever/` |

If your project has no matching directory, note `"new directory needed"` in
the test entry's `target_dir` — the `test-writer` will create the directory.

---

## Framework Conventions

### unittest (live_trader, model_retriever)

```python
import unittest


class TestFooBar(unittest.TestCase):
    def setUp(self):
        # Minimal in-memory fixture; no DB
        self.subject = FooBar(param="value")

    def tearDown(self):
        # Release any resources (e.g. mock patches)
        pass

    def test_process_returns_expected_value(self):
        result = self.subject.process(input_data)
        self.assertEqual(result, expected_value)
```

Run: `poetry run python -m unittest discover -s unit_tests/live_trader -t . -p "test_*.py"`

### pytest (sql_functions)

```python
import pytest
import psycopg2


@pytest.fixture
def db_conn():
    conn = psycopg2.connect("postgresql://trader:trader@localhost:5403/LIVE")
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


def test_procedure_result(db_conn):
    cur = db_conn.cursor()
    cur.execute("CALL my_procedure(%s)", (param,))
    cur.execute("SELECT result FROM my_table WHERE id = %s", (id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == expected_value
```

Run: `poetry run python -m pytest unit_tests/sql_functions -v`

---

## Performance Constraints

Every auto-running test must complete in **≤ 5 seconds** (wall clock).

Tests that cannot meet this threshold must be marked manual by appending
`_MANUAL` to the test function name:

```python
def test_heavy_database_scan_MANUAL(self):
    """Manual: requires full DB table scan (~30s). Run with pytest -k _MANUAL."""
    ...
```

The pre-commit suite excludes `_MANUAL` tests. They are invoked explicitly:

```bash
python -m pytest unit_tests/ -k "_MANUAL"
```

---

## Test Output Rules

**Never write files to the project root or any project subdirectory.**

All test output (temp files, result artifacts, logs) must go to:
- `tmp_path` fixture (pytest) — automatically cleaned up.
- `tempfile.mkdtemp()` (unittest) — clean up in `tearDown`.
- `%TEMP%/bybit-trader-tests/` — shared test output dir for longer-lived artifacts.

The `testing_context.test_output_dir` config key holds this path.

---

## DB Test Patterns (Transaction Rollback)

For any test that exercises DB logic:

1. Open a connection in `setUp` / `@pytest.fixture`.
2. Set `autocommit = False`.
3. Run queries within the connection.
4. **Always rollback** in `tearDown` / fixture teardown — never commit.
5. Close the connection.

```python
# unittest pattern
def setUp(self):
    self.conn = psycopg2.connect(DB_URL)
    self.conn.autocommit = False

def tearDown(self):
    self.conn.rollback()   # <-- always
    self.conn.close()
```

**Never** use `db.session_scope()` in tests — it auto-commits, polluting DB
state and breaking test isolation.

---

## Pre-Commit Hook Behavior

The pre-commit suite runs automatically on `git commit`:

- **Always runs**: `unit_tests/live_trader/` (unittest discover) — fast, no DB.
- **Never runs automatically**: `unit_tests/sql_functions/` — requires a running
  DB container. Run manually before SQL changes: `poetry run python -m pytest unit_tests/sql_functions -v`.
- `_MANUAL` tests are excluded from both suites.

---

## Customizing per Project

Edit `testing_context` in your `.claude/skills_config.json`:

```json
{
  "testing_context": {
    "test_root": "unit_tests/",
    "readme_path": "unit_tests/README.md",
    "directories": {
      "my_module": { "framework": "unittest", "db_required": false },
      "integration": { "framework": "pytest", "db_required": true }
    },
    "max_test_duration_seconds": 5,
    "manual_test_suffix": "_MANUAL",
    "db_connection_test": "postgresql://myuser:mypass@localhost:5432/mydb",
    "naming_pattern": "test_*.py",
    "test_output_rules": "Never write to project dirs; use tmp_path or %TEMP%"
  }
}
```

The `test-planner` agent reads this config at runtime and uses `directories`
to produce valid `target_dir` values. The `test-writer` uses it to select the
correct framework and setUp pattern.

---

## Cross-Links

- [docs/agents/coding/test-planner.md](../agents/coding/test-planner.md) — planning-phase test expert
- [docs/agents/coding/test-writer.md](../agents/coding/test-writer.md) — execution-phase test authoring agent
- [docs/agents/coding/test-runner.md](../agents/coding/test-runner.md) — test execution agent
- [leafcutter/config/skills_config.default.json](../../config/skills_config.default.json) — default `testing_context` values
- [leafcutter/config/skills_config.schema.json](../../config/skills_config.schema.json) — JSON schema for `testing_context`
