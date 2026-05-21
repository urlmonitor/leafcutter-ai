---
title: "Agent Reference: test-writer"
type: reference
status: active
created: 2026-05-13
last_updated: 2026-05-13
components:
  - infrastructure
related_docs:
  - "docs/agents/conventions.md"
  - "docs/agents/coding/test-planner.md"
  - "docs/agents/coding/test-runner.md"
  - "docs/testing/README.md"
related_code:
  - "leafcutter/templates/agents/test-writer.md"
---

# Agent Reference: `test-writer`

Visibility class: **phase** — dispatched by `ticket-supervisor`.
Implementing agent: `test-writer` (Sonnet).
Family: `coding/`.

This doc explains **when to use** the agent, **what it reads**, **what it
writes**, and **its sign-off contract**.

---

## 1. When to Use

`test-writer` is a **ticket-phase agent**. `ticket-supervisor` dispatches it
when the ticket has a non-empty `## Test Requirements` table:

```
ticket has test_requirements.tests array with ≥ 1 entry → test-writer: needed
ticket has empty test_requirements.tests array          → test-writer: not_needed
```

Do **not** invoke `test-writer` directly. Use `ticket-supervisor` as the entry
point (via `/build-feature` or the epic pipeline).

---

## 2. Dispatch Position

```
architect-review → python-coder → test-writer → test-runner → documentation-expert → pr-reviewer → commit → pull-request
```

`test-writer` runs **after `python-coder`** (which implements the production
code) and **before `test-runner`** (which runs the full test suite).

The SRP split: `test-writer` writes tests; `test-runner` runs them. They are
separate agents.

---

## 3. Pre-flight Reads

On every invocation, before writing any file, the agent reads:

1. The ticket body — finds the `## Test Requirements` section and parses the
   table.
2. `testing_context` from `.claude/skills_config.json` (or the default JSON
   fallback) — picks framework, constraints, and output rules.
3. `testing_context.readme_path` (the test README) — gets naming conventions
   and directory layout.
4. Confirms each `target_dir` exists (via `Bash ls`).

---

## 4. What It Writes

For each row in the `## Test Requirements` table, the agent writes one file:

```
<target_dir>/<name>.py
```

### Framework selection

| `testing_context.directories[dir].framework` | Pattern used |
|---|---|
| `"unittest"` | `unittest.TestCase` with `setUp`/`tearDown` |
| `"pytest"` | pytest functions/classes with `@pytest.fixture` |

### DB test pattern

For directories with `db_required: true`, the agent uses the transaction
rollback pattern:

```python
def setUp(self):
    self.conn = psycopg2.connect(DB_URL)
    self.conn.autocommit = False

def tearDown(self):
    self.conn.rollback()   # always
    self.conn.close()
```

Never `commit()` in test code. Never use `db.session_scope()`.

### Skeleton tests

If `python-coder` has not yet implemented the function under test, the agent
writes a skeleton that:
1. Imports the module (smoke test).
2. Asserts the function/class is importable.
3. Has a `TODO` comment marking what to assert once the implementation exists.

It does NOT write tests that unconditionally pass (`assertTrue(True)`).

---

## 5. Verification Run

After writing all test files, the agent runs only the new test files:

```bash
# unittest example
poetry run python -m unittest discover -s unit_tests/live_trader -t . -p "test_*.py"

# pytest example
poetry run python -m pytest unit_tests/sql_functions -v
```

Acceptable outcomes:
- **Green** — all pass. Ideal.
- **Yellow** — `AssertionError` failures because implementation is not yet done. Expected for spec-first tests; reported in the completion report.
- **Red** — `ImportError` or `SyntaxError`. Must be fixed before sign-off.

---

## 6. Completion Report

```
## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_foo_bar.py | unit_tests/live_trader/ | unittest | written |
| test_baz_MANUAL.py | unit_tests/sql_functions/ | pytest | written (manual) |

### Verification Run
- Command: <command run>
- Result: <green | yellow (N assertion failures) | red (N import errors)>

### Notes
<Any caveats: skeleton tests, missing implementations, manual tests, new directories created.>
```

---

## 7. Sign-off Contract

`test-writer` is a phase agent with `signoff: true`. On success it updates:
- Frontmatter: `test-writer: needed → signed_off`
- `## Sign-offs`: `- [ ] test-writer → - [x] test-writer — YYYY-MM-DD HH:MM`
- Appends a `## Comments` entry with `(status: ok)`.

On failure (unfixable import errors): sets `test-writer: failed` and appends
`(status: blocker)`.

---

## 8. Selection Criteria (Registry)

From `agent_registry.json`:

| Field | Value |
|---|---|
| `is_ticket_phase` | `true` |
| `tier` | `phase` |
| `default_status` | `needed` |

**Trigger conditions** (any one is sufficient):
- Ticket body contains a non-empty `test_requirements.tests` array.
- Ticket adds or modifies testable Python or SQL logic.
- `files_touched` includes paths under `unit_tests/`.

---

## 9. Cross-Links

- [docs/agents/coding/test-planner.md](test-planner.md) — produces the `test_requirements` spec that test-writer consumes.
- [docs/agents/coding/test-runner.md](test-runner.md) — runs the tests written by test-writer.
- [docs/testing/README.md](../../testing/README.md) — portable testing conventions.
- [leafcutter/templates/agents/test-writer.md](../../../templates/agents/test-writer.md) — the agent template itself.
- [leafcutter/config/skills_config.default.json](../../../config/skills_config.default.json) — default `testing_context` values.
