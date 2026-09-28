---
title: "KI-TQ-20260928-subtest-failures-read-as-passed — the pytest outcome parser the red-baseline and done-proof gates share reads a test whose only failures are in unittest subTest blocks as PASSED, so a red test counts as green at baseline"
description: "medium — pytest 9 prints '<nodeid> PASSED' for a unittest test whose failures are all inside self.subTest(), and reports the failures on separate SUBFAILED lines. _PYTEST_RESULT_RE matches the PASSED line and does not know SUBFAILED, so the test is classified green. Reproduced 2026-09-28 against done_proof._parse_pytest_verbose_output with pytest 9.1.1. Seen live on test_db_check_output_never_contains_credentials."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - testing_quality
  - build_orchestration
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g.yaml
  - docs/analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md
---

# KI-TQ-20260928-subtest-failures-read-as-passed — the pytest outcome parser the red-baseline and done-proof gates share reads a test whose only failures are in unittest subTest blocks as PASSED, so a red test counts as green at baseline

- **Severity:** medium. The error goes in the safe direction at red-baseline (a truly red test is reported as `green_at_baseline`, so the gate refuses when it should accept). At done-proof it goes the other way: a test whose subtests fail is read as PASSED and can support a done verdict. Both depend on the test using `self.subTest()`.
- **Status:** open. No AC of its own. It is one instance of the gap `TQ-500g` (L1, `readiness: approved`, `work_status: todo`) exists to close: nothing checks that the runs the gates read actually show what the gate concludes. `TQ-500g` is Phase B and is not decomposed yet, so this parser fix needs its own leaf when that tree is planned, or a separate ticket.
- **Occurrences:** 1 live (fast-lane red baseline for INF-1100d-3-i, `unit_tests/portability/test_inf_1100d_3_i_no_leak.py:156` `test_db_check_output_never_contains_credentials`, whose cases run inside `self.subTest(address=...)` at `:169`; session observation) plus the reproduction below.
- **First seen:** 2026-09-27 · **Last seen:** 2026-09-28
- **Where:** `scripts/ac_store/done_proof.py:245-248` (`_PYTEST_RESULT_RE`) and `:1247` (`_parse_pytest_verbose_output`), used by `_run_pytest_and_parse` (`:1260`) and through it by `fast_lane.verify_red_baseline` (`scripts/build_orchestration/fast_lane.py:366-368`) · outcome buckets at `scripts/build_orchestration/_fl_red_baseline_support.py:98-99`

## Reproduction (2026-09-28, Windows 11, pytest 9.1.1)

```python
class T(unittest.TestCase):
    def test_x(self):
        for i in range(2):
            with self.subTest(i=i):
                self.assertEqual(i, 0)
```

`python -m pytest -v --tb=no --no-header test_sub.py` (the gate's own flags) prints:

```text
test_sub.py::T::test_x PASSED
SUBFAILED(i=1) test_sub.py::T::test_x - AssertionError: 1 != 0
=============== 1 failed, 1 passed, 1 subtests passed ===============
```

and exits 1. Feeding that stdout to `done_proof._parse_pytest_verbose_output` returns `{'test_sub.py::T::test_x': 'PASSED'}`.

## Mechanism

`_PYTEST_RESULT_RE` is `^(\S+::test_\w+(?:\[.*?\])?)\s+(PASSED|FAILED|XFAIL|XPASS|SKIPPED|ERROR)`. It matches the parent's `PASSED` line. `SUBFAILED(...)` lines start with the outcome, not a node id, and the outcome is not in the list, so they are ignored. The run's exit code (1) is only checked for being in `(0, 1)`, never compared with the parsed outcomes. So "the run failed" and "every parsed test passed" can both be true, and nothing notices the contradiction.

## Detection

Any gate report that lists a test as `PASSED` / `green_at_baseline` while the same run's summary shows `N failed` with N greater than the number of `FAILED` lines. Or grep the run output for `SUBFAILED`.

## Workaround

Do not trust a gate's green reading of any test that uses `self.subTest()`. Run it yourself and read the `SUBFAILED` lines. Or rewrite the cases with `pytest.mark.parametrize`, which gives each case its own node id and outcome line.

## Suggested fix

1. Parse `SUBFAILED(...) <nodeid>` lines and downgrade that node id to `FAILED` (keep `SUBPASSED` as informational).
2. Cross-check: when pytest exits 1 but no parsed outcome is red, report the run as inconclusive instead of reading it as all green.
3. Add a regression test with the five-line reproduction above against `_parse_pytest_verbose_output`.

**Pattern:** a parser built for one line format sees a second format and silently drops it. The dropped lines are the failures.
