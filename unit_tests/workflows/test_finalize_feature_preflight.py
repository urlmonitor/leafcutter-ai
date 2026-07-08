"""
MODULE: test_finalize_feature_preflight
GOAL: Verify that both the Step 0 baseline dispatch prompt and the Step 3
    test-runner dispatch prompt in finalize-feature.js contain the build.py /
    install_shims instruction, so the two test runs share identical deploy
    state and cannot drift apart (FIN-100a-4).

    The tests parse finalize-feature.js as text so they guard the actual prompt
    content reaching the agent, mirroring the pattern in
    test_finalize_feature_step6a.py.

TICKET: TICKET-20260707-FinalizeFeaturePreflightAndBuildSymmetry.md
ACs: FIN-100a-4

DECISION HISTORY
----------------
2026-07-08: Initial test stubs written as RED baseline for the TDD cycle,
            originally covering both FIN-100g-1 (pre-flight target resolution)
            and FIN-100a-4 (build/deploy symmetry).
2026-07-08: Scope reduced to FIN-100a-4 only. The FIN-100g-1 pre-flight fix
            shipped independently on main via PR #231
            (TICKET-20260707-Finalize_Preflight_Branch_Detection), which owns
            its own tests. The FIN-100g-1 test class (which asserted this
            branch's now-discarded args.target_branch approach) was removed to
            avoid a competing-solution collision; this ticket delivers only the
            build/deploy-symmetry change.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _get_step_block(js: str, step_label: str, next_step_label: str) -> str:
    """Extract the text for a given step phase block.

    Returns text from phase('<step_label>') up to (but not including)
    phase('<next_step_label>'). Returns an empty string when the start marker
    is absent, and the tail of the file when only the end marker is absent.
    """
    start_marker = f"phase('{step_label}')"
    end_marker = f"phase('{next_step_label}')"
    start = js.find(start_marker)
    if start == -1:
        return ""
    end = js.find(end_marker, start)
    if end == -1:
        return js[start:]
    return js[start:end]


# ---------------------------------------------------------------------------
# FIN-100a-4: Step 0 and Step 3 must be symmetric in their build/deploy setup
# ---------------------------------------------------------------------------

class TestBaselineAndPostMergeBuildSymmetry:
    """FIN-100a-4: both Step 0 (pre-merge baseline) and Step 3 (post-merge suite)
    must run scripts/build.py (install_shims) before their respective test runs.
    """

    def test_step0_baseline_prompt_contains_build_py(self):
        """Step 0's dispatch prompt must instruct the agent to run scripts/build.py
        (install_shims) before the pytest baseline run inside the temp worktree.

        Gap: Step 0 previously ran `pytest --tb=no -q` directly without first
        deploying the shims. Deploy-dependent tests (e.g. check_secrets,
        commit_guardian) therefore fail RED in the baseline even though they would
        pass in a properly-built environment, skewing the triage set-difference.
        """
        step0 = _get_step_block(_js_text(), "Step 0", "Step 1")
        has_build = (
            "build.py" in step0
            or "scripts/build.py" in step0
            or "install_shims" in step0
        )
        assert has_build, (
            "Step 0 baseline dispatch prompt must include a build.py / install_shims "
            "instruction before running pytest. "
            "Without it, ~13 deploy-dependent tests fail in the baseline."
        )

    def test_step3_test_runner_prompt_contains_build_py(self):
        """Step 3's test-runner dispatch prompt must instruct the agent to run
        scripts/build.py (install_shims) before the post-merge test run.

        Gap: Step 3 previously invoked the test-runner without build.py. Because
        Step 0 also lacked build.py, the regression set-difference
        (post_merge - baseline) misclassified the resulting deploy-dependent
        failures as regressions — causing a spurious test_regression HALT before
        the PR could be merged.
        """
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        has_build = (
            "build.py" in step3
            or "scripts/build.py" in step3
            or "install_shims" in step3
        )
        assert has_build, (
            "Step 3 post-merge test-runner dispatch prompt must include a build.py / "
            "install_shims instruction before running the suite."
        )

    def test_step0_and_step3_both_reference_build_py(self):
        """Both Step 0 and Step 3 must reference build.py / install_shims so the
        two test runs share identical deploy state and cannot drift apart.

        This is the regression-guard for FIN-100a-4: if one step is fixed but the
        other is not, this test surfaces the asymmetry explicitly.
        """
        js = _js_text()
        step0 = _get_step_block(js, "Step 0", "Step 1")
        step3 = _get_step_block(js, "Step 3", "Step 3.5")

        step0_has_build = (
            "build.py" in step0
            or "scripts/build.py" in step0
            or "install_shims" in step0
        )
        step3_has_build = (
            "build.py" in step3
            or "scripts/build.py" in step3
            or "install_shims" in step3
        )

        assert step0_has_build and step3_has_build, (
            "BOTH Step 0 and Step 3 must reference build.py / install_shims. "
            f"Step 0 has it: {step0_has_build}. Step 3 has it: {step3_has_build}. "
            "Asymmetry between the two runs causes deploy-dependent test failures to "
            "appear in one run but not the other, skewing the triage set-difference "
            "and producing false test_regression halts or false clean baselines."
        )

    def test_step3_build_instruction_precedes_test_run(self):
        """In Step 3, the build.py instruction must appear before the test-suite
        run instruction so shims are deployed before the suite runs.

        If build.py is added to Step 3 but placed after the run instruction, the
        shims are absent during the run and deploy-dependent tests still fail RED.
        Step 3 delegates to the test-runner agent with a "run the full test suite"
        instruction (it does not name pytest literally, unlike the Step 0 baseline),
        so the run marker here is "test suite".
        """
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")

        build_idx = step3.find("build.py")
        if build_idx == -1:
            build_idx = step3.find("install_shims")
        run_idx = step3.lower().find("test suite")

        assert build_idx != -1, (
            "Step 3 must reference build.py / install_shims before the test-suite run"
        )
        assert run_idx != -1, (
            "Step 3 must still instruct the agent to run the full test suite"
        )
        assert build_idx < run_idx, (
            "The build.py / install_shims instruction must appear BEFORE the "
            "test-suite run instruction in Step 3's dispatch prompt so shims are "
            "deployed before the suite runs. Current Step 3 order: build at char "
            f"offset {build_idx}, test-suite run at char offset {run_idx}."
        )
