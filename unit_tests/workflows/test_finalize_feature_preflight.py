"""
MODULE: test_finalize_feature_preflight
GOAL: Verify (1) the pre-flight target-resolution logic in finalize-feature.js
    reads args.target_branch and uses git worktree list --porcelain to locate
    the right worktree rather than the ambient CWD (FIN-100g-1), and (2) that
    both the Step 0 baseline dispatch prompt and the Step 3 test-runner dispatch
    prompt contain the build.py / install_shims instruction so the two test runs
    cannot drift apart (FIN-100a-4).

    All tests in this file must be RED before python-coder implements the fixes
    to templates/workflows-js/finalize-feature.js and GREEN after.

    FIN-100g-1 tests: Currently RED because the pre-flight dispatch in
    finalize-feature.js does not reference args.target_branch, does not invoke
    git worktree list --porcelain, and has no conditional fallback path.

    FIN-100a-4 tests: Currently RED because neither Step 0 nor Step 3 in
    finalize-feature.js includes a build.py / install_shims instruction before
    their respective test runs.

TICKET: TICKET-20260707-FinalizeFeaturePreflightAndBuildSymmetry.md
ACs: FIN-100g-1, FIN-100a-4

DECISION HISTORY
----------------
2026-07-08: Initial test stubs written as RED baseline for TDD cycle.
            Both FIN-100g-1 (pre-flight target resolution) and FIN-100a-4
            (build/deploy symmetry) are covered. Tests parse finalize-feature.js
            as text so they guard the actual prompt content reaching the agent,
            mirroring the pattern established in test_finalize_feature_step6a.py.
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


def _get_preflight_block(js: str) -> str:
    """Extract the first pre-flight section of finalize-feature.js.

    Returns the text from phase('Pre-flight') up to (but not including)
    phase('Pre-flight 2'), which is where the gh account check lives. This
    isolates the branch/worktree-resolution logic that FIN-100g-1 targets.
    Falls back to phase('Step 0') as the end marker when Pre-flight 2 is absent.
    """
    start_marker = "phase('Pre-flight')"
    # End at Pre-flight 2 (gh account check) — not the target of FIN-100g-1.
    end_marker = "phase('Pre-flight 2')"
    start = js.find(start_marker)
    if start == -1:
        return ""
    end = js.find(end_marker, start)
    if end == -1:
        # Pre-flight 2 may not exist yet; fall back to Step 0 as the boundary.
        end = js.find("phase('Step 0')", start)
    if end == -1:
        return js[start:]
    return js[start:end]


def _get_step_block(js: str, step_label: str, next_step_label: str) -> str:
    """Extract the text for a given step phase block.

    Returns text from phase('<step_label>') up to (but not including)
    phase('<next_step_label>'). Returns an empty string when either marker
    is absent.
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
# FIN-100g-1: pre-flight must resolve branch/worktree_root from args.target_branch
# ---------------------------------------------------------------------------

class TestPreflightTargetResolution:
    """FIN-100g-1: the pre-flight section of finalize-feature.js must accept an
    explicit target branch via args.target_branch, use git worktree list --porcelain
    to locate the correct worktree, and fall back to CWD detection when no target
    is provided.

    Every test in this class is RED until python-coder updates the pre-flight
    dispatch in finalize-feature.js.
    """

    def test_preflight_reads_args_target_branch(self):
        """The pre-flight section must reference args.target_branch (or equivalent)
        so callers can pass an explicit feature branch name.

        Gap: the current pre-flight uses only `git branch --show-current`, which
        resolves to the CWD's branch. When finalize is invoked from the main
        checkout, BRANCH is set to 'main' and the workflow aborts immediately —
        ignoring the branch the caller actually wanted to finalize.
        """
        preflight = _get_preflight_block(_js_text())
        has_target_branch_read = (
            "args.target_branch" in preflight
            or 'args["target_branch"]' in preflight
            or "args?.target_branch" in preflight
            or "targetBranch" in preflight
        )
        assert has_target_branch_read, (
            "Pre-flight must read args.target_branch (or derive targetBranch from args) "
            "to accept an explicit feature branch from the caller. "
            "Currently the pre-flight only reads git branch --show-current (ambient CWD), "
            "which resolves to 'main' when finalize is run from the main checkout — "
            "causing a spurious 'must be run from a feature branch' abort."
        )

    def test_preflight_prompt_uses_git_worktree_list_porcelain(self):
        """When a target branch is provided, the pre-flight dispatch must instruct
        the agent to run 'git worktree list --porcelain' to locate the worktree
        where that branch is currently checked out.

        Gap: the current prompt only runs git branch --show-current and
        git rev-parse --show-toplevel, which are CWD-relative commands and cannot
        discover a worktree at a different path.
        """
        preflight = _get_preflight_block(_js_text())
        assert "worktree list --porcelain" in preflight, (
            "Pre-flight dispatch prompt must include 'git worktree list --porcelain' "
            "so the agent can find the worktree where the target branch is checked out "
            "regardless of the CWD. "
            "Currently the prompt only uses git branch --show-current (CWD-relative)."
        )

    def test_preflight_handles_no_worktree_for_target_branch(self):
        """The pre-flight must explicitly handle the case where the target branch
        has no checked-out worktree — returning a clear, branch-named error.

        Gap: the current pre-flight has no such conditional. When git worktree list
        --porcelain returns no match for the target branch, the workflow should
        surface a message such as 'no worktree for branch <name>' rather than
        silently resolving to the wrong repo or producing a generic 'branch: unknown'
        result.
        """
        preflight = _get_preflight_block(_js_text())
        has_no_worktree_handling = (
            "no worktree" in preflight.lower()
            or "not found" in preflight.lower()
            # Accept 'error' language paired with target branch reference as evidence
            # that the no-worktree case is described in the dispatch prompt.
            or (
                "error" in preflight.lower()
                and (
                    "target_branch" in preflight
                    or "targetBranch" in preflight
                )
            )
        )
        assert has_no_worktree_handling, (
            "Pre-flight dispatch prompt must handle the 'no worktree for target branch' case "
            "and instruct the agent to return a clear branch-named error. "
            "Currently the prompt has no such branch-not-found path."
        )

    def test_preflight_falls_back_to_cwd_when_no_target_provided(self):
        """When args.target_branch is absent or null, the pre-flight must fall back
        to CWD-based detection (git branch --show-current + git rev-parse) so that
        existing callers who do not pass a target branch continue to work unchanged.

        Gap: once args.target_branch is introduced, the existing CWD-based path
        must remain as the fallback — it must NOT be unconditionally replaced.
        This test asserts that both the new (target_branch) and the legacy (CWD)
        paths are present in the pre-flight block.
        """
        preflight = _get_preflight_block(_js_text())
        has_target_ref = (
            "args.target_branch" in preflight
            or 'args["target_branch"]' in preflight
            or "targetBranch" in preflight
        )
        has_cwd_fallback = "git branch --show-current" in preflight
        assert has_target_ref and has_cwd_fallback, (
            "Pre-flight must include BOTH: (1) args.target_branch handling for the "
            "new target-resolution path, AND (2) git branch --show-current as the "
            "fallback for backward compatibility when no target branch is provided. "
            f"has_target_ref={has_target_ref}, has_cwd_fallback={has_cwd_fallback}."
        )

    def test_preflight_abort_condition_anchored_to_resolved_target(self):
        """The 'must be run from a feature branch' abort must fire on the RESOLVED
        TARGET branch — not on the ambient CWD branch.

        After the fix, the abort condition (BRANCH === 'main' || BRANCH === 'master')
        must be reached only after the target-resolution logic has set BRANCH to the
        target branch (not the CWD branch). This test verifies that the pre-flight
        block contains the args.target_branch / targetBranch reference that drives
        the resolved value of BRANCH before the abort fires.

        Gap: the current pre-flight sets BRANCH from git branch --show-current
        (CWD-based). When the CWD is on main, BRANCH = 'main' → abort fires even
        though the target feature branch is valid.
        """
        preflight = _get_preflight_block(_js_text())
        # The args.target_branch reference must be present in the pre-flight block
        # so the resolved target (not the CWD branch) drives the abort.
        has_target_ref = (
            "args.target_branch" in preflight
            or 'args["target_branch"]' in preflight
            or "targetBranch" in preflight
        )
        assert has_target_ref, (
            "args.target_branch (or targetBranch) must appear in the pre-flight block "
            "before the 'must be run from a feature branch' abort condition so that "
            "BRANCH is set to the resolved target, not the ambient CWD branch. "
            "Currently BRANCH is set from git branch --show-current (CWD-relative), "
            "causing the abort to fire spuriously when the CWD is on main."
        )


# ---------------------------------------------------------------------------
# FIN-100a-4: Step 0 and Step 3 must be symmetric in their build/deploy setup
# ---------------------------------------------------------------------------

class TestBaselineAndPostMergeBuildSymmetry:
    """FIN-100a-4: both Step 0 (pre-merge baseline) and Step 3 (post-merge suite)
    must run scripts/build.py (install_shims) before their respective test runs.

    Every test in this class is RED until python-coder adds the build.py /
    install_shims instruction to both step prompts in finalize-feature.js.
    """

    def test_step0_baseline_prompt_contains_build_py(self):
        """Step 0's dispatch prompt must instruct the agent to run scripts/build.py
        (install_shims) before the pytest baseline run inside the temp worktree.

        Gap: Step 0 currently runs `pytest --tb=no -q` directly without first
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
            "Currently Step 0 invokes pytest directly without deploying shims, "
            "causing ~13 deploy-dependent tests to fail in the baseline."
        )

    def test_step3_test_runner_prompt_contains_build_py(self):
        """Step 3's test-runner dispatch prompt must instruct the agent to run
        scripts/build.py (install_shims) before the post-merge test run.

        Gap: Step 3 currently invokes the test-runner without build.py. Because
        Step 0 also lacks build.py (see prior test), the regression set-difference
        (post_merge − baseline) misclassifies the resulting deploy-dependent
        failures as regressions — causing a spurious test_regression HALT before
        the PR can be merged.
        """
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        has_build = (
            "build.py" in step3
            or "scripts/build.py" in step3
            or "install_shims" in step3
        )
        assert has_build, (
            "Step 3 post-merge test-runner dispatch prompt must include a build.py / "
            "install_shims instruction before running the suite. "
            "Without it, ~13 deploy-dependent tests fail RED in Step 3 while passing "
            "in the Step 0 baseline (once Step 0 is also fixed), causing the triage "
            "set-difference to misclassify them as regressions and halt finalization."
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

    def test_step3_build_instruction_precedes_pytest_invocation(self):
        """In Step 3, the build.py instruction must appear before the pytest
        invocation so shims are deployed before the test suite runs.

        If build.py is added to Step 3 but placed after the pytest line, the shims
        are absent during the run and deploy-dependent tests still fail RED.
        """
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")

        build_idx = step3.find("build.py")
        if build_idx == -1:
            build_idx = step3.find("install_shims")
        pytest_idx = step3.find("pytest")

        # build.py must be present (first assertion mirrors test_step3_test_runner above)
        assert build_idx != -1, (
            "Step 3 must reference build.py / install_shims before the pytest invocation"
        )
        assert pytest_idx != -1, (
            "Step 3 must still invoke pytest to run the post-merge test suite"
        )
        # Ordering: build must precede pytest within the step 3 block.
        assert build_idx < pytest_idx, (
            "The build.py / install_shims instruction must appear BEFORE the pytest "
            "invocation in Step 3's dispatch prompt so shims are deployed before the "
            "suite runs. Current Step 3 order: build at char offset "
            f"{build_idx}, pytest at char offset {pytest_idx}."
        )
