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
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_traceability:
  l2:
    - FIN-100c-4
    - FIN-100c-5
    - FIN-100c-6
    - FIN-100c-7
    - FIN-100c-8
    - FIN-100c-10
  l3:
    - FIN-100c-9
  ac_path: docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/
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

> These Gherkin ACs are for human readability. The **canonical, test-coverable
> ACs live in the store** under `docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/`
> (FIN-100c-4..9, children of L1 `FIN-100c`). Where the two diverge, the store
> YAML wins. See the AC Traceability table below for the mapping.

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

## Test Requirements

```yaml
tests:
  # --- FIN-100c-4: null baseline → targeted main-HEAD rerun (with build.py parity) ---
  - name: test_null_baseline_with_failures_does_not_blanket_regress
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-4
    asserts: "With baseline_failures=null and a non-empty post-merge failure set, the workflow does not immediately mark every failure regression; it enters the recovery branch instead of the blanket-regression path."
  - name: test_null_baseline_establishes_main_head_checkout
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-4
    asserts: "The recovery branch establishes a detached checkout of origin/main HEAD before re-running the failing tests."
  - name: test_null_baseline_runs_build_before_rerun
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-4
    asserts: "The recovery branch runs python3 scripts/build.py --target-dir <checkout> against the main-HEAD checkout before executing the tests, matching the Step 0 / Step 3 build/deploy step."
  - name: test_null_baseline_reexecutes_failing_tests_on_main
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-4
    asserts: "The recovery branch re-executes the post-merge failing tests against main HEAD and records each test's pass/fail result on main."
  # --- FIN-100c-5: rerun scoped to only the failing test IDs → bounded runtime ---
  - name: test_rerun_executes_only_failing_test_ids
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-5
    asserts: "The main-HEAD rerun is invoked with exactly the K post-merge failing test node IDs and no other tests."
  - name: test_rerun_does_not_run_full_suite
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-5
    asserts: "The recovery path never invokes the full test suite (no bare pytest / discover) — only the scoped node-ID invocation."
  - name: test_rerun_completes_when_full_suite_baseline_timed_out
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-5
    asserts: "Given the Step 0 full-suite baseline timed out (baseline_failures null), the scoped rerun of K IDs still completes and yields a recovered baseline."
  # --- FIN-100c-6: recovered baseline built from rerun, forwarded as non-null ---
  - name: test_recovered_baseline_contains_only_ids_that_fail_on_main
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-6
    asserts: "The recovered baseline equals the intersection of post_merge_failures and the set of tests that failed on the main-HEAD rerun."
  - name: test_recovered_baseline_supplied_as_baseline_failures
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-6
    asserts: "The triage dispatch receives the recovered baseline as baseline_failures in place of null."
  - name: test_ids_passing_on_main_excluded_from_recovered_baseline
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-6
    asserts: "Test IDs that pass on main HEAD are excluded from the recovered baseline so they remain in the regression set-difference."
  - name: test_recovered_baseline_empty_list_when_none_fail_on_main
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-6
    asserts: "When no failing test fails on main, baseline_failures is forwarded as [] (clean baseline → all regressions), never as null."
  # --- FIN-100c-7: classify pre_existing (fails on main) vs regression (passes on main) ---
  - name: test_recovered_baseline_failures_on_main_classified_pre_existing
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-7
    asserts: "Given a recovered baseline, every post-merge failure that also fails on main HEAD is classified pre_existing (2026-07-15 case: all 3 deploy-dependent tests)."
  - name: test_recovered_baseline_pass_on_main_classified_regression
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-7
    asserts: "A post-merge failure whose test passes on main HEAD (absent from the recovered baseline) is classified regression."
  - name: test_triage_report_includes_category_per_test
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-7
    asserts: "Each post-merge failure appears in the triage_report with its category field set."
  # --- FIN-100c-8: only real regressions set blocks_finalization=true ---
  - name: test_all_pre_existing_does_not_block_finalization
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-8
    asserts: "When every post-merge failure is classified pre_existing against the recovered baseline, blocks_finalization is false and finalization proceeds."
  - name: test_any_regression_blocks_finalization
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-8
    asserts: "When at least one post-merge failure is classified regression, blocks_finalization is true (finalize HALTs)."
  - name: test_2026_07_15_three_deploy_dependent_all_pre_existing_no_false_halt
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-8
    asserts: "The 2026-07-15 case (3 deploy-dependent tests, all pre-existing on main) yields blocks_finalization=false — no false test_regression halt."
  # --- FIN-100c-9 (L3): rerun-unavailable → conservative fallback + modified_by_branch ---
  - name: test_rerun_checkout_failure_falls_back_to_conservative_halt
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-9
    asserts: "When the main-HEAD checkout fails, the workflow falls back to the conservative null-baseline path (all failures regression, blocks_finalization=true)."
  - name: test_rerun_build_failure_falls_back_to_conservative_halt
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-9
    asserts: "When the build/deploy step against the main-HEAD checkout errors, the workflow falls back to the conservative halt."
  - name: test_conservative_fallback_sets_blocks_finalization_true
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-9
    asserts: "The fallback halt sets blocks_finalization=true and treats every post-merge failure as regression."
  - name: test_halt_message_lists_modified_by_branch_per_test
    file: unit_tests/workflows/test_finalize_baseline_recovery.py
    covers:
      - FIN-100c-9
    asserts: "The conservative halt message lists each failing test together with its modified_by_branch flag."
  # --- FIN-100c-10: how-to guide describes the null-baseline targeted rerun ---
  - name: test_howto_step0_drops_blanket_regression_as_current
    file: unit_tests/docs/test_finalize_howto.py
    covers:
      - FIN-100c-10
    asserts: "The Step 0 narrative no longer presents an unavailable baseline as causing triage to classify all post-merge failures conservatively as regressions as the current behavior."
  - name: test_howto_step3_describes_targeted_rerun_recovered_baseline
    file: unit_tests/docs/test_finalize_howto.py
    covers:
      - FIN-100c-10
    asserts: "The Step 3 row and the test_regression halt section describe the targeted per-test rerun against main HEAD that recovers a baseline and distinguishes pre_existing from regression when the Step 0 baseline is null."
  - name: test_howto_conservative_halt_narrowed_to_fallback_with_modified_by_branch
    file: unit_tests/docs/test_finalize_howto.py
    covers:
      - FIN-100c-10
    asserts: "The guide describes the conservative all-regressions halt as the narrowed rerun-unavailable fallback and states it surfaces each failing test's modified_by_branch flag for human adjudication."
  - name: test_howto_has_no_stale_null_baseline_all_regressions_as_current
    file: unit_tests/docs/test_finalize_howto.py
    covers:
      - FIN-100c-10
    asserts: "No remaining passage presents the old 'null baseline -> all post-merge failures are regressions -> halt' behavior as the current Step 3 behavior (including the misclassification-troubleshooting text)."
```

## AC Traceability

Canonical ACs in the store (L1 parent `FIN-100c` — "Test failures are triaged into
regression, pre-existing, or flaky"):

| Store AC | Level | Behavior | Agent | Body AC |
|----------|-------|----------|-------|---------|
| FIN-100c-4 | L2 | Null baseline → targeted main-HEAD rerun (with `build.py` parity) instead of blanket regression | python-coder | AC-1, AC-3 |
| FIN-100c-5 | L2 | Rerun scoped to only the failing test IDs → bounded runtime | python-coder | AC-2 |
| FIN-100c-6 | L2 | Build a recovered baseline (IDs that also fail on main), forward as non-null (`[]` when clean) | python-coder | AC-1 |
| FIN-100c-7 | L2 | Classify: fails-on-main → `pre_existing`; passes-on-main-but-fails-post-merge → `regression` | test-failure-triage | AC-1 |
| FIN-100c-8 | L2 | Only real regressions set `blocks_finalization=true` | test-failure-triage | AC-5 |
| FIN-100c-9 | L3 | Rerun-unavailable → conservative fallback + surface each test's `modified_by_branch` | python-coder | AC-4 |

Supersession: `FIN-100c-3` (the prior "null baseline → all regressions, halt" path) is
`superseded_by: FIN-100c-9`.

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
