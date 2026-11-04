---
title: "Reference: Produced-Tests Assertion Kinds, Test-Writer Family"
description: "Lookup for the ten test-writer assertion kinds of the produced-tests eval: what each reads, what passes and fails it, one passing and one failing example, and the test-writer template sentence it checks."
type: reference
status: active
created: 2026-11-01
last_updated: 2026-11-01
components:
  - testing_quality
  - documentation_system
related_docs:
  - docs/reference/produced-tests-eval-assertion-kinds.md
  - docs/reference/wrong-version-runs.md
  - scripts/evals/README.md
---

# Produced-Tests Assertion Kinds, Test-Writer Family

Lets a reader look up the ten assertion kinds that read the test files and the completion report of the test-writer, registered in `produced_tests_scoring.py`, `produced_tests_mutants.py` and `produced_tests_runs.py`. What a kind is and how the family pages fit together is on the [hub](produced-tests-eval-assertion-kinds.md).

## Kinds

| Kind | Reads | Used by |
|---|---|---|
| `fixture_seeds_moved_input` | produced test file | test-writer set |
| `counts_rows_and_non_null` | produced test file | test-writer set |
| `asserts_known_seeded_value` | produced test file | test-writer set |
| `test_files_present` | names of the produced test files | test-writer and sql-test-writer sets |
| `test_fails_on_wrong_result` | produced test file, run against an instrumented module | test-writer set |
| `fails_on_mutants` | produced test files, run against mutant copies | test-writer set |
| `produced_test_green` | produced test files, run on the fixture | test-writer set |
| `report_mentions` | completion report | test-writer and test-runner sets |
| `report_lists_wrong_version` | completion report | test-writer set |
| `wrong_version_run` | produced test files and a wrong-version run verdict | test-writer set |

## Entries

### `fixture_seeds_moved_input`

**Used by:** the test-writer set, row `input-moved-to-a-new-column`.

**Reads:** the produced test file named by `file`, parsed and not run. Spec keys: `file`, `column`, `old_column`.

**Passes when:** the file seeds at least one record (a dict literal with string keys, or a call with keyword arguments) that holds `column`, and every such record that also holds `old_column` gives `column` a literal value different from the literal value of `old_column`.

**Fails when:** the file is absent or does not parse; no record holds `column`; or a record holding both gives them equal values, or gives `column` a value that is not a literal.

**Passing example:** with `column` `cvd_delta_30` and `old_column` `cvd`, the record `{"symbol": "AAA", "cvd": 12.0, "cvd_delta_30": -4.0}` passes.

**Failing example:** the record `{"symbol": "AAA", "cvd": 12.0, "cvd_delta_30": 12.0}` fails, because a gate still reading `cvd` would pass; a file whose records hold only `cvd` fails too.

**Template sentence:**

> Every new input the change reads is seeded with values distinct from the old inputs, so the old input cannot satisfy the new branch.

- templates/agents/test-writer.md

### `counts_rows_and_non_null`

**Used by:** the test-writer set, row `empty-window`.

**Reads:** the produced test file named by `file`, parsed and not run.

**Passes when:** the file asserts both an exact processed-row count and a non-NULL count. A count is an `assert` that compares a call of the bare function `len`, `sum` or `count` (a method call such as `values.count(1)` is not one), or a name assigned from such a call, on the left, with an integer on the right. Without a `None` in the expression only `==` is an exact processed-row count. With a `None` in it, `==`, `> n` for `n` of 0 or more, and `>= n` for `n` of 1 or more are a non-NULL count.

**Fails when:** either count is missing, or the file is absent or does not parse. The detail starts with "the test asserts no".

**Passing example:**

```python
processed = len(values)
non_null = sum(1 for value in values if value is not None)
assert processed == 3
assert non_null == 3
```

**Failing example:** `assert all(value >= 0 for value in values)` alone fails, and so does the example above with `assert non_null >= 0` in place of the last line, because that bound admits an all-NULL window.

**Template sentence:**

> Remedy: assert an exact count of processed rows plus a non-NULL count.

- templates/agents/test-writer.md

### `asserts_known_seeded_value`

**Used by:** the test-writer set, row `presence-is-not-correctness`.

**Reads:** the produced test file named by `file`, parsed and not run.

**Passes when:** an `assert` holds an `==` comparison with a numeric literal (not a boolean) that an assignment elsewhere in the file also holds. Numbers inside `assert` statements are not seeds.

**Fails when:** no `==` assertion compares with an assigned numeric literal, or the file is absent or does not parse.

**Passing example:**

```python
feed = {"AAA": 1.5, "BBB": 2.0}
result = live_values(["AAA", "BBB"], feed)
assert result["AAA"] == 1.5
```

**Failing example:** `assert result["AAA"] is not None` fails (presence, not correctness), and so does `assert result["AAA"] == 9.0` when no assignment holds `9.0`.

**Template sentence:**

> Remedy: assert at least one known expected value seeded in the fixture.

- templates/agents/test-writer.md

### `test_files_present`

**Used by:** the test-writer set (rows `new-function-or-existing-code`, `configured-database`, `missing-setting-no-database-work`) and the sql-test-writer set.

**Reads:** the names of the test files in the output. A file is known by its base name, or by its sandbox-relative path when the base name is taken. Spec key: `files`.

**Passes when:** every name in `files` is among the produced test files.

**Fails when:** any named file is missing; the detail lists the missing names.

**Passing example:** row `new-function-or-existing-code` names `test_a_summarise_window.py` and `test_b_refresh_config.py`; an output holding both passes ("all 2 test file(s) present").

**Failing example:** an output holding only `test_a_summarise_window.py` fails with "missing test file(s): ['test_b_refresh_config.py']".

**Template sentence:** none - the names come from the row's request, and the template states no sentence about which files a request names.

### `test_fails_on_wrong_result`

**Used by:** the test-writer set, row `new-function-or-existing-code` (test B).

**Reads:** the produced test file `file`, run under pytest against a copy of `module` (default `<target>.py`) in which `target` records the running test after it returns.

**Passes when:** at least one case fails on an assertion (`assert` or `AssertionError` in its output) with `target` having returned during that case, and no failing case is an error or an import or missing-name error.

**Fails when:** the file is absent; nothing is collected; every case passes or is skipped; any failing case is an error or an import or missing-name error (absence), even when another case fails on an assertion; or no failing case reached `target` before failing (it failed before the call, through `pytest.fail`, or on an error of its own).

**Passing example:** with `target` `refresh_config`, `assert refresh_config({"retries": 0})["retries"] == 0` fails with `assert 3 == 0` on today's code, which replaces a falsy override with the default; the kind passes.

**Failing example:** a test that imports `refresh_config_v2` fails with "fails only at import or on a missing name (absence)".

**Template sentence:**

> rewrite that test to reach the existing code (no invented helper names) until its red is assertion-shaped.

- templates/agents/test-writer.md

### `fails_on_mutants`

**Used by:** the test-writer set, rows `empty-window`, `presence-is-not-correctness` and `input-moved-to-a-new-column`.

**Reads:** the produced test files (`files`, else all), run under pytest on the fixed fixture and again once per mutant. Each mutant in `mutants` replaces `module`, and the original is restored afterwards.

**Passes when:** the tests are green on the fixed code (at least one case, all passed) and every mutant makes at least one case fail or error.

**Fails when:** the tests are not green on the fixed code (a skip counts as not green), or any mutant leaves all cases passing or skipped; the detail names the survivors.

**Passing example:** row `empty-window` has mutants `drops_falsy_values` and `drops_last_row` of `buy_volume_window.py`. A test that asserts `processed == 3` and `non_null == 3` over a window holding a `0.0` value kills both.

**Failing example:** the same test with `assert processed >= 0` and `assert non_null >= 0` fails: "still passes against the mutant(s) ['drops_falsy_values', 'drops_last_row']".

**Template sentence:**

> When Q1 names a change that would keep the test green, strengthen the test until that change would turn it red

- templates/agents/test-writer.md

### `produced_test_green`

**Used by:** the test-writer set, rows `empty-window`, `presence-is-not-correctness` and `input-moved-to-a-new-column`.

**Reads:** the produced test files (`files`, else all), run under pytest on the fixture project as it stands.

**Passes when:** at least one case is collected and every case passes.

**Fails when:** nothing is collected, a case fails or errors, or a case is skipped or marked xfail.

**Passing example:** the `empty-window` test passes ("1 produced test(s) pass on the fixture").

**Failing example:** the same test with `assert processed == 4` fails ("failure: assert 3 == 4"); with `@pytest.mark.skip(reason='later')` it fails ("skipped: later").

**Template sentence:** none - this kind runs a finished test on code that already works, and the template states no sentence about a green run on the fixture.

### `report_mentions`

**Used by:** the test-writer set (rows such as `empty-window`, `configured-database`) and the test-runner set (rows `configured-database`, `missing-setting-database-work`).

**Reads:** the completion report (`report.md`). Spec key: `contains`.

**Passes when:** the report holds `contains` as a substring, ignoring case.

**Fails when:** it does not; the detail reads "report does not name '<contains>'".

**Passing example:** row `empty-window` has `contains` `non-NULL`; a report saying "the non-NULL buy_volume values (3)" passes.

**Failing example:** a report saying only "the check counts the values" fails.

**Template sentence:** none - `contains` is a per-row term of the fixture, and the kind quotes no template sentence.

### `report_lists_wrong_version`

**Used by:** the test-writer set, row `refresh-gate` (the report half of the row).

**Reads:** the completion report. Spec key: `contains`.

**Passes when:** a list item (`-`, `*`, `+` or numbered) under the first line holding "wrong versions the tests now catch", read up to the next line that starts with `#`, holds `contains`, ignoring case.

**Fails when:** no such item holds it: the line is absent, the list is empty, or the term sits only in prose.

**Passing example:** row `refresh-gate` has `contains` `retry_due`; the report line `- drop the retry_due condition` under "Wrong versions the tests now catch:" passes.

**Failing example:** the same report with the list reduced to `- the gate always allows`, and `retry_due` named only in an earlier sentence, fails.

**Template sentence:**

> Wrong versions the tests now catch: <list, including every `must_catch` entry>

- templates/agents/test-writer.md

### `wrong_version_run`

**Used by:** the test-writer set, row `refresh-gate` (the test half of the row).

**Reads:** the produced test files and the verdict of a wrong-version run. The kind finds the test functions tagged `# covers: <AC-ID>`, writes an AC record per id naming the row's `wrong_version` under `must_catch` for every tagged test, installs the `fixed` module, prepares the `altered` copy as the wrong version, and calls the shared runner ([wrong-version runs](wrong-version-runs.md)). Every tagged test runs on the fixed version and under the wrong version.

**Passes when:** at least one tagged test is `caught` for the wrong version, no tagged test fails on the fixed version, and no run is left unfinished. One catching test is enough: tagged tests that pass under the wrong version are not blocking in the eval (they would be in build work, where the shared verdict is unchanged). An untagged catching test never counts.

**Fails when:** no test carries a `# covers:` tag, every tagged test passes under the wrong version ("not caught by the runner (survivor)"), a tagged test fails on the fixed version, or the run is stopped or unfinished.

**Passing example:** four tests tagged `# covers: TQ-9201` (`test_refresh_fires_when_both_due`, `test_refresh_blocked_when_retry_not_due`, `test_refresh_blocked_when_refresh_not_due`, `test_refresh_blocked_when_neither_due`) all pass on the fixed version; the altered code drops `retry_due`, so only `test_refresh_blocked_when_retry_not_due` fails and the verdict is "caught 'drop the retry_due condition' by test_refresh_blocked_when_retry_not_due", with the other three listed as not blocking. Probe fixture: `unit_tests/evals/fixtures/tq200d-rerun/test-writer/refresh-gate/run1`.

**Failing example:** the same file without `test_refresh_blocked_when_retry_not_due` survives ("not caught by the runner (survivor)"); without its `# covers: TQ-9201` lines, the detail is "no '# covers: <AC-ID>' tagged test in the output".

**Template sentence:**

> each listed wrong version is a Q1 answer you must defeat first: every one must be a version the test would catch.

- templates/agents/test-writer.md

## See Also

- [Produced-tests assertion kinds (hub)](produced-tests-eval-assertion-kinds.md) - what a kind is and the other family pages.
- [Wrong-version runs](wrong-version-runs.md) - the runner behind `wrong_version_run`.
- `scripts/evals/produced_tests_scoring.py` - the registry and the static kinds.
- `scripts/evals/produced_tests_mutants.py` - `fails_on_mutants`, `produced_test_green`, `test_fails_on_wrong_result`.
- `scripts/evals/produced_tests_runs.py` - the sandbox and `wrong_version_run`.
