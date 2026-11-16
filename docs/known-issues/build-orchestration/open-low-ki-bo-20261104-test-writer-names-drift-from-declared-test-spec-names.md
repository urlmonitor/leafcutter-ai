---
title: "KI-BO-20261104-test-writer-names-drift-from-declared-test-spec-names — test-writer wrote tests under other names than the AC's test_spec declares, the red-baseline gate let it pass because one declared name did match, and the wrong-version runs then reported the declared tests 'not found'"
description: "low — on 2026-11-04 (TQ-200d-1-iv) three of the AC's declared tests were written under other names (e.g. test_weak_or_self_comparing_counts_fail_in_unittest_form for the declared test_weak_or_self_comparing_counts_fail). verify_red_baseline only fails closed when NONE of the declared names is matched (_any_declared_name_matched, _fl_red_baseline_support.py:501-524), so it passed. The wrong-version runner then marked each of the three 'invalid: declared test not found' (wrong_version_runner.py:292). Context: on TQ-200d-1-v and -1-iv the end-to-end tests also left 6 and 4 named wrong versions surviving until tests were strengthened by hand."
type: reference
category: reference
status: active
created: '2026-11-04'
last_updated: '2026-11-04'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261023-test-breaker-no-op-alterations.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261104-wrong-version-finish-fails-in-the-command-runner.md
---

# KI-BO-20261104-test-writer-names-drift-from-declared-test-spec-names — test names drift from the declared test_spec names, and the red-baseline gate does not notice

> Filed 2026-11-04. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. Nothing wrong is accepted: the wrong-version step does catch the mismatch and
  reports it as invalid. But it catches it late, after the coder has finished, and the red-baseline
  gate, which runs first and reads the same declared names, says nothing. Fixing it means renaming
  tests by hand.
- **Status:** open. No AC.
- **Occurrences:** 1 (`TQ-200d-1-iv`, 2026-11-04, seen in its wrong-version runs).
- **First seen:** 2026-11-04 · **Last seen:** 2026-11-04
- **Where** (at `origin/main` `72ddec43f`):
  - `scripts/build_orchestration/_fl_red_baseline_support.py:466` — `_load_declared_test_names()`
    collects the names of `test_spec` entries that declare `must_catch` or
    `angle: discrimination`.
  - `:501-524` — `_any_declared_name_matched()` returns
    `any(tag["function"] in declared_names ...)` (`:524`). It is checked over all declared names
    together, so a batch where one declared name is matched passes even if others are missing.
    The docstring at `:38-51` says this is on purpose ("the gate stays permissive when at least
    one OTHER declared name in the same batch IS matched").
  - `:550` — `_declared_names_preflight()` fails closed with
    `declared_test_missing_no_matching_test` only when no declared name matched.
  - `scripts/build_orchestration/_wvr_scope.py:175` — the wrong-version runner computes
    `scope.missing = sorted(declared - found)` per name.
  - `scripts/build_orchestration/wrong_version_runner.py:292` — each missing name becomes an
    `invalid` row: "declared test not found: <name> is declared in test_spec but no covers-tagged
    test of that name exists".

## Symptom

On `TQ-200d-1-iv`, test-writer wrote three of the declared tests under longer names. One example:
the AC declares `test_weak_or_self_comparing_counts_fail`, and the test was written as
`test_weak_or_self_comparing_counts_fail_in_unittest_form`. Other declared names in the same batch
were written as declared, so `verify_red_baseline` passed. The wrong-version runs then reported the
three declared tests as `declared test not found` (invalid), and the tests had to be renamed by
hand.

## Mechanism

1. Two readers check the same declared names with different strictness. The red-baseline gate
   asks "was at least one declared name attempted?". The wrong-version runner asks, per name,
   "does this declared test exist?".
2. test-writer treats the declared name as a description, not an exact identifier. It added a
   suffix that made the name more specific.
3. Nothing between the two checks compares the full sets, so the drift is first seen at the
   wrong-version step, after the coder phase.

## Related finding: weak isolation in end-to-end tests (context, not a separate entry)

On `TQ-200d-1-v` and `TQ-200d-1-iv` the end-to-end tests could not single out the named wrong
versions: 6 and 4 of them survived (every test still passed under the wrong version) until the
tests were strengthened by hand. That is a test-strength problem, not a name problem. It is
recorded here because it showed up in the same runs and the same step, and it also only appears at
the wrong-version step. If it recurs on other ACs, file it on its own. It is not
`KI-BO-20261023-test-breaker-no-op-alterations`: those alterations changed nothing the tests read,
and here the wrong versions were real.

## Detection

A wrong-version verdict with one or more `invalid` rows whose reason starts `declared test not
found:` on a run where `verify_red_baseline` passed. Compare the AC's `test_spec[].name` values
with the `def test_*` names in the files tagged `# covers:<id>`.

## Workaround

Rename the tests to the declared names (or, if the new name is better, change the AC's `test_spec`
name through the normal AC edit path) and rerun the wrong-version step.

## Fix direction

1. In `_declared_names_preflight()`, report every declared name with no matching newly-added test
   (not only the case where none match). Either fail the gate, or return the list so the lane can
   send test-writer back once to rename.
2. Tell test-writer in its prompt that a declared `test_spec` name is an exact function name.
3. If the permissive shape is kept on purpose (the docstring's "today's accepted control shape"),
   say so in the gate's verdict, so a partial match is visible before the coder runs.

**Pattern:** two checks that read the same declared list with different strictness, so the
weaker, earlier one passes what the stricter, later one refuses.
