---
title: "KI-ACS-20261013-done-proof-cannot-see-manual-tests — done-proof's own pytest run inherits pytest.ini's `-m \"not manual ...\"` selection, so an AC proven by `_MANUAL` tests is refused as \"linked test not run\" (or \"run did not finish\" when every linked test is `_MANUAL`) and can never close"
description: "medium — since TQ-600a-13 (3f67f8769, 2026-10-08) pytest_manual_deselect marks every *_MANUAL test `manual`, and pytest.ini's addopts deselect that marker. done_proof._run_pytest_and_parse spawns plain `python -m pytest` with that ini, so `_MANUAL` linked tests never produce a result line. BO-4300a-1 (9 `_MANUAL` deployed-maker tests) could only be closed by running mark_ac_done.py with PYTEST_ADDOPTS='-m \"not timing_ratio\"' and a raised timeout. On main 55 `_MANUAL` tests carry covers tags for 13 ACs, 6 of them todo. test-runner's documented `manual` action selects nothing for the same reason."
type: reference
category: reference
status: active
created: '2026-10-13'
last_updated: '2026-10-13'
components:
  - ac_store
  - testing_quality
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
  - docs/known-issues/ac-store/open-low-ki-acs-20260928-done-proof-rootdir-walk-unbounded.md
---

# KI-ACS-20261013-done-proof-cannot-see-manual-tests — the proof gate deselects the tests it is asked to read

> Filed 2026-10-13 from the BO-4300 drive (ticket 01, BO-4300a-1). Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. It fails closed: no AC is marked done on a test that did not run. But an AC
  whose proof is a `_MANUAL` test cannot close through the gate at all, and the only way through is an
  environment override that also changes what else the run selects.
- **Status:** open, no AC. Mechanism verified on `origin/main` `964f23a60`.
- **Occurrences:** 1 (BO-4300a-1, closed by the ac-fulfillment-gate with the override; session account).
- **First seen:** 2026-10-13 · **Last seen:** 2026-10-13
- **Where:**
  - `scripts/ac_store/done_proof.py:1281-1393`, `_run_pytest_and_parse`: runs
    `python -m pytest -v --tb=no --no-header <files>` (`:1362`) with `os.environ` plus
    `AC_ENFORCE_STRICT=1` (`:1364`), from the nearest pytest rootdir (`_resolve_pytest_run_cwd`). The
    leaf path and the composite path both reach it through `_run_python_test_phase`
    (`scripts/ac_store/_done_proof_phase_helpers.py:620-657`).
  - `pytest.ini:18`: `addopts = ... -m "not manual and not timing_ratio" ... -p scripts.suite_performance.pytest_manual_deselect ...`.
  - `scripts/suite_performance/pytest_manual_deselect.py:24-38`: adds the `manual` marker to every
    collected test whose name ends in `_MANUAL`. Landed in `3f67f8769` (PR #1050, 2026-10-08).

## Mechanism (verified)

The gate starts a pytest process like any other, so the repo's `pytest.ini` applies. Since TQ-600a-13,
that ini deselects every `_MANUAL` test. Probed on main with a scratch file:

| Linked file holds | pytest exit | done-proof reads it as |
|---|---|---|
| one `_MANUAL` test and one ordinary test | 0, "1 passed, 1 deselected" | the `_MANUAL` nodeid has no result line, so `_describe_non_passing` reports **"linked test not run"** (`done_proof.py:1629`) |
| only `_MANUAL` tests | **5**, "1 deselected" | returncode not in (0, 1), so **"pytest run unfinished: N file(s), returncode 5"** (`:1388-1391`), then "could not verify <AC>: the run did not finish" |
| the same, with `PYTEST_ADDOPTS='-m "not timing_ratio"'` | 0, "2 passed" | eligible |

The override works because the child inherits `os.environ`, and pytest applies `PYTEST_ADDOPTS` after
the ini's `addopts`, so the second `-m` wins.

**BO-4300a-1** (epic branch, `cc3c85edc`): `covered_by` names three child ACs plus
`unit_tests/build_orchestration/test_bo_4300a_1.py` (one ordinary test) and
`test_bo_4300a_1_deployed.py` (nine `..._MANUAL` tests, each `# covers: BO-4300a-1`). That is the first
row: the nine were refused as "not run". The ac-fulfillment-gate ran `mark_ac_done.py` with
`PYTEST_ADDOPTS='-m "not timing_ratio"'` and a raised `LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS`. The
tests ran and passed (session account).

## Blast radius on main (measured)

55 test functions on `origin/main` end in `_MANUAL`. They carry `# covers:` tags for 13 ACs. Six of
those ACs are still `todo`: BP-1500d-1-i, TQ-600a-1, TQ-600a-1-i, TQ-600a-9, TQ-600a-9-i and TQ-600a-9-ii.
Inferred: any of them whose proof includes a `_MANUAL` test meets the same refusal when it is closed.

**The same deselection breaks test-runner's `manual` action.** `templates/agents/test-runner.md:115`
documents `python -m pytest unit_tests/ -k "_MANUAL"`. With the ini's `-m "not manual ..."` still
applied, `-k _MANUAL` selects nothing: exit 5, "2 deselected" on the probe. The documented way to
run the manual tests runs none of them.

## Detection

A done-proof refusal of "linked test not run: <...>_MANUAL" for a test that exists and passes when run
on its own with `-m manual`. Or "pytest run unfinished ... returncode 5" for an AC whose linked tests
are all `_MANUAL`.

## Workaround

Run the close with the selection overridden and enough time for the slow tests:
`PYTEST_ADDOPTS='-m "not timing_ratio"' LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS=<n> python scripts/ac_store/mark_ac_done.py ...`.
For test-runner's manual action, use `-m manual` in place of `-k "_MANUAL"`.

## Fix direction

- Done-proof should select exactly the linked tests. Pass the linked nodeids, and override the marker
  selection for the run (`-m "not timing_ratio"`, or `-m ""` plus an explicit list), so the repo's
  default lane selection cannot hide a test the AC names. Keep the computed timeout. `_MANUAL` tests are
  slow by definition, so the budget may need a per-test allowance.
- Treat "linked test deselected" as its own outcome, with its own refusal text. It is not "not run",
  and it is not an unfinished run. Read it from pytest's `deselected` count or the
  `-rA`/`--collect-only` listing.
- Change `test-runner.md:115` to `-m manual`, and add a test that the documented manual command selects
  at least one test.

**Related.** `KI-ACS-20260928-done-proof-rootdir-walk-unbounded` (the same subprocess picks up whichever
ini it finds, and that ini decides what runs).

**Pattern:** a proof gate that borrows the default test run's selection, then reads a test the default
run deliberately skips as a test that did not run.
