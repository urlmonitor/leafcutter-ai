---
title: "Portable Testing Conventions"
type: reference
status: active
created: 2026-05-13
last_updated: 2026-06-04
components:
  - infrastructure
related_docs:
  - "docs/agents/coding/test-writer.md"
  - "docs/agents/coding/test-runner.md"
  - "leafcutter/config/skills_config.default.json"
---

# Portable Testing Conventions

This document describes the test infrastructure conventions that the
`test-writer` and `test-runner` agents rely on. Both agents read this
knowledge from the `testing_context` block in `skills_config.json` at
runtime, so adopters can customize per-project.

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
  README.md             primary test reference (read by test-writer at runtime)
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

The `test-writer` agent reads this config at runtime and uses `directories`
to produce valid `target_dir` values, selecting the correct framework and
setUp pattern.

---

---

## Fixture Convention (ADR-007)

**Agents are required to read this section.** `test-writer` and `python-coder`
are instructed in their system prompts to consult this file before authoring
tests. If you observe an agent inlining large data blobs (dicts with more than
5 keys, or parametrize tables with more than 3 rows) instead of using
`load_fixture()`, the agent prompt may have drifted — file a ticket to update
`templates/agents/test-writer.md` or `templates/agents/python-coder.md`.

Large test data blobs (dicts, expected-output structures, parametrize tables) MUST be
externalised to JSON files under `tests/fixtures/` and loaded via the `load_fixture()`
helper in `tests/conftest.py`. This keeps test files under the 500-line ceiling and
separates data concerns from test logic.

### Directory Layout

```
tests/
  conftest.py            ← load_fixture() helper (sole canonical location)
  fixtures/
    _shared/             ← fixtures used by two or more test modules
    <module>/            ← module = test file stem minus the test_ prefix
```

**Module-naming rule:** strip the `test_` prefix from the test file stem.

| Test file | Fixture subdirectory |
|---|---|
| `tests/test_build_clean.py` | `tests/fixtures/build_clean/` |
| `tests/test_build_pipeline.py` | `tests/fixtures/build_pipeline/` |
| Any multi-module fixture | `tests/fixtures/_shared/` |

### load_fixture() Signature

```python
from conftest import load_fixture

def load_fixture(name: str) -> Any:
    """Load a JSON fixture by slash-separated path relative to tests/fixtures/."""
    path = Path(__file__).parent / "fixtures" / f"{name}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
```

**Usage examples:**

```python
# Module-specific fixture
data = load_fixture("build_pipeline/valid_config")
# → tests/fixtures/build_pipeline/valid_config.json

# Shared fixture (used by multiple test modules)
schema = load_fixture("_shared/common_schema")
# → tests/fixtures/_shared/common_schema.json
```

The function raises `FileNotFoundError` naturally when the path does not exist —
no try/except suppression.

### When to Use _shared/ vs Module-Specific

| Situation | Location |
|---|---|
| Fixture used by exactly one test file | `tests/fixtures/<module>/` |
| Fixture used by two or more test files | `tests/fixtures/_shared/` |
| Fixture mirrors a production schema shared across modules | `tests/fixtures/_shared/` |

**Prefer module-specific locations.** Only move to `_shared/` when a second test file
genuinely needs the same data blob. Premature sharing creates unnecessary coupling.

### Agent Requirements

**Agents authoring or migrating tests MUST:**

1. Read this document before authoring or migrating test files.
2. Use `load_fixture()` whenever a test data blob would push the file past 500 lines.
3. Place new fixture files under `tests/fixtures/<module>/` (or `_shared/` when
   appropriate) following the module-naming rule above.
4. Every fixture file MUST be JSON with the `.json` extension.

This requirement applies to `test-writer`, `python-coder`, and any agent that produces
test files as part of its deliverable.

### Cross-Reference

- [docs/architecture/adrs/ADR-007-test-fixture-convention.md](../architecture/adrs/ADR-007-test-fixture-convention.md) — binding architectural decision
- `tests/conftest.py` — canonical implementation of `load_fixture()`
- `tests/fixtures/_shared/.gitkeep` — establishes the shared fixture directory in version control

---

## Cross-Links

- [docs/agents/coding/test-writer.md](../agents/coding/test-writer.md) — execution-phase test authoring agent
- [docs/agents/coding/test-runner.md](../agents/coding/test-runner.md) — test execution agent
- [leafcutter/config/skills_config.default.json](../../config/skills_config.default.json) — default `testing_context` values
- [leafcutter/config/skills_config.schema.json](../../config/skills_config.schema.json) — JSON schema for `testing_context`
