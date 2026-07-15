---
title: "finalize-feature: targeted per-test rerun when baseline capture fails, not blanket regression"
status: todo
components:
  - finalize
  - testing_quality
created: 2026-07-15
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - finalize-feature
  - false-positive
  - test-triage
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/agents/test-failure-triage.md
---

# finalize-feature: targeted per-test rerun when baseline capture fails, not blanket regression

## Actor / Goal
In order to stop `/finalize-feature` from halting good branches on false
`test_regression` results, we need the regression triage to fall back to a
**targeted per-test rerun against main HEAD** when the Step 0 baseline is
unavailable, so that pre-existing/deploy-dependent failures are not blanket-
classified as regressions.

## Context
Observed 2026-07-15 finalizing `TICKET-20260715-BuildPipelineAuditFindings`
(a docs + one-test change). `/finalize-feature` (`wf_23c45a0a-f4d`) halted at
Step 3 with `reason: test_regression`, flagging 3 tests
(`tests/commit_guardian/test_commit_guardian_imports.py::test_module_set_is_non_empty`,
`tests/test_build_phases.py::...includes_plan_feature`,
`tests/test_build_phases.py::...deployed_in_consumer_config`).

Manual verification showed all 3 were false positives:
- 1 **passed** on clean `main` (environmental — `build.py` had not finished).
- 2 **failed identically** on clean `main` (pre-existing `plan-feature.js`
  deploy staleness, already targeted by `EPIC-RedTestClusterRepair`).
- None are touched by the branch.

### Root cause
Step 0 captures the baseline by running `build.py` **and the full test suite**
in a temp worktree on `origin/main`
([finalize-feature.js:415-462](../../templates/workflows-js/finalize-feature.js#L415)).
On this repo the full suite is ~3120 tests and `build.py` can time out, so the
baseline run does not complete and returns `run_failed`/`worktree_failed`. The
workflow then sets `baselineFailures = null`
([finalize-feature.js:490-495](../../templates/workflows-js/finalize-feature.js#L490)),
and the Step 3 triage classifies **every** post-merge failure as a regression
because `regressions = post_merge_failures − baseline_failures` collapses to
"all failures" when the baseline is null
([finalize-feature.js:663-664](../../templates/workflows-js/finalize-feature.js#L663);
[test-failure-triage.md](../../templates/agents/test-failure-triage.md)).

The deploy-dependent failures that trip Step 3 would ALSO have failed in Step 0's
baseline — so if the baseline had completed, they would be subtracted correctly.
The blanket "all regressions" fallback is the defect: it is safe in intent but
produces recurring false halts whenever the baseline can't be captured (large
suite, slow `build.py`, timeout).

This is the documented `finalize_false_test_regression` pattern; the workflow's
own Step 3 note already acknowledges it but still halts.

## Acceptance Criteria
- [ ] AC-1: When the Step 0 baseline is unavailable (`baseline_failures == null`),
      the Step 3 triage does NOT blanket-classify all post-merge failures as
      regressions. Instead, for each post-merge failing test it performs a
      **targeted rerun of just that test (or its file) against main HEAD** and
      classifies it `pre_existing` if it fails there too, `regression` only if it
      passes on main HEAD but fails post-merge.
- [ ] AC-2: The targeted fallback runs only the specific failing test IDs (not the
      full suite), so it completes within a bounded time even when the full-suite
      baseline times out.
- [ ] AC-3: The targeted rerun deploys shims (`build.py`) in the main-HEAD checkout
      before running the tests, matching the Step 3 build state, so deploy-dependent
      tests are evaluated under identical conditions (no `build.py`-incomplete skew).
- [ ] AC-4: If even the targeted rerun cannot run (e.g. main-HEAD checkout fails),
      the workflow falls back to the current conservative behavior AND the halt
      message clearly states the baseline could not be established and lists the
      `modified_by_branch` flag per test so a human can adjudicate quickly.
- [ ] AC-5: A test reproduces the false-positive: given a null baseline and a
      post-merge failure whose test is not modified by the branch and fails on main
      HEAD, triage returns `pre_existing`/`blocks_finalization: false` (not
      `regression`).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] In the Step 3 triage path, add a null-baseline fallback that reruns only the
      post-merge failing test IDs against a main-HEAD checkout (after `build.py`).
- [ ] Classify each as `pre_existing` (fails on main too) vs `regression` (passes on
      main, fails post-merge); only real regressions set `blocks_finalization: true`.
- [ ] Update `test-failure-triage.md` to document the targeted-rerun fallback and the
      `modified_by_branch` signal usage.
- [ ] Improve the halt/summary message for the "baseline unavailable" case.
- [ ] Add a unit/scenario test covering the null-baseline + pre-existing-failure case.

## Out of Scope
- Fixing the underlying pre-existing `plan-feature.js` deploy staleness (owned by
  `EPIC-RedTestClusterRepair`).
- Making the full-suite baseline itself faster / not time out (separate concern;
  the targeted fallback makes baseline-timeout non-fatal regardless).

## Risk & Safety
- Touches money? No.
- Touches data? No — logic change in the finalize workflow + triage agent prompt.
- Reversibility? Fully reversible; the current conservative behavior remains as the
  final fallback (AC-4).
