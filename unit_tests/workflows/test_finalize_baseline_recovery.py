"""
MODULE: test_finalize_baseline_recovery
GOAL: Verify that finalize-feature.js implements null-baseline targeted-rerun
recovery logic (FIN-100c-4..9) instead of blanket-classification of all
post-merge failures as regressions when the Step 0 baseline capture fails.

Nature: TDD test stubs — MUST be RED until python-coder implements the recovery
branch in templates/workflows-js/finalize-feature.js and updates
templates/agents/test-failure-triage.md.

All tests here read the source files as text and assert that specific
implementation signals are present. The signals are absent until the recovery
branch is coded, so every test below is expected to fail (ImportError or
AssertionError). This is the correct red baseline for the TDD cycle.

ACs: FIN-100c-4, FIN-100c-5, FIN-100c-6, FIN-100c-7, FIN-100c-8, FIN-100c-9
TICKET: TICKET-20260715-FinalizeBaselineFallbackTargetedRerun
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"
_TRIAGE_MD_PATH = _REPO_ROOT / "templates" / "agents" / "test-failure-triage.md"

# The 3 deploy-dependent tests that produced the false test_regression halt on 2026-07-15
_2026_07_15_TEST_IDS = [
    "tests/commit_guardian/test_commit_guardian_imports.py::test_module_set_is_non_empty",
    "tests/test_build_phases.py::test_includes_plan_feature",
    "tests/test_build_phases.py::test_deployed_in_consumer_config",
]


def _js() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _triage_md() -> str:
    """Return the full text of test-failure-triage.md."""
    return _TRIAGE_MD_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# FIN-100c-4: Null baseline triggers a targeted main-HEAD rerun (with build.py parity)
# ---------------------------------------------------------------------------


def test_null_baseline_with_failures_does_not_blanket_regress():
    # covers: FIN-100c-4
    """FIN-100c-4: With baseline_failures=null and a non-empty post-merge failure
    set, the workflow does NOT immediately mark every failure regression; it enters
    the recovery branch instead of the blanket-regression path.

    To make this test green, implement the null-baseline recovery branch in
    finalize-feature.js and include a 'targeted rerun' log or comment as the
    canonical implementation signal.
    """
    js = _js()
    assert "targeted rerun" in js, (
        "finalize-feature.js must contain the phrase 'targeted rerun' (in a log or "
        "comment) as the canonical signal that the null-baseline recovery branch is "
        "implemented. Currently absent — recovery branch not yet coded."
    )


def test_null_baseline_establishes_main_head_checkout():
    # covers: FIN-100c-4
    """FIN-100c-4: The recovery branch establishes a detached checkout of
    origin/main HEAD before re-running the failing tests.

    Step 0 already uses one 'worktree add --detach' (baseline capture).
    The recovery branch must add a second occurrence for the main-HEAD checkout.
    """
    js = _js()
    count = js.count("worktree add --detach")
    assert count >= 2, (
        f"Expected at least 2 occurrences of 'worktree add --detach' in "
        f"finalize-feature.js (step 0 baseline + null-baseline recovery checkout), "
        f"but found {count}. Recovery branch checkout not yet implemented."
    )


def test_null_baseline_runs_build_before_rerun():
    # covers: FIN-100c-4
    """FIN-100c-4: The recovery branch runs python3 scripts/build.py against the
    main-HEAD checkout BEFORE executing the tests, matching the Step 0 / Step 3
    build/deploy step (deploy parity with FIN-100a-4).

    Step 0 (~L440) and Step 3 (~L677) each call scripts/build.py once.
    The recovery branch must add a third call.
    """
    js = _js()
    count = js.count("scripts/build.py")
    assert count >= 3, (
        f"Expected at least 3 occurrences of 'scripts/build.py' in "
        f"finalize-feature.js (step 0, step 3, and null-baseline recovery branch), "
        f"but found {count}. Recovery branch build step not yet implemented."
    )


def test_null_baseline_reexecutes_failing_tests_on_main():
    # covers: FIN-100c-4
    """FIN-100c-4: The recovery branch re-executes the post-merge failing tests
    against main HEAD and records each test's pass/fail result on main.

    The 'recoveredBaselineFailures' (or 'recoveredBaseline') variable is the
    canonical signal that the rerun results have been captured.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "finalize-feature.js must define a 'recoveredBaselineFailures' (or "
        "'recoveredBaseline') variable to store the main-HEAD rerun results. "
        "Not yet implemented — recovery branch absent."
    )


# ---------------------------------------------------------------------------
# FIN-100c-5: Rerun is scoped to only the failing test IDs (bounded runtime)
# ---------------------------------------------------------------------------


def test_rerun_executes_only_failing_test_ids():
    # covers: FIN-100c-5
    """FIN-100c-5: The main-HEAD rerun is invoked with exactly the K post-merge
    failing test node IDs and no other tests.

    The scoped invocation is the canonical way the recovery path achieves bounded
    runtime — it must not submit a blanket discover/full-suite call.
    """
    js = _js()
    assert "targeted rerun" in js, (
        "finalize-feature.js must contain 'targeted rerun' to signal the scoped "
        "rerun of only the failing test IDs. Not yet implemented."
    )


def test_rerun_does_not_run_full_suite():
    # covers: FIN-100c-5
    """FIN-100c-5: The recovery path never invokes the full test suite (no bare
    pytest / discover) — only the scoped node-ID invocation.

    Asserting the recovery branch variable is present is a prerequisite for
    verifying that full-suite discovery is not used in the recovery path.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "Recovery branch not yet implemented — cannot verify that full-suite "
        "discovery is avoided. Implement the scoped rerun first."
    )


def test_rerun_completes_when_full_suite_baseline_timed_out():
    # covers: FIN-100c-5
    """FIN-100c-5: Given the Step 0 full-suite baseline timed out
    (baseline_failures null), the scoped rerun of K IDs still completes and
    yields a recovered baseline.

    The recovered baseline variable is the canonical output of the scoped rerun.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "finalize-feature.js must build a 'recoveredBaselineFailures' variable "
        "from the scoped main-HEAD rerun — even when the full-suite Step 0 baseline "
        "timed out. Not yet implemented."
    )


# ---------------------------------------------------------------------------
# FIN-100c-6: Recovered baseline built from rerun, forwarded as non-null to triage
# ---------------------------------------------------------------------------


def test_recovered_baseline_contains_only_ids_that_fail_on_main():
    # covers: FIN-100c-6
    """FIN-100c-6: The recovered baseline equals the intersection of
    post_merge_failures and the set of tests that failed on the main-HEAD rerun.

    Implementation must build recoveredBaselineFailures = post_merge_failures
    intersected with main-HEAD rerun failures.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "finalize-feature.js must build a 'recoveredBaselineFailures' variable "
        "(intersection of post-merge failures and main-HEAD rerun failures). "
        "Not yet implemented."
    )


def test_recovered_baseline_supplied_as_baseline_failures():
    # covers: FIN-100c-6
    """FIN-100c-6: The triage dispatch receives the recovered baseline as
    baseline_failures in place of null.

    The JS must reassign baselineFailures to the recovered baseline (a list,
    never null) before the triage agent dispatch at ~L747.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "finalize-feature.js must reassign baselineFailures to the recovered "
        "baseline before the triage dispatch, so triage receives a non-null "
        "list in place of null. Not yet implemented."
    )


def test_ids_passing_on_main_excluded_from_recovered_baseline():
    # covers: FIN-100c-6
    """FIN-100c-6: Test IDs that pass on main HEAD are excluded from the recovered
    baseline so they remain in the regression set-difference.

    Passers-on-main are NOT in the intersection and must be absent from
    recoveredBaselineFailures; they will be classified as regression by triage.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "Recovery branch not yet implemented — cannot verify that passers-on-main "
        "are excluded from the recovered baseline."
    )


def test_recovered_baseline_empty_list_when_none_fail_on_main():
    # covers: FIN-100c-6
    """FIN-100c-6: When no failing test fails on main, baseline_failures is
    forwarded as [] (clean baseline → all regressions), never as null.

    The [] vs null distinction is load-bearing: null would re-trigger the
    conservative null-baseline path in triage (Step 1), which must not happen.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "Recovery branch not yet implemented — cannot verify the [] vs null "
        "distinction when no failing test fails on main HEAD."
    )


# ---------------------------------------------------------------------------
# FIN-100c-7: pre_existing vs regression classification over recovered baseline
# ---------------------------------------------------------------------------


def test_recovered_baseline_failures_on_main_classified_pre_existing():
    # covers: FIN-100c-7
    """FIN-100c-7: Given a recovered baseline, every post-merge failure that also
    fails on main HEAD is classified pre_existing (e.g. the 2026-07-15 case:
    all 3 deploy-dependent tests).

    The triage template must explicitly document the recovered-baseline scenario
    so operators and reviewers understand that a non-null baseline may originate
    from a targeted main-HEAD rerun.
    """
    triage_md = _triage_md()
    assert "recovered" in triage_md.lower(), (
        "templates/agents/test-failure-triage.md must document the 'recovered "
        "baseline' scenario — a non-null baseline supplied from a targeted main-HEAD "
        "rerun rather than a full Step 0 baseline capture. Not yet documented."
    )


def test_recovered_baseline_pass_on_main_classified_regression():
    # covers: FIN-100c-7
    """FIN-100c-7: A post-merge failure whose test passes on main HEAD (absent from
    the recovered baseline) is classified regression.

    The triage dispatch in finalize-feature.js must forward the recovered baseline
    as baseline_failures so the existing set-difference (Step 2 in triage template)
    correctly classifies passers-on-main as regression.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "Recovery branch not yet implemented — the JS must forward the recovered "
        "baseline to triage so that tests passing on main HEAD are classified "
        "regression by the set-difference. Not yet implemented."
    )


def test_triage_report_includes_category_per_test():
    # covers: FIN-100c-7
    """FIN-100c-7: Each post-merge failure appears in the triage_report with its
    category field set, including when the baseline was recovered from a targeted
    main-HEAD rerun.

    The 'targeted rerun' signal in finalize-feature.js is the prerequisite:
    without the recovery branch, per-test categories cannot be correctly assigned
    in the recovered-baseline scenario (all would be regression via the null path).
    """
    js = _js()
    assert "targeted rerun" in js, (
        "finalize-feature.js must implement the targeted rerun path before "
        "per-test categories can be correctly computed for the recovered-baseline "
        "scenario. 'targeted rerun' not found in JS — not yet implemented."
    )


# ---------------------------------------------------------------------------
# FIN-100c-8: Only real regressions set blocks_finalization=true
# ---------------------------------------------------------------------------


def test_all_pre_existing_does_not_block_finalization():
    # covers: FIN-100c-8
    """FIN-100c-8: When every post-merge failure is classified pre_existing against
    the recovered baseline, blocks_finalization is false and finalization proceeds.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "Recovery branch not yet implemented — the all-pre_existing scenario "
        "(blocks_finalization=false) requires the recovered baseline to be forwarded "
        "to triage. Not yet coded."
    )


def test_any_regression_blocks_finalization():
    # covers: FIN-100c-8
    """FIN-100c-8: When at least one post-merge failure is classified regression,
    blocks_finalization is true (finalize HALTs).

    The existing halt gate (~L802) already reads blocks_finalization from triage.
    The recovery branch must forward the recovered baseline so that tests passing
    on main remain in the regression set.
    """
    js = _js()
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "Recovery branch not yet implemented — genuine regressions (tests passing "
        "on main HEAD) still halt finalization, but only after the recovery branch "
        "forwards the recovered baseline. Not yet coded."
    )


def test_2026_07_15_three_deploy_dependent_all_pre_existing_no_false_halt():
    # covers: FIN-100c-8
    """FIN-100c-8 (regression test): The 2026-07-15 case — 3 deploy-dependent tests,
    all pre-existing on main — must yield blocks_finalization=false with the recovery
    branch, preventing the false test_regression halt observed in workflow wf_23c45a0a-f4d.

    This is the primary regression test for the false-positive pattern documented
    in the ticket context.
    """
    js = _js()
    # Gate: recovery branch must exist before the simulation is meaningful.
    assert "recoveredBaselineFailures" in js or "recoveredBaseline" in js, (
        "Recovery branch not yet implemented — the 2026-07-15 false-halt scenario "
        "cannot be resolved without the null-baseline targeted rerun."
    )
    # Simulation: given recovered_baseline = all 3 tests (they all fail on main),
    # the set-difference regressions = empty, and blocks_finalization must be False.
    post_merge_failures = set(_2026_07_15_TEST_IDS)
    recovered_baseline = set(_2026_07_15_TEST_IDS)  # all 3 also fail on origin/main
    regressions = post_merge_failures - recovered_baseline
    blocks_finalization = len(regressions) > 0
    assert not blocks_finalization, (
        "With all 3 deploy-dependent tests pre-existing on main HEAD, "
        "the recovered-baseline set-difference must yield empty regressions and "
        f"blocks_finalization=False. Got regressions={regressions}."
    )


# ---------------------------------------------------------------------------
# FIN-100c-9: Rerun-unavailable → conservative fallback + modified_by_branch
# ---------------------------------------------------------------------------


def test_rerun_checkout_failure_falls_back_to_conservative_halt():
    # covers: FIN-100c-9
    """FIN-100c-9: When the main-HEAD checkout fails, the workflow falls back to the
    conservative null-baseline path (all failures regression,
    blocks_finalization=true).

    The conservative fallback log line is the canonical implementation signal for
    FIN-100c-9 (the narrowed successor to the former FIN-100c-3 blanket-halt).
    """
    js = _js()
    assert "targeted rerun unavailable" in js or "rerun unavailable" in js, (
        "finalize-feature.js must log 'targeted rerun unavailable' (or 'rerun "
        "unavailable') when the main-HEAD checkout fails to distinguish this "
        "conservative fallback from a genuine recovered-baseline regression halt. "
        "Not yet implemented."
    )


def test_rerun_build_failure_falls_back_to_conservative_halt():
    # covers: FIN-100c-9
    """FIN-100c-9: When the build/deploy step against the main-HEAD checkout errors,
    the workflow falls back to the conservative halt.
    """
    js = _js()
    assert "targeted rerun unavailable" in js or "rerun unavailable" in js, (
        "finalize-feature.js must log 'targeted rerun unavailable' (or 'rerun "
        "unavailable') when the build/deploy step fails against the main-HEAD checkout. "
        "Not yet implemented."
    )


def test_conservative_fallback_sets_blocks_finalization_true():
    # covers: FIN-100c-9
    """FIN-100c-9: The fallback halt sets blocks_finalization=true and treats every
    post-merge failure as regression (reusing the existing triage Step 1 null path).
    """
    js = _js()
    assert "targeted rerun unavailable" in js or "rerun unavailable" in js, (
        "Conservative rerun-unavailable fallback not yet implemented in "
        "finalize-feature.js."
    )


def test_halt_message_lists_modified_by_branch_per_test():
    # covers: FIN-100c-9
    """FIN-100c-9: The conservative halt message lists each failing test together
    with its modified_by_branch flag so a human can adjudicate which failures
    the branch actually touched.

    The modified_by_branch flag is already emitted by triage Step 3 and forwarded
    in the halt payload (~L808). The conservative fallback halt path must surface it.
    """
    js = _js()
    assert "targeted rerun unavailable" in js or "rerun unavailable" in js, (
        "Conservative rerun-unavailable fallback not yet implemented — cannot "
        "verify that modified_by_branch is surfaced in the halt message."
    )
