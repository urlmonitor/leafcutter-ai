---
title: "KI-BO-20261012-subtest-with-message-and-params-reads-passed — the shared pytest outcome reader still drops a failing unittest subTest that has both a message and keyword parameters, so the green gate can pass a test whose sub-cases failed"
description: "high — TQ-500g-4 (2026-10-07) taught pytest_outcome_reader to read SUBFAILED[msg] and SUBFAILED(params) lines, which fixes the subTest misreading seen while building BO-2400f-5-iii on 2026-09-30. A sub-case opened with both, self.subTest('msg', i=1), prints 'SUBFAILED[msg] (i=1) <nodeid>', which _SUBFAILED_RE does not match, so the test reads PASSED. The exit-1 cross-check catches it only when no other test in the run failed. Reproduced on origin/main e93eda09a with pytest 9.1.1."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - build_orchestration
  - ac_store
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/testing-quality/resolved/resolved-low-ki-tq-20260928-subtest-failures-read-as-passed.md
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g.yaml
---

# KI-BO-20261012-subtest-with-message-and-params-reads-passed — a failing subTest with a message and parameters reads PASSED

> Filed 2026-10-12 from the BO-2400f-5-iii build. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. At the green gate the error is in the unsafe direction: a covering test whose
  sub-cases failed reads `PASSED`, so `verify_green_and_coverage` and done-proof can accept it. Two
  conditions must hold together. The test uses `self.subTest(<msg>, <key>=<value>)`, and another
  test in the same pytest run fails. At the red-baseline gate the same misreading causes a false
  refusal, never a false pass.
- **Status:** open, no AC. The form originally reported is fixed on main (see History). The residual
  form below was found by reproduction while filing this entry.
- **Occurrences:** 1 observation of the original form (2026-09-30, a week before the fix), plus the
  reproduction of the residual form on 2026-10-12. No live occurrence of the residual form is known.
- **First seen:** 2026-09-30 · **Last seen:** 2026-10-12
- **Where:** `scripts/ac_store/pytest_outcome_reader.py` on origin/main `e93eda09a`: `_SUBFAILED_RE`
  (:46-49) and `parse_pytest_outcomes` (:78-105). `scripts/ac_store/done_proof.py` imports it as
  `_parse_pytest_verbose_output` (:181-185) and calls it from `_run_pytest_and_parse` (:1281, :1392).
  The fast lane reaches it on both gates:
  - `verify_red_baseline` (`scripts/build_orchestration/fast_lane.py:264`, runner chosen at :370-373)
    goes through `_run_pytest_and_parse` or `done_proof_kind_support._run_pytest_and_parse_with_kind`
    (:353).
  - `verify_green_and_coverage` (`scripts/build_orchestration/_fl_coverage.py:23`) calls
    `verify_done_eligible` per AC (:79), which runs `_run_pytest_and_parse`
    (`scripts/ac_store/_done_proof_phase_helpers.py:652`).

## History: the form that was reported

On 2026-09-30, while building BO-2400f-5-iii, three tests written with `self.subTest()` were each
classified `green_at_baseline` although every sub-case failed. They were rewritten to collect
problems in a list and assert once. The subTest versions were never committed, so their exact form
is not known.

That was `KI-TQ-20260928-subtest-failures-read-as-passed`. pytest 9 prints the parent's
`<nodeid> PASSED` line and reports each failed sub-case on a separate `SUBFAILED` line, which the
parser ignored. TQ-500g-4 fixed it on 2026-10-07 (`7ef8f23cb`). The fix put the one shared parse
in `pytest_outcome_reader.py`. Any node id named on a `SUBFAILED` line is now forced to `FAILED`,
and an exit-1 run with no parsed failure is now inconclusive.

On origin/main `e93eda09a` both forms the fix targets read correctly. This was verified on
2026-10-12 with pytest 9.1.1, using the gate's own flags `-v --tb=no --no-header`:

```text
SUBFAILED[case alpha] test_sub_all_fail.py::T::test_every_subtest_fails - Ass...
SUBFAILED(i=0) test_sub_all_fail.py::T::test_params_form - AssertionError: 0 ...
```

Both tests read `FAILED`, with their sub-case labels attached.

## Symptom: the residual form

A sub-case opened with both a message and keyword parameters, `self.subTest("labelled", i=i)`,
is reported as:

```text
test_sub_masked.py::T::test_msg_and_params PASSED                        [ 50%]
test_sub_masked.py::T::test_plain_failure FAILED                         [100%]
SUBFAILED[labelled] (i=0) test_sub_masked.py::T::test_msg_and_params - Assert...
SUBFAILED[labelled] (i=1) test_sub_masked.py::T::test_msg_and_params - Assert...
FAILED test_sub_masked.py::T::test_plain_failure - AssertionError: 1 != 2
```

`parse_pytest_outcomes(output, 1)` returns `test_msg_and_params: PASSED` and
`test_plain_failure: FAILED`, with an empty `subfailed` map.

## Mechanism

pytest builds the label in `_pytest/subtests.py` `_sub_test_description` (:88-97). It emits
`[msg]`, `(k=v)`, or both joined by a space. `_SUBFAILED_RE` allows one optional group, `[msg]` or
`(params)`, then whitespace, then a node id containing `::`. With both groups present, the text
after `[labelled]` is ` (i=0) <nodeid>`. The node-id group cannot start at `(i=0)`, which holds no
`::`. So the line does not match, the sub-case failure is dropped, and the parent's `PASSED` line
stands.

The exit-1 cross-check (:103-104) catches this only when no other test in the run reads `FAILED`
or `ERROR`. In that case the whole run becomes the incomplete-run sentinel, which callers treat as
inconclusive. When another test in the run did fail, the cross-check is satisfied and the masked
test reads `PASSED`.

## Effect on each gate

- **`verify_green_and_coverage` (unsafe).** It calls `verify_done_eligible` once per AC, and each
  call runs every linked test *file* whole. Suppose the masked test covers one AC and a different
  test in the same file fails. The masked test reads `PASSED` and its AC is judged eligible. The
  batch's `green` stays true when that other failing test covers no AC in the batch. The done-proof
  path (`check-done-proof`, mark-done) has the same exposure.
- **`verify_red_baseline` (false refusal only).** At baseline other tests are expected to fail, so
  the cross-check rarely fires, and a newly added masked test is classified `green_at_baseline`. If
  it is the only new test, the gate refuses with `all_new_tests_green_at_baseline`. If another new
  test is red, the gate passes, which is the right result. The misreading only turns red into green,
  so a test that was never red cannot pass this gate through it.

## Detection

Grep the gate's pytest output for a `SUBFAILED[` line that has ` (` after the closing bracket. Or
compare the summary's `N failed` with the number of tests the gate reports as failing. A masked
sub-case makes the summary count larger.

## Workaround

Don't use `subTest()` in tests these gates must classify. Accumulate failures in a list and assert
once, as was done for BO-2400f-5-iii, or use `pytest.mark.parametrize`, which gives each case its
own node id. If `subTest()` stays, pass a message or keyword parameters, never both.

## Suggested fix

1. Accept both label groups in sequence, for example
   `^SUBFAILED(?:\[(?P<msg>.*?)\])?\s*(?:\((?P<params>.*?)\))?\s+(?P<nodeid>\S+::.*?)(?=\s+-\s|\s*$)`,
   and join them into the sub-case label.
2. Count every line that starts with `SUBFAILED` toward its parent node id, even when the label
   cannot be parsed: take the first `::`-bearing token as the node id. An unparseable label must
   never drop a failure. `SUBPASSED` lines can stay informational, since a passing sub-case never
   changes the parent's outcome.
3. pytest 9.1.1 has no option that folds sub-case results into the parent. Its only subtest
   setting is the `verbosity_subtests` ini (`_pytest/subtests.py:46-54`). The fix therefore has to
   live in the parser.
4. Add regression tests to `unit_tests/ac_store/test_tq_500g_4_parser.py`. One should cover the
   `[msg] (params)` form. Another should put a second failing test in the same output, so the exit-1
   cross-check cannot hide the result. The current tests cover `[msg]` and `(params)` only.

**Related.** The resolved `KI-TQ-20260928-subtest-failures-read-as-passed` is the original defect.
Its Occurrences line does not yet include the 2026-09-30 BO-2400f-5-iii observation.

**Pattern:** a parser fixed for the formats it had seen, while the producer composes those formats
into a third.
