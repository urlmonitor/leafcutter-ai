## sql-test-writer Report

**SQL object**: `sql_functions/views/buy_volume_window.sql`
**Test file**: `unit_tests/sql_functions/test_buy_volume_window.py`
**Framework**: unittest (default — no `PROJECT_CONTEXT.md` found; see note below)
**Slow-test marker**: `_MANUAL` (default; not needed — these tests run instantly)

**Test cases authored**:
- `test_all_rows_have_non_negative_buy_volume` — seeds 3 uniquely-tagged rows (0, 12, 1,000,000) and asserts exact row count, exact non-NULL count, exact zero negative-count, and exact per-symbol value match against the view.
- `test_absent_symbol_window_returns_no_rows` — a window with no matching trades returns exactly zero rows, not a swallowed/phantom row.

**Slow tests**: none

**Database check**: `invalid` — `testing_context.db_connection_test is not a valid postgres connection URL (expected postgres:// or postgresql:// with a safe host, port, and database segment).` The repo's `skills_config.json` still has the literal placeholder `postgresql://<user>:<password>@<host>:<port>/<database>`. Setting: `testing_context.db_connection_test`.
**Base ref used**: not applicable — no run was made.
**Pre-fix run**: not run: database check status is `invalid` (see above); `testing_context.db_connection_test`.
**Post-fix run**: not run: same reason.

**Three questions** (all `reasoned` — no run was made):
- `test_all_rows_have_non_negative_buy_volume` —
  Q1: smallest wrong change is `abs(buy_volume)` in the view, or returning `NULL::numeric`, or filtering `where buy_volume > 0`; the test now catches all three via exact-count and exact-value assertions instead of a loose `>= 0` bound. [reasoned]
  Q2: a view that abs()'s, nulls, or filters the data produces a value-mismatch, non-NULL-count mismatch, or row-count mismatch respectively — the fixture's 3 distinct, uniquely-tagged seed rows (including the 0-volume boundary row) produce exactly that result. [reasoned]
  Q3: no — the boundary (0) row and the other rows all pass through the same exact-count / exact-value assertions, not through separate logic. [reasoned]
- `test_absent_symbol_window_returns_no_rows` —
  Q1: a view returning a phantom/default row for any query. Caught by the exact `== 0` count. [reasoned]
  Q2: yes — a non-empty result for the absent-symbol query would fail the assertion. [reasoned]
  Q3: not applicable — single assertion, no control/negative pair.
- Vacuity checklist:
  1. Exact count, not one-sided bound — done (row count, non-NULL count, negative count, absent-symbol count are all `==`, never `>=`).
  2. Control row alongside negative check — done: the 0-volume boundary row is the control that must still appear; no DB-level negative row was inserted (risk of violating an unknown CHECK constraint on `trades`), so the negative-value transformation is instead defeated via the exact per-value round-trip assertion.
  3. Distinct new inputs vs old inputs — not applicable: this is a static data-invariant check on an existing view/table, not a new-branch code change with "old" vs "new" inputs.
  4. Collaborator call count — not applicable: pure SQL view test, no mocked collaborator.
- Wrong versions the tests now catch (all `reasoned`, not run this dispatch): `abs(buy_volume)` sign-hiding, `NULL::numeric` passthrough, `where buy_volume > 0` row-drop, phantom-row-on-empty-query.

**To run later**: written to `.git/leafcutter/to-run-later/TQ-9502.json` — the four wrong versions listed above (all unrun this dispatch).

**Syntax check**: OK (`python -m py_compile` exit 0)

**Run command**:
```
pytest unit_tests/sql_functions/test_buy_volume_window.py
```
(from `.claude/skills_config.json`'s `testing_context.test_command: "pytest"`; no `PROJECT_CONTEXT.md` was present, so the test folder and framework used the documented defaults.)

**Note**: `.agents/agents/sql-test-writer/PROJECT_CONTEXT.md` was not found; ran template-only with defaults (`unit_tests/sql_functions/`, `unittest`, `_MANUAL`). No `research-agent`/subagent dispatch tool was available in this session, so SQL-object and schema lookups were done directly with Serena's file tools rather than delegated — the `trades` table has no DDL in this repo, so the test seeds only the two columns (`symbol`, `buy_volume`) the view itself reads.