---
title: "KI-TQ-20261012-nested-pytest-session-walks-system-temp — test_bo_4400f_2's nested pytest session keeps its suite under the system Temp folder, so pytest's collection walk lists and lstats all of Temp and crashes when another process deletes an entry mid-collection"
description: "low — the helper run_session puts the synthetic suite in a TemporaryDirectory and runs pytest with -c/--rootdir at the repo. pytest then collects every directory from just below the common ancestor (C:\\Users\\<user>) down to the suite: AppData, Local, Temp (about 29,000 entries here), and on Windows it lstats every non-matching child. If any concurrent process deletes a Temp entry in between, collection errors with FileNotFoundError, the run reports 'collected 0 items / 1 error', and the vacuity guard fails three tests. Reproduced on pristine origin/main and on a feature branch on 2026-10-12."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20260928-windows-pytest-collection-flake.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20260914-tempdir-cleanup-race-fails-a-green-test-run.md
---

# KI-TQ-20261012-nested-pytest-session-walks-system-temp — the nested session's collection walk crosses all of Temp

> Filed 2026-10-12. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. The failure is loud. The vacuity guard refuses a session that ran nothing, so
  nothing passes wrongly. The cost is a red run that has nothing to do with the change under test,
  and it is likeliest exactly when the suite runs in parallel.
- **Status:** open, no AC. The mechanism was confirmed against the installed pytest 9.1.1 source.
- **Occurrences:** several runs on 2026-10-12. The failure reproduced on pristine origin/main and on
  a feature branch alike. With a quiet Temp, 6 of 6 attempts passed. With another process churning
  Temp, for example a parallel `pytest -n 7`, 0 or 1 of 6 passed. It first looked like a strict-mode
  failure, but it is not.
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:** `unit_tests/build_orchestration/_bo4400f2_helpers.py` on origin/main `e93eda09a`:
  - `run_session` (:115-156) creates the suite in `tempfile.TemporaryDirectory(prefix="bo4400f2_")`
    (:121, :128). It runs `pytest -c <repo>/pytest.ini --rootdir <repo> ... <suite>` (:146-150)
    with `cwd=suite` (:153).
  - `default_run` (:162-166) caches one session for the first three tests.

  In `unit_tests/build_orchestration/test_bo_4400f_2.py`, the guard is
  `_assert_session_really_ran` (:28-33).

## Symptom

The nested session prints `collected 0 items / 1 error`. The error is a
`FileNotFoundError ... lstat` raised from pytest's collection, naming an entry under
`AppData\Local\Temp` that the test never touched. `_assert_session_really_ran` then fails on
`tests_that_ran == 3`.

All three tests that share the default session fail together:

- `test_passing_tests_leave_no_scratch_anywhere`
- `test_failing_test_scratch_retained_in_scratch_location_and_printed`
- `test_no_scratch_written_inside_project_or_durable_folders`

The fourth test, `test_durable_basetemp_stops_run_before_any_test`, has a control run at :98-101
that uses the same helper and asserts that 3 tests ran. It is exposed in the same way, though it
was not seen failing.

## Mechanism (pytest 9.1.1, `.venv/Lib/site-packages/_pytest/`)

1. **The walk's upper bound is the repo, not the suite.** With `-c <ini>`, `confcutdir` defaults
   to the ini file's directory, the repo root (`config/__init__.py:1599-1603`). Session collection
   prepends each parent of the argument path until it reaches one that is an ancestor of
   `confcutdir` (`main.py:919-928`, with `_is_in_confcutdir` at `config/__init__.py:669-682`). The
   suite is `C:\Users\<user>\AppData\Local\Temp\bo4400f2_<x>\suite`, and the first shared ancestor
   is `C:\Users\<user>`. So pytest collects `AppData`, `Local`, `Temp`, `bo4400f2_<x>` and `suite`,
   one level at a time. `--rootdir` does not shorten this.
2. **Every level is listed and compared.** At each level pytest collects the directory, which
   lists all of its entries, and prunes the nodes that are not on the path. On Windows, any node
   whose path is not equal to the target is compared with `samefile_nofollow` (`main.py:986-994`).
   That calls `lstat()` on both paths (`pathlib.py:1049-1054`). In `Temp` that is one `lstat` per
   entry, about 29,000 here (29,298 counted on 2026-10-12).
3. **A deletion between listing and `lstat` is fatal.** If another process removes a Temp entry
   after the listing and before its `lstat`, the `FileNotFoundError` propagates out of session
   collection as one collection error, and no test runs.

## Detection

A `test_bo_4400f_2` failure whose captured output shows `collected 0 items / 1 error` and a
`FileNotFoundError` naming a path under the system Temp folder rather than under the suite.

## Workaround

Run these tests while no other pytest or tool is churning Temp, or run them on their own after a
parallel run. Untested: point `TEMP`/`TMP` for the outer pytest at a quiet directory near a drive
root, which keeps the walk out of `AppData\Local\Temp`.

## Suggested fix

- Bound the walk explicitly: pass `--confcutdir <suite>` in `run_session`'s argv. The suite's parent
  is then an ancestor of `confcutdir`, and the walk stops at the suite itself. The repo plugin is
  loaded with `-p` from `pytest.ini`'s `addopts`, so `confcutdir` does not affect it. Its effect on
  conftest loading needs checking, but the repo's `conftest.py` files are not ancestors of the
  suite anyway.
- Or create the suite under a quiet root whose common ancestor with the repo excludes Temp. A
  directory inside the repo would conflict with the test's own "no new project entries" assertion,
  unless it sits inside an existing non-durable folder.

The vacuity guard needs no change: it already turns this into a loud failure instead of a vacuous
pass. Only the walk needs bounding.

**Related.** `KI-TQ-20260928-windows-pytest-collection-flake` is the same family: a rootdir or
collection walk that crosses unrelated, transiently changing directories (`done_proof.py`'s
`_run_pytest_and_parse` docstring describes the shape). BO-2900a-3 fixed the done-proof instance by
anchoring the child's cwd. `KI-TQ-20260914-tempdir-cleanup-race-fails-a-green-test-run` is another
failure that comes from Temp rather than from the change under test.

**Pattern:** a test that isolates its own files in Temp, and so shares a directory listing with
every other process on the machine.
