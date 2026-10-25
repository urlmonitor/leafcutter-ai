---
title: "KI-TQ-20261025-sql-test-writer-eval-rejects-valid-live-outputs — two sql-test-writer evidence kinds fail correct live outputs: the to-run-later check wants the function name inside the free-prose wrong version, and the empty-window check accepts only counts written in SQL"
description: "medium — found by the 2026-10-25 live before-score, where both database rows of the sql-test-writer set failed on correct outputs. (a) sql_to_run_later_names_wrong_version (scripts/evals/sql_test_writer_eval/evidence_kinds.py:42-46) requires the row's wrong_version_contains keyword, 'fn_refresh_due' (sql-test-writer.jsonl row 1), inside the wrong_version text, which the template asks for 'in your own words'; the live file named the function in every test node id and wrote wrong versions such as 'select refresh_due (retry_due parameter ignored entirely)', and failed. (b) sql_counts_rows_and_non_null (:74-89) looks for count(*) / count(col) / filter / case-when only inside executed SQL; the live test fetched the rows and asserted the processed-row and non-NULL counts in Python, which turns red on an empty or all-NULL window, and failed. Recorded gold scoring is unaffected."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261025-sql-test-writer-eval-residual-misreads.md
---

# KI-TQ-20261025-sql-test-writer-eval-rejects-valid-live-outputs — two evidence kinds are stricter than the template

> Filed 2026-10-25. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Both database rows of the sql-test-writer set failed on outputs that do
  what the template asks, so the live score (1/3) understates the agent by two rows and cannot
  reach its threshold for these reasons alone. The failures are falsely red, never falsely green.
  Recorded gold scoring (`--score-gold`) is unaffected: the gold outputs happen to use the forms
  the kinds accept.
- **Status:** open, no AC.
- **Occurrences:** 1 (the live before-score on 2026-10-25, Windows 11, `run_agent_eval.py
  --agent sql-test-writer` without `--score-gold`, results timestamp `2026-10-25T21:05:42Z`):
  - `stored-procedure-regression` failed only `sql_to_run_later_names_wrong_version`: "the
    to-run-later file names no wrong version of fn_refresh_due".
  - `empty-window-database-shape` failed only `sql_counts_rows_and_non_null`: "the SQL counts no
    processed rows and no non-NULL buy_volume values, so an empty or all-NULL window passes it".
  - Evidence: the run's Claude session transcripts,
    `C:\Users\Hendrik\.claude\projects\C--Users-Hendrik-AppData-Local-Temp-produced-tests-jsb-65kc-score-sandbox\`
    (`stored-procedure-regression`) and
    `C:\Users\Hendrik\.claude\projects\C--Users-Hendrik-AppData-Local-Temp-produced-tests-s59ge617-score-sandbox\`
    (`empty-window-database-shape`). They are local to the machine that ran the score.
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where** (line numbers at `origin/main` `5e5a37380`):
  - (a) `scripts/evals/sql_test_writer_eval/evidence_kinds.py`:42-46, `_real_wrong_version`:
    `keyword = spec.get("wrong_version_contains", spec["contains"])` (:44) and
    `keyword in str(entry.get("wrong_version", ""))` (:46). The same line also requires `::` and
    the function name in the `test` field, which the live file met.
  - (a) `scripts/evals/sets/sql-test-writer.jsonl`:1, the `stored-procedure-regression` row:
    `{"kind": "sql_to_run_later_names_wrong_version", "ac_id": "TQ-9501", "contains":
    "fn_refresh_due", "wrong_version_contains": "fn_refresh_due"}`.
  - (a) `templates/agents/sql-test-writer.md`:330, the to-run-later file format:
    `"wrong_version": "<the wrong version in your own words, non-empty>"`. Nothing asks for the
    function name in that field.
  - (b) `scripts/evals/sql_test_writer_eval/evidence_kinds.py`:74-89,
    `counts_rows_and_non_null`: the executed SQL that selects from the view (:84-85) must match
    `ROW_COUNT_RE` (:28, `count(*)` / `count(1)` not followed by `filter`) and `non_null_re`
    (:67-71, `count(col)`, `filter (where col is not null)` or `case when col is not null`), :86.
  - (b) `templates/agents/sql-test-writer.md`:219-224, the empty-window pattern: "Remedy: assert
    an exact count of processed rows plus a non-NULL count." It does not say where the count must
    be taken.

## Symptom

A live sql-test-writer run fails a database row although the output, read by hand, is correct:

- **(a)** The to-run-later file `TQ-9501.json` has `ac_id` `TQ-9501` and entries whose `test` is
  `unit_tests/sql_functions/test_fn_refresh_due.py::TestFnRefreshDue::<test>` (for example
  `test_retry_due_false_overrides_refresh_due_true`), with wrong versions "select refresh_due
  (retry_due parameter ignored entirely)", "select refresh_due or retry_due (OR instead of AND)",
  "select true (hardcoded true, ignoring both parameters)" and "select false (hardcoded false,
  ignoring both parameters)". Each is a real wrong version of `fn_refresh_due`; none contains the
  string `fn_refresh_due`, so the row fails.
- **(b)** The test runs `SELECT buy_volume FROM buy_volume_window WHERE symbol = %s ORDER BY
  buy_volume`, calls `fetchall()`, and asserts in Python
  `assertEqual(len(returned_volumes), len(seeded_volumes))` and that the count of returned values
  that are not `None` (and `>= 0`) equals `len(seeded_volumes)`. An empty window or an all-NULL
  window makes both assertions red, which is what the row tests for, yet the row fails.

## Mechanism

1. **(a) The keyword is searched in the wrong field.** The row's `wrong_version_contains` is the
   function name, and `_real_wrong_version` looks for it inside the prose. The template makes the
   prose free ("in your own words") and puts the function in the `test` node id, which the same
   check already verifies. An agent that describes the change itself ("select refresh_due …")
   rather than restating the function's name is rejected.
2. **(b) Only one form of the count is recognised.** The kind reads the SQL that reaches
   `.execute(...)` and looks for an aggregate. A test that fetches the rows and counts them in
   Python asserts the same two facts, but no aggregate appears in the SQL, so the kind reports
   "counts no processed rows and no non-NULL values". The template's remedy names the facts to
   assert, not the SQL form.
3. **Gold scoring stays green.** The recorded gold to-run-later file says "fn_refresh_due returns
   refresh_due alone, without the retry_due condition", and the recorded gold test runs `select
   count(*), count(buy_volume), min(buy_volume) from buy_volume_window`, so both kinds pass on
   gold and the gap shows only in live runs.

## Detection

On a live sql-test-writer run, a `sql_to_run_later_names_wrong_version` failure whose
to-run-later file holds entries with a `::` node id in `test_fn_refresh_due.py`, or a
`sql_counts_rows_and_non_null` failure whose test asserts `len(...)` of fetched rows and a
non-`None` count against the seeded rows, is this issue. Open the produced file or the session
transcript to tell it from a real miss.

## Workaround

Read such a failure by hand and, if the output matches the symptom above, count the row as
passing for the before-score. Do not change the agent template to put the function name into
the prose or to move the counts into SQL just to satisfy the kinds.

## Suggested fix

Directions only; nothing here is applied.

- **(a)** Accept an entry whose `test` names the function (already checked) and whose
  `wrong_version` names either the function or the changed condition, for example a
  `wrong_version_any_of: ["fn_refresh_due", "retry_due"]` list on the row in place of the single
  `wrong_version_contains`. Or drop the prose keyword and keep only the `test` check plus a
  non-empty `wrong_version`.
- **(b)** Also accept the Python-side form: rows fetched from the view and an exact
  `len(...)` assertion plus a count of non-`None` values asserted against a fixed or seeded
  number. Or, if counts in SQL are what is wanted, say so in `templates/agents/sql-test-writer.md`
  :219-224 and keep the kind as it is.
- Add both live outputs above as positive probes to the TQ-200d-2 kind tests either way.

**Related.** `KI-TQ-20261025-sql-test-writer-eval-residual-misreads` lists the residual misreads
of the same scoring left by the TQ-200d-2 reviews (among them `fetchall` / `read_sql` not treated
as executing calls); these two were not in it. `KI-TQ-20261025-test-runner-row-fails-on-quoted-checker-message`
is the matching scorer defect on the test-runner side of the same before-score.

**Pattern:** an evidence check stricter than the instruction it checks: the template asks for a
fact, and the check accepts only one way of writing it.
