---
title: "KI-TQ-20261102-sql-non-null-count-misses-count-star-where-not-null — the sql-test-writer non-NULL count pattern does not accept `COUNT(*) … WHERE <col> IS NOT NULL`, so a correct exact non-NULL count is scored falsely red"
description: "low — scripts/evals/sql_test_writer_eval/evidence_kinds.py non_null_re accepts only count(col), filter (where col is not null) and case when col is not null. A test that runs SELECT COUNT(*) FROM buy_volume_window WHERE symbol = ANY(%s) AND buy_volume IS NOT NULL and asserts it with an exact assertEqual fails sql_counts_rows_and_non_null. Failed twice on 2026-11-02 (first live run and re-run 1); re-runs 3 and 4 passed because the agent counted in Python instead."
type: reference
category: reference
status: active
created: '2026-11-02'
last_updated: '2026-11-02'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/reference/produced-tests-eval-assertion-kinds-sql-test-writer.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261025-sql-test-writer-eval-residual-misreads.md
---

# KI-TQ-20261102-sql-non-null-count-misses-count-star-where-not-null — a WHERE-filtered COUNT(*) is not read as a non-NULL count

> Filed 2026-11-02. Index: [testing-quality.md](../testing-quality.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** low. One SQL form of a correct non-NULL count is rejected, so the
  `empty-window-database-shape` row is falsely red when the agent picks that form; other forms
  pass.
- **Status:** open, no AC.
- **Occurrences:** 2 (2026-11-02 first live run and re-run 1, Windows 11, main `8248ac7a`).
  Re-run 2 crashed before scoring (see
  [KI-TQ-20261102-eval-temp-cleanup-error-crashes-the-run](open-low-ki-tq-20261102-eval-temp-cleanup-error-crashes-the-run.md));
  re-runs 3 and 4 passed because the agent counted the fetched rows in Python
  (`self.assertEqual(len(non_null_volumes), len(seeded))`,
  `self.assertEqual(sum(1 for v in values if v is not None), 3)`).
- **First seen:** 2026-11-02 · **Last seen:** 2026-11-02
- **Where:** `scripts/evals/sql_test_writer_eval/evidence_kinds.py` (line numbers on `171aafa5d`,
  unchanged since `8248ac7a`): `non_null_re` :68-72, used by `counts_rows_and_non_null` :101-117
  (:114); row `empty-window-database-shape` in `scripts/evals/sets/sql-test-writer.jsonl`.

## Symptom

`sql_counts_rows_and_non_null` fails with "the SQL counts no non-NULL buy_volume values, so an
empty or all-NULL window passes it" on a test that runs a non-NULL count in SQL and asserts it
exactly.

## Mechanism

`non_null_re(column)` (:68-72) matches three shapes only: `count(<col>)`,
`filter (where <col> is not null` and `case when <col> is not null`. Counting the rows that pass a
`WHERE` / `AND <col> IS NOT NULL` predicate with `COUNT(*)` is the same count, but neither
alternative matches it. `ROW_COUNT_RE` (:29) does match that `COUNT(*)`, so the query is read as a
second processed-row count. The Python-side fallback (`_python_side_counts` :90-98) does not rescue
it either: the assertion `self.cur.fetchone()[0] == len(_SEEDED_ROWS)` holds `len(` but no
`is not None`, so it too is a row count.

## Evidence

Kept output (local, not committed):
`<session scratchpad>/kept_runs/run1/sql-test-writer/empty-window-database-shape/files/unit_tests/sql_functions/test_buy_volume_window.py`:78-83:

```python
self.cur.execute(
    "SELECT COUNT(*) FROM buy_volume_window "
    "WHERE symbol = ANY(%s) AND buy_volume IS NOT NULL",
    (symbols,),
)
self.assertEqual(self.cur.fetchone()[0], len(_SEEDED_ROWS))
```

The executed-SQL resolver reads it as
`select count(*) from buy_volume_window where symbol = any(%s) and buy_volume is not null`, and
`non_null_re("buy_volume")` does not match it (checked directly with `executed_queries` and
`non_null_re` on 2026-11-02). Result in `run1-sql-test-writer.json`: `test_files_present` and
`db_test_uses_setting` passed, `sql_counts_rows_and_non_null` failed with the detail above. The
first live run (`../rerun_score/sql-test-writer.json`) failed the same kind with the same detail.

## Fix direction

- In `non_null_re` (or in `counts_rows_and_non_null`), accept a `count(*)` / `count(1)` whose own
  statement carries a `where` or `and <alias.>col is not null` predicate, checked within the same
  statement so a `col is not null` elsewhere in the file does not count.
- Update the `sql_counts_rows_and_non_null` entry in
  `docs/reference/produced-tests-eval-assertion-kinds-sql-test-writer.md` (:61-79), whose "Passes
  when" lists the three accepted forms, and add the WHERE form as a passing example.

**Related.** [KI-TQ-20261025-sql-test-writer-eval-residual-misreads](open-low-ki-tq-20261025-sql-test-writer-eval-residual-misreads.md)
records `count(all col)` as another form `non_null_re` misses.
