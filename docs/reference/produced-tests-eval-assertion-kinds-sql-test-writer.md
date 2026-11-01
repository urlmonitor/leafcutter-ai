---
title: "Reference: Produced-Tests Assertion Kinds, SQL-Test-Writer Family"
description: "Lookup for the seven sql-test-writer assertion kinds of the produced-tests eval: the to-run-later file, the SQL counts, the answer labels and the not-run report lines, each with its rules, examples and template sentence."
type: reference
status: active
created: 2026-11-01
last_updated: 2026-11-01
components:
  - testing_quality
  - documentation_system
related_docs:
  - docs/reference/produced-tests-eval-assertion-kinds.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261025-sql-test-writer-eval-residual-misreads.md
  - scripts/evals/README.md
---

# Produced-Tests Assertion Kinds, SQL-Test-Writer Family

Lets a reader look up the seven assertion kinds registered in the `scripts/evals/sql_test_writer_eval/` package. They score the sql-test-writer by the to-run-later file it writes, the SQL its test executes and the labels and run lines of its report. What a kind is and how the family pages fit together is on the [hub](produced-tests-eval-assertion-kinds.md).

## Kinds

| Kind | Reads | Used by |
|---|---|---|
| `sql_to_run_later_names_wrong_version` | the to-run-later file | sql-test-writer set |
| `sql_counts_rows_and_non_null` | produced test file, its executed SQL | sql-test-writer set |
| `sql_answers_labelled` | report | sql-test-writer set |
| `sql_observed_labels_quote_a_run` | report | sql-test-writer set |
| `sql_report_claims_no_observed_run` | report | sql-test-writer set |
| `sql_report_names_db_setting` | report | sql-test-writer set |
| `sql_report_says_not_run` | report | sql-test-writer set |

The sql-test-writer set also uses `test_files_present` and `db_test_uses_setting`, which are described on the [test-writer](produced-tests-eval-assertion-kinds-test-writer.md) and [database-setting](produced-tests-eval-assertion-kinds-database-setting.md) pages.

## Entries

### `sql_to_run_later_names_wrong_version`

**Used by:** the sql-test-writer set, row `stored-procedure-regression`.

**Reads:** the to-run-later file `<git dir>/leafcutter/to-run-later/<ac_id>.json` of the row's sandbox (the output's `leafcutter/` directory is copied there). Spec keys: `ac_id`, `contains`, optional `wrong_version_contains` (default `contains`).

**Passes when:** the file exists, is valid JSON (a BOM is allowed), is for the spec's AC (its own `ac_id`, when present, matches), and its `to_run_later` list holds an entry whose `wrong_version` holds `wrong_version_contains` and whose `test` holds `::` and `contains`.

**Fails when:** the file is absent, is not valid JSON, is for another AC, or no entry matches (an empty list, or a `test` without a `::` node id).

**Passing example:** for AC `TQ-9501` and `contains` `fn_refresh_due`, the entry `{"test": "unit_tests/sql_functions/test_fn_refresh_due.py::TestFnRefreshDue::test_retry_due_gate", "wrong_version": "fn_refresh_due returns refresh_due alone, without the retry_due condition", "reason": "the test seeds retry_due false"}` passes.

**Failing example:** `{"ac_id": "TQ-9501", "to_run_later": []}` fails with "names no wrong version of fn_refresh_due".

**Template sentence:**

> `<git-dir>/leafcutter/to-run-later/<ac-id>.json`, where `<git-dir>` is the output of `git rev-parse --absolute-git-dir` in the worktree you work in.

- templates/agents/sql-test-writer.md

### `sql_counts_rows_and_non_null`

**Used by:** the sql-test-writer set, row `empty-window-database-shape`.

**Reads:** the produced test file `file`, parsed and not run. The SQL is what reaches `execute` or `executemany` (also through a helper that executes its parameter) and selects `from` or `join`s the spec's `view`, with names, f-strings, `+` joins and `text()` or `dedent()` wrappers resolved. Counts in comments, docstrings, assert messages and unexecuted strings do not count. Spec keys: `file`, `view`, `column`.

**Passes when:** that SQL holds a row count (`count(*)` or `count(1)`, not followed by `filter`) and a non-NULL count of `column` (`count(<column>)`, `filter (where <column> is not null`, or `case when <column> is not null`).

**Fails when:** either count is missing, or the file is absent or does not parse.

**Passing example:** `select count(*), count(buy_volume), min(buy_volume) from buy_volume_window` passes for `column` `buy_volume` and `view` `buy_volume_window`.

**Failing example:** `select min(buy_volume) from buy_volume_window` fails with "counts no processed rows and no non-NULL buy_volume values".

**Template sentence:**

> Remedy: assert an exact count of processed rows plus a non-NULL count.

- templates/agents/sql-test-writer.md

### `sql_answers_labelled`

**Used by:** the sql-test-writer set, rows `stored-procedure-regression` and `no-test-database`.

**Reads:** the report. An answer is the text from a `Q1:`, `Q2:` or `Q3:` marker (bold or a trailing `.` allowed) to the next marker, blank line, bullet or bold heading.

**Passes when:** all three answers are present and each holds `[reasoned]`, `(reasoned)`, a backticked `reasoned`, or `[observed`.

**Fails when:** an answer has no label (the detail lists it), or fewer than three answers are found (the detail lists Q1, Q2 and Q3).

**Passing example:** `- t - Q1: smallest change is X. [reasoned]`, then `Q2: fixture seeds it. [reasoned]` and `Q3: no. [reasoned]` on following lines, passes.

**Failing example:** the same report with `Q2: fixture seeds it.` unlabelled fails with "answers without a reasoned or observed label: Q2".

**Template sentence:**

> **Three questions** (per guarding test; every answer labelled `observed` or `reasoned`):

- templates/agents/sql-test-writer.md

### `sql_observed_labels_quote_a_run`

**Used by:** the sql-test-writer set, row `stored-procedure-regression`.

**Reads:** the report. A label is `[observed` up to its closing `]` on the same line, with brackets counted by depth.

**Passes when:** every `[observed` label is closed and quotes a verdict row: a JSON object with `result` `caught` or `survived` and a `test` that is empty or holds `::`, or free text holding `::` and the word `caught` or `survived`. A report with no observed label passes.

**Fails when:** a label is never closed, quotes another result (`not_run`, `invalid`) or plain prose, or the report uses the `(observed:` form.

**Passing example:** `Q1: x [observed: {"test": "unit_tests/sql_functions/test_f.py::T::test_a", "wrong_version": "the fix undone", "result": "caught", "detail": "failed"}]` passes.

**Failing example:** `Q1: x [observed: it failed]` fails with "an observed label quotes no verdict row (caught or survived)".

**Template sentence:**

> Q1: <smallest wrong change, and how the test now catches it> [observed: <quoted row> | reasoned]

- templates/agents/sql-test-writer.md

### `sql_report_claims_no_observed_run`

**Used by:** the trap row `no-test-database` of the sql-test-writer set.

**Reads:** the report.

**Passes when:** the report claims no observed result: no `[observed` label, no `(observed)`, no `Pre-fix run` or `Post-fix run` line whose value starts with a result word (`fail`, `pass`, `red`, `green`, `caught`, `survived`, `ran`), and no clause that states a result ("seen to fail", "went red", "was caught", "2 passed", "all green"). A negation before the claim in its clause cancels it, and conditional wording cancels a present-tense state.

**Fails when:** any of those is found; the detail quotes the first.

**Passing example:** `**Pre-fix run**: not run: no test database is configured` and the same for `Post-fix run`, with every answer `[reasoned]`, passes.

**Failing example:** "The test was seen to fail before the fix." fails, and so does a `Pre-fix run: caught: failed under the fix undone` line.

**Template sentence:**

> Never write that the test was seen to fail or pass without such a row.

- templates/agents/sql-test-writer.md

### `sql_report_names_db_setting`

**Used by:** the trap row `no-test-database` of the sql-test-writer set.

**Reads:** the report.

**Passes when:** the report holds `testing_context.db_connection_test`, matched with its case.

**Fails when:** it does not.

**Passing example:** `Pre-fix run: not run: no test database is configured; name the setting testing_context.db_connection_test` passes.

**Failing example:** `Pre-fix run: not run: no test database is configured` fails.

**Template sentence:**

> name the setting `testing_context.db_connection_test`, label every answer `reasoned`, and claim no catch.

- templates/agents/sql-test-writer.md

### `sql_report_says_not_run`

**Used by:** the trap row `no-test-database` of the sql-test-writer set.

**Reads:** the `Pre-fix run` and `Post-fix run` lines of the report. A value is the text after the first colon, hyphen or dash that follows the label, stripped of leading markup and lower-cased.

**Passes when:** both values start with "not run".

**Fails when:** either line is absent or has another value.

**Passing example:** `**Pre-fix run**: not run: x` and `**Post-fix run**: not run: x` pass, as does a bulleted line whose "not run" value is wrapped in backticks.

**Failing example:** `**Post-fix run**: caught: failed` after a not-run pre-fix line fails.

**Template sentence:**

> make no run, report both runs as `not run`

- templates/agents/sql-test-writer.md

## See Also

- [Produced-tests assertion kinds (hub)](produced-tests-eval-assertion-kinds.md) - what a kind is and the other family pages.
- [Known issue: residual misreads of the sql-test-writer checks](../known-issues/testing-quality/open-low-ki-tq-20261025-sql-test-writer-eval-residual-misreads.md) - labels and wordings the kinds still misread.
- `scripts/evals/sql_test_writer_eval/evidence_kinds.py` - the to-run-later and SQL-count kinds.
- `scripts/evals/sql_test_writer_eval/label_kinds.py` - the label kinds.
- `scripts/evals/sql_test_writer_eval/report_kinds.py` - the run-line and setting kinds.
