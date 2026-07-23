"""
MODULE: test_finalize_baseline_recovery
GOAL: Behavioral tests for the null-baseline targeted-rerun recovery path in
      finalize-feature.js (FIN-100c-4 to FIN-100c-9), using the E2 workflow
      harness to execute real JS code and assert on observed agent call behavior.
BUSINESS CONTEXT: The 2026-07-15 incident: Step 0 baseline capture failed
      (run_failed), so three deploy-dependent post-merge failures were all
      misclassified as regressions, halting finalize incorrectly. The recovery
      branch re-runs only the failing test IDs against origin/main HEAD to
      recover a targeted baseline, enabling correct pre_existing vs. regression
      classification and unblocking the finalize.
ARCHITECTURE: Tests use run_workflow_under_e2() from _workflow_engine_harness.py
      to run finalize-feature.js in a Node.js subprocess with mock agent() calls
      controlled via label_responses. Behavioral assertions inspect the triage
      agent call's prompt to verify the correct baseline_failures value is
      forwarded. This catches implementation bugs that source-text grep tests
      cannot catch (e.g. the logic is inverted, the wrong branch runs).

ACs: FIN-100c-4, FIN-100c-5, FIN-100c-6, FIN-100c-7, FIN-100c-8, FIN-100c-9
TICKET: TICKET-20260715-FinalizeBaselineFallbackTargetedRerun
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/). E402 is suppressed in ruff.toml.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

# Canonical post-merge failing test IDs used across behavioral tests.
# These represent a realistic set of deploy-dependent or pre-existing failures.
_POST_MERGE_FAILURES = [
    "tests/foo.py::test_one",
    "tests/bar.py::test_two",
    "tests/baz.py::test_three",
]

_HARNESS_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_label_responses(
    post_merge_failing_tests: list | None = None,
    targeted_rerun_response: dict | None = None,
) -> dict:
    """Build label_responses that drive finalize-feature.js to the recovery step.

    Drives Step 0 to fail (baselineFailures=null), Step 1 to find an open PR,
    Step 2 to merge cleanly, and Step 3 test run to fail with the given tests.
    targeted_rerun_response controls what the recovery agent returns.
    """
    if post_merge_failing_tests is None:
        post_merge_failing_tests = list(_POST_MERGE_FAILURES)
    responses: dict = {
        "pre-flight": {
            "found": True,
            "branch": "feature/test-recovery",
            "worktree_root": "/tmp/test-wt",
        },
        "gh-config": {"gh_target_account": None, "gh_repo": None},
        # run_failed → baselineFailures stays null, recovery branch activates.
        "step-0-baseline": {
            "status": "run_failed",
            "baseline_sha": None,
            "baseline_failures": None,
            "baseline_run_at": None,
        },
        # PR already open → skip pull-request agent dispatch.
        "step-1-pr-probe": {
            "found": True,
            "number": 42,
            "url": "https://github.com/test/pull/42",
        },
        # Clean merge → no conflict halt.
        "step-2-merge-main": {"status": "merged", "merge_strategy": "merged_main"},
        # Non-empty failing_tests → enters triage sub-step (and potentially recovery).
        "step-3-test-run": {
            "passed": False,
            "output": "test output stub",
            "failing_tests": post_merge_failing_tests,
        },
        "step-3-changed-files": {"changed_files": []},
        # blocks_finalization=false → triage does not halt the workflow.
        "step-3-triage": {"triage_report": [], "blocks_finalization": False},
    }
    if targeted_rerun_response is not None:
        responses["step-3-targeted-rerun"] = targeted_rerun_response
    return responses


def _find_triage_call(result: HarnessResult):
    """Return the step-3-triage AgentCall from the harness result, or None."""
    for call in result.agent_calls:
        if call.label == "step-3-triage":
            return call
    return None


def _extract_baseline_failures(triage_call) -> tuple:
    """Parse the baseline_failures value from the triage agent's prompt.

    The prompt contains:
      '...baseline_failures=<JSON value>, baseline_sha=...'

    Returns (parsed_value, error_str).
    parsed_value is the parsed Python value (list or None on success).
    error_str is None on success, a description string on failure.
    """
    prompt = triage_call.prompt
    if not isinstance(prompt, str):
        return None, f"triage prompt is not a string: {type(prompt)!r}"
    marker = "baseline_failures="
    idx = prompt.find(marker)
    if idx == -1:
        return None, "'baseline_failures=' not found in triage prompt"
    after = prompt[idx + len(marker):]
    end_marker = ", baseline_sha="
    end_idx = after.find(end_marker)
    if end_idx == -1:
        return None, f"', baseline_sha=' not found after baseline_failures; got: {after[:120]!r}"
    json_str = after[:end_idx]
    try:
        return json.loads(json_str), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error on {json_str!r}: {exc}"


# ---------------------------------------------------------------------------
# Smoke checks (thin, non-tautological — guard naming and label contracts)
# These verify implementation artifacts that must stay stable; they are not
# the primary evidence (behavioral tests below are).
# ---------------------------------------------------------------------------


def test_js_uses_recoveredbaselinefailures_variable():
    """The recovery variable must be named 'recoveredBaselineFailures' in the JS."""
    js = _JS_PATH.read_text(encoding="utf-8")
    assert "recoveredBaselineFailures" in js, (
        "finalize-feature.js must define the 'recoveredBaselineFailures' variable "
        "to hold the targeted main-HEAD rerun results. Renaming it breaks the "
        "implementation contract and the behavioral tests below."
    )


def test_js_fallback_log_uses_rerun_unavailable_phrase():
    """The conservative fallback path must log 'targeted rerun unavailable'."""
    js = _JS_PATH.read_text(encoding="utf-8")
    assert "targeted rerun unavailable" in js, (
        "finalize-feature.js must log 'targeted rerun unavailable' in the fallback "
        "path (FIN-100c-9) so operators can distinguish conservative fallback from a "
        "genuine regression halt."
    )


def test_js_uses_step3_targeted_rerun_label():
    """The recovery agent dispatch must use label='step-3-targeted-rerun'."""
    js = _JS_PATH.read_text(encoding="utf-8")
    assert "step-3-targeted-rerun" in js, (
        "finalize-feature.js must dispatch the recovery agent with "
        "label='step-3-targeted-rerun'. Absent — label was renamed or removed."
    )


# ---------------------------------------------------------------------------
# Behavioral tests
#
# Each test drives the full workflow body via run_workflow_under_e2(), then
# locates the step-3-triage agent call and asserts on the baseline_failures
# value embedded in its prompt. This is mutation-resistant: inverting the
# recovery logic in JS causes baseline_failures to carry the wrong value,
# which these tests detect directly.
#
# Mutation resistance verified (see task sign-off): temporarily setting
# baselineFailures = null in the success arm caused tests 1-3 to fail;
# reverting restored them to green.
# ---------------------------------------------------------------------------


def test_behavioral_recovery_ok_subset_triage_gets_recovered_list():
    """AC FIN-100c-6: recovery ok, subset → triage receives exactly the recovered subset.

    Post-merge failures: [T1, T2, T3]. Recovery reports [T2, T3] fail on main.
    Expected: triage receives baseline_failures=[T2, T3] (T1 is a regression).
    """
    recovered = ["tests/bar.py::test_two", "tests/baz.py::test_three"]
    label_responses = _base_label_responses(
        targeted_rerun_response={"status": "ok", "recovered_failures": recovered},
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=label_responses, timeout=_HARNESS_TIMEOUT)

    triage_call = _find_triage_call(result)
    assert triage_call is not None, (
        "step-3-triage agent was not dispatched. "
        f"Dispatched labels: {[c.label for c in result.agent_calls]!r}. "
        f"harness stderr: {result.stderr[:400]!r}"
    )

    baseline_failures, err = _extract_baseline_failures(triage_call)
    assert err is None, f"Failed to parse baseline_failures from triage prompt: {err}"
    assert baseline_failures == recovered, (
        f"Expected triage baseline_failures={recovered!r} (recovered subset), "
        f"but got {baseline_failures!r}. "
        "The success arm must set baselineFailures = recoveredBaselineFailures "
        "before the triage dispatch (FIN-100c-6)."
    )


def test_behavioral_recovery_ok_empty_triage_gets_empty_not_null():
    """AC FIN-100c-6: recovery ok, empty → triage receives [], NOT null.

    Post-merge failures: [T1, T2, T3]. Recovery reports [] (nothing fails on main).
    Expected: triage receives baseline_failures=[] — the [] vs null distinction is
    load-bearing: null would re-trigger the conservative all-regressions path.
    """
    label_responses = _base_label_responses(
        targeted_rerun_response={"status": "ok", "recovered_failures": []},
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=label_responses, timeout=_HARNESS_TIMEOUT)

    triage_call = _find_triage_call(result)
    assert triage_call is not None, (
        "step-3-triage agent was not dispatched. "
        f"Dispatched labels: {[c.label for c in result.agent_calls]!r}"
    )

    baseline_failures, err = _extract_baseline_failures(triage_call)
    assert err is None, f"Failed to parse baseline_failures: {err}"
    assert baseline_failures is not None, (
        "triage received baseline_failures=null but expected [] (empty list). "
        "An empty recovered baseline must be forwarded as [], never null — "
        "null would re-trigger the conservative null-baseline path in triage."
    )
    assert baseline_failures == [], (
        f"Expected triage baseline_failures=[] but got {baseline_failures!r}."
    )


def test_behavioral_recovery_ok_all_pre_existing_triage_gets_all():
    """AC FIN-100c-6/8: all post-merge failures pre-exist on main → triage gets all.

    Post-merge failures: [T1, T2, T3]. Recovery reports all three fail on main.
    Expected: triage receives baseline_failures=[T1, T2, T3], so regressions=[] and
    blocks_finalization=false (the 2026-07-15 deploy-dependent false-halt scenario).
    """
    all_failures = list(_POST_MERGE_FAILURES)
    label_responses = _base_label_responses(
        targeted_rerun_response={"status": "ok", "recovered_failures": all_failures},
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=label_responses, timeout=_HARNESS_TIMEOUT)

    triage_call = _find_triage_call(result)
    assert triage_call is not None, (
        "step-3-triage agent was not dispatched. "
        f"Dispatched labels: {[c.label for c in result.agent_calls]!r}"
    )

    baseline_failures, err = _extract_baseline_failures(triage_call)
    assert err is None, f"Failed to parse baseline_failures: {err}"
    assert baseline_failures == all_failures, (
        f"Expected triage baseline_failures={all_failures!r} (all pre-existing), "
        f"but got {baseline_failures!r}."
    )


def test_behavioral_recovery_checkout_failed_triage_gets_null():
    """AC FIN-100c-9: checkout_failed → conservative fallback → triage gets null.

    When the main-HEAD worktree checkout fails, the recovery branch must fall back
    to the conservative null-baseline path: triage receives baseline_failures=null
    and treats all post-merge failures as regressions.
    """
    label_responses = _base_label_responses(
        targeted_rerun_response={"status": "checkout_failed", "recovered_failures": None},
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=label_responses, timeout=_HARNESS_TIMEOUT)

    triage_call = _find_triage_call(result)
    assert triage_call is not None, (
        "step-3-triage agent was not dispatched. "
        f"Dispatched labels: {[c.label for c in result.agent_calls]!r}"
    )

    baseline_failures, err = _extract_baseline_failures(triage_call)
    assert err is None, f"Failed to parse baseline_failures: {err}"
    assert baseline_failures is None, (
        f"Expected triage to receive baseline_failures=null after checkout_failed "
        f"(conservative fallback must preserve null), but got {baseline_failures!r}."
    )


def test_behavioral_empty_post_merge_failures_skips_recovery():
    """AC FIN-100c-5: postMergeFailures empty → recovery agent never dispatched.

    The targeted-rerun condition is: baselineFailures === null AND
    postMergeFailures.length > 0. When post-merge failures is empty the second
    clause is false, so the step-3-targeted-rerun agent must not be called.
    """
    label_responses = _base_label_responses(
        post_merge_failing_tests=[],  # empty — recovery condition is false
        targeted_rerun_response=None,
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=label_responses, timeout=_HARNESS_TIMEOUT)

    dispatched_labels = [c.label for c in result.agent_calls]
    assert "step-3-targeted-rerun" not in dispatched_labels, (
        "step-3-targeted-rerun was dispatched but must NOT be when postMergeFailures "
        "is empty (condition: baselineFailures===null AND postMergeFailures.length>0). "
        f"All dispatched labels: {dispatched_labels!r}"
    )


# ---------------------------------------------------------------------------
# Coverage backfill (ac-audit 2026-07-21) — direct tests for the thin spots the
# audit flagged on FIN-100c-4/-7/-9 (each previously covered only transitively).
# ---------------------------------------------------------------------------


def test_fin_100c_9_build_failed_triage_gets_null():
    """AC FIN-100c-9: build_failed (not only checkout_failed) → conservative fallback.

    A recovery build failure traverses the same non-ok arm as checkout_failed and must
    preserve the null baseline, so triage treats all post-merge failures as regressions.
    """
    label_responses = _base_label_responses(
        targeted_rerun_response={"status": "build_failed", "recovered_failures": None},
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=label_responses, timeout=_HARNESS_TIMEOUT)
    triage_call = _find_triage_call(result)
    assert triage_call is not None, (
        f"step-3-triage not dispatched. labels={[c.label for c in result.agent_calls]!r}"
    )
    baseline_failures, err = _extract_baseline_failures(triage_call)
    assert err is None, f"Failed to parse baseline_failures: {err}"
    assert baseline_failures is None, (
        f"build_failed must fall back to a null baseline (conservative), got {baseline_failures!r}."
    )


def test_fin_100c_9_fallback_surfaces_modified_by_branch():
    """AC FIN-100c-9: the conservative fallback surfaces modified_by_branch so operators
    can see which failing tests the branch touched."""
    js = _JS_PATH.read_text(encoding="utf-8")
    assert "modified_by_branch" in js, (
        "finalize-feature.js must surface 'modified_by_branch' on the rerun-unavailable "
        "conservative fallback path (FIN-100c-9)."
    )


def test_fin_100c_7_pass_on_main_excluded_from_baseline():
    """AC FIN-100c-7: a test that PASSES on main HEAD is excluded from the recovered
    baseline (→ regression); tests that FAIL on main are included (→ pre_existing).

    Post-merge [T1,T2,T3]; recovery reports [T2,T3] fail on main (T1 passes on main).
    Forwarded baseline_failures must be exactly [T2,T3] — T1 excluded.
    """
    fail_on_main = ["tests/bar.py::test_two", "tests/baz.py::test_three"]
    passes_on_main = "tests/foo.py::test_one"
    label_responses = _base_label_responses(
        targeted_rerun_response={"status": "ok", "recovered_failures": fail_on_main},
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=label_responses, timeout=_HARNESS_TIMEOUT)
    triage_call = _find_triage_call(result)
    assert triage_call is not None, (
        f"step-3-triage not dispatched. labels={[c.label for c in result.agent_calls]!r}"
    )
    baseline_failures, err = _extract_baseline_failures(triage_call)
    assert err is None, f"Failed to parse baseline_failures: {err}"
    assert baseline_failures == fail_on_main, (
        f"Expected baseline_failures={fail_on_main!r} (fail-on-main subset); got {baseline_failures!r}."
    )
    assert passes_on_main not in (baseline_failures or []), (
        f"{passes_on_main!r} passes on main HEAD, so it must be EXCLUDED from the baseline "
        "(→ regression per FIN-100c-7), but it is present."
    )


def test_fin_100c_7_triage_prompt_encodes_classification_rule():
    """AC FIN-100c-7: the triage agent encodes the rule applied to the (recovered)
    baseline — in-baseline → pre_existing, absent → regression."""
    triage = (_REPO_ROOT / "templates" / "agents" / "test-failure-triage.md").read_text(encoding="utf-8")
    low = triage.lower()
    assert "pre_existing" in low or "pre-existing" in low, (
        "test-failure-triage.md must define the pre_existing classification (FIN-100c-7)."
    )
    assert "regression" in low, (
        "test-failure-triage.md must define the regression classification (FIN-100c-7)."
    )


def test_fin_100c_4_recovery_deploys_before_targeted_rerun():
    """AC FIN-100c-4: the targeted rerun deploys against the fresh main-HEAD checkout
    BEFORE re-running the failing tests (build parity with Step 0 / Step 3)."""
    js = _JS_PATH.read_text(encoding="utf-8")
    idx_label = js.find("step-3-targeted-rerun")
    assert idx_label != -1, "step-3-targeted-rerun dispatch must exist (FIN-100c-4)."
    region = js[max(0, idx_label - 2500):idx_label + 400]
    assert "Deploy shims before rerun" in region or "build parity" in region, (
        "The targeted-rerun recovery prompt must deploy (build.py) before re-running the "
        "failing tests, for build parity (FIN-100c-4)."
    )


# ---------------------------------------------------------------------------
# FIN-100g-4 deploy-parity self-check — behavioral guards (post-review remediation).
# These execute the real JS via the E2 harness, so they FAIL if the gate/exclusion
# logic is broken. They cover the two load-bearing behaviors the source-substring
# tests could not: the H-1 empty-set flip, and "a genuine failure survives → triage".
# ---------------------------------------------------------------------------


def _base_with_captured_baseline(post_merge_failing_tests, deploy_parity_response):
    """label_responses with a SUCCESSFUL Step 0 baseline (non-null) so the
    null-baseline recovery branch does NOT run — isolating the deploy-parity
    self-check — plus a step-3-deploy-parity response.
    """
    lr = _base_label_responses(post_merge_failing_tests=post_merge_failing_tests)
    lr["step-0-baseline"] = {
        "status": "ok",
        "baseline_sha": "deadbeef",
        "baseline_failures": [],
        "baseline_run_at": "2026-07-21T00:00:00Z",
    }
    lr["step-3-deploy-parity"] = deploy_parity_response
    return lr


def test_h1_empty_post_merge_failures_does_not_run_deploy_parity():
    """H-1: a Step-3 run with testPassed=false but an EMPTY failure set (the
    malformed/ambiguous case) must NOT enter the deploy-parity self-check, so it can
    never flip testPassed→true and skip triage/merge on a malformed test run.
    """
    lr = _base_with_captured_baseline(
        post_merge_failing_tests=[],  # testPassed=false, postMergeFailures=[]
        deploy_parity_response={
            "deploy_consistent": False, "redeployed": True,
            "build_state_only_failures": ["tests/x.py::t"], "still_failing": [],
        },
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=lr, timeout=_HARNESS_TIMEOUT)
    labels = [c.label for c in result.agent_calls]
    assert "step-3-deploy-parity" not in labels, (
        "deploy-parity ran on an EMPTY post-merge failure set — the H-1 gate "
        "(postMergeFailures.length > 0) is missing; an empty set could flip "
        f"testPassed→true and skip triage. Dispatched: {labels!r}. stderr: {result.stderr[:300]!r}"
    )


def test_fin_100g_4i_genuine_failure_survives_exclusion_and_reaches_triage():
    """FIN-100g-4-i: when some failures are build-state (cleared by re-deploy) but a
    GENUINE failure remains, the genuine one is NOT excluded and triage IS dispatched
    (so it can HALT). If the exclusion wrongly cleared everything, testPassed would flip
    true and triage would be skipped — this test would then fail.
    """
    failures = ["tests/a.py::t1", "tests/b.py::t2", "tests/c.py::t3"]
    lr = _base_with_captured_baseline(
        post_merge_failing_tests=failures,
        deploy_parity_response={
            "deploy_consistent": True, "redeployed": True,
            "build_state_only_failures": ["tests/a.py::t1", "tests/b.py::t2"],
            "still_failing": ["tests/c.py::t3"],
        },
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=lr, timeout=_HARNESS_TIMEOUT)
    labels = [c.label for c in result.agent_calls]
    assert "step-3-deploy-parity" in labels, (
        f"deploy-parity self-check did not run with a non-empty failure set. Dispatched: {labels!r}"
    )
    assert "step-3-triage" in labels, (
        "A genuine failure (tests/c.py::t3) remained after build-state exclusion, so triage "
        "must be dispatched (it can HALT). It was not — the exclusion likely cleared a genuine "
        f"failure or flipped testPassed→true. Dispatched: {labels!r}"
    )


def test_fin_100g_4i_still_failing_contradiction_is_not_excluded():
    """M-2 contradiction guard: a test the agent lists in BOTH build_state_only_failures
    AND still_failing must NOT be excluded — it reaches triage. Without the guard all
    three would be excluded, testPassed would flip true, and triage would be skipped.
    """
    failures = ["tests/a.py::t1", "tests/b.py::t2", "tests/c.py::t3"]
    lr = _base_with_captured_baseline(
        post_merge_failing_tests=failures,
        deploy_parity_response={
            "deploy_consistent": True, "redeployed": True,
            "build_state_only_failures": failures,            # claims all cleared
            "still_failing": ["tests/c.py::t3"],              # but c.py::t3 still fails
        },
    )
    result = run_workflow_under_e2(_JS_PATH, label_responses=lr, timeout=_HARNESS_TIMEOUT)
    labels = [c.label for c in result.agent_calls]
    assert "step-3-triage" in labels, (
        "A test listed in BOTH build_state_only_failures and still_failing was excluded "
        "anyway (contradiction), flipping testPassed→true and skipping triage. The M-2 guard "
        f"must keep it. Dispatched: {labels!r}"
    )
