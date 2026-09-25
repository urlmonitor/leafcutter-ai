---
title: "KI-ACS-20260925-done-proof-parametrised-first-match — the done-proof oracle judges a parametrised test by its first case only, so an AC with one failing case is proven done"
description: "blocker — _find_nodeid_for_test returns the first nodeid whose function name matches; with test_b[0] PASS and test_b[1] FAIL the AC is judged done-eligible. The required CI done-proof gate issues a false green."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/ac-store/open-high-ki-acs-008.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20260826-1900.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-ACS-20260925-done-proof-parametrised-first-match — the done-proof oracle judges a parametrised test by its first case only, so an AC with one failing case is proven done

- **Severity:** blocker. The CI done-proof gate is a required check whose whole purpose is to refuse phantom-done; this lets a partly failing test prove an AC.
- **Status:** **RESOLVED** (9fa4c65d, PR #900 merged as c038123e, AC ACS-200f-2; verified 2026-09-25 by a red → green → fix-reverted-red → restored-green run of `unit_tests/ac_store/test_find_nodeid_for_test.py` under `AC_ENFORCE_STRICT=1`). Originally: open — reproduced 2026-09-25 by a scratch fixture (sub-agent probe); code re-read by the main session.
- **Where:** `scripts/ac_store/done_proof.py:1485-1494` (`_find_nodeid_for_test`); reused by `scripts/build_orchestration/_fl_red_baseline_support.py:234-252`.

## Symptom

A test file tagged `# covers: XX-100` with `test_b` parametrised over two cases: `test_b[0]` PASSED, `test_b[1]`
FAILED. The oracle reports the AC done-eligible.

## Mechanism

```python
for nodeid in pytest_results:
    if _nodeid_function_name(nodeid) == func_name and file_basename in nodeid:
        return nodeid              # first matching case only
```

The caller then reads the outcome of that single nodeid.

## Relation to existing KIs

KI-ACS-008 recorded the parametrised-id problem and warned (L72-78) against a first-match fix; KI-BO-20260826-1900
(L81-87) required "all matching node ids must pass". The fix that landed took the first match — so the KI is
nominally addressed and the defect is still live.

## Detection

For any AC whose covering test is parametrised, compare the oracle's verdict with `pytest -q <file>::<test>`; a
failing case with an eligible verdict is this bug.

## Resolution (2026-09-25)

`_find_nodeid_for_test` now builds on a new `_find_nodeids_for_test`, which returns every
nodeid of the function, with same-file matches still preferred as a group. It returns a
non-passing case whenever any case is not `PASSED`, and the first match otherwise. The
single-nodeid contract is unchanged, so `_classify_outcomes` and the fast lane's
`_fl_red_baseline_support._resolve_tag_outcome` both get the all-cases rule without edits.

- **Tests:** `unit_tests/ac_store/test_find_nodeid_for_test.py`, `TestClassifyOutcomesParametrisedAllCases`, covering:
  - a failing case reported after a passing one;
  - a failing case reported before a passing one;
  - all cases passing;
  - same-file precedence.
- **Mutation proof:** with the fix reverted the ordering test fails; with it restored (byte-identical) all 11 tests pass.

Not covered by this fix, and still open elsewhere: the async and decorator tag
misattribution (KI-ACS-20260925-done-proof-credits-tags-to-the-wrong-test), and the
other `# covers:` readers that the 2026-09-25 duplication analysis lists under cluster C1.

## Fix direction

Collect **all** nodeids for the function (every parametrised case) and require every one to pass; an absent or
incomplete case is `incomplete`, not pass. Belongs in the single `ac_proof.run_tests` proposed as cluster 1 of the
2026-09-25 duplication analysis, shared by pre-commit, CI, `mark_ac_done`, the fast lane and the pytest plugin.
