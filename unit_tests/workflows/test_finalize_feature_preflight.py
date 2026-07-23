"""
MODULE: test_finalize_feature_preflight
GOAL: Verify that both the Step 0 baseline dispatch prompt and the Step 3
    test-runner dispatch prompt in finalize-feature.js contain the build.py /
    install_shims instruction, so the two test runs share identical deploy
    state and cannot drift apart (FIN-100a-4).

    Also verifies (FIN-100g-2, FIN-100g-2-i) that the pre-flight argument
    normalization accepts the target as a bare string OR as an object carrying
    a `target` / `target_branch` key, and that an empty/missing key routes to
    CWD-based detection rather than producing an empty-target collapse.

    The tests parse finalize-feature.js as text so they guard the actual prompt
    content reaching the agent, mirroring the pattern in
    test_finalize_feature_step6a.py.

TICKET: TICKET-20260707-FinalizeFeaturePreflightAndBuildSymmetry.md (FIN-100a-4)
        TICKET-20260721-FIN-100g-2.md (FIN-100g-2, FIN-100g-2-i)
ACs: FIN-100a-4, FIN-100g-2, FIN-100g-2-i

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
2026-07-21: Added FIN-100g-2 and FIN-100g-2-i test classes. FIN-100g-2 covers
            the argument normalization (bare string AND object {target}/
            {target_branch} forms). FIN-100g-2-i covers the empty/missing-key
            fallback to CWD-based detection (TICKET-20260721-FIN-100g-2.md).
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


# ---------------------------------------------------------------------------
# Shared helper for the FIN-100g-2 / FIN-100g-2-i test classes
# ---------------------------------------------------------------------------

def _get_preflight_block(js: str) -> str:
    """Extract the Pre-flight argument-normalization block.

    Returns text from phase('Pre-flight') up to (but not including)
    phase('Pre-flight 2'). This is the segment that contains the epicArg
    normalization code which FIN-100g-2 and FIN-100g-2-i require to handle
    both bare strings and object {target}/{target_branch} arguments.
    """
    return _get_step_block(js, "Pre-flight", "Pre-flight 2")


# ---------------------------------------------------------------------------
# FIN-100g-2: pre-flight must accept bare string AND object {target}/{target_branch}
# ---------------------------------------------------------------------------

class TestPreflightArgNormalizationFIN100g2:
    """FIN-100g-2: pre-flight normalizes its argument from a bare string OR an
    object carrying a `target` / `target_branch` key, yielding the identical
    resolved target for the worktree-resolution step (FIN-100g-1).

    The current (broken) implementation at line 338 of finalize-feature.js:
        const epicArg = (typeof args === 'string' ? args.trim() : '');
    silently collapses any object argument to empty string, so
    {target: 'ge-116a-1'} routes to CWD detection instead of the intended
    worktree. All tests in this class are RED against the current code because
    the normalization block never references args.target or args.target_branch.
    """

    def test_ac_fin100g2_preflight_accepts_bare_string_target(self):
        # covers: FIN-100g-2
        """FIN-100g-2: bare string argument is resolved to the same target as object forms.

        The normalization block must handle BOTH the bare-string case and the object
        case. A normalizer that only handles strings (the current code) fails AC
        FIN-100g-2 even for the string path, because the spec requires the same
        resolved-target contract to hold across all three invocation forms.

        This test asserts that the pre-flight block contains object-form extraction
        code (args.target or args.target_branch) alongside the existing string check,
        confirming the normalization is complete and covers the bare-string case as
        one of the documented input forms.

        Must be implemented to make green:
          Extend the epicArg normalization to extract args.target / args.target_branch
          from object args so that both string and object forms yield the same result.
        """
        preflight = _get_preflight_block(_js_text())

        has_string_check = (
            "typeof args === 'string'" in preflight
            or 'typeof args === "string"' in preflight
        )
        has_object_extraction = (
            "args.target" in preflight
            or "args.target_branch" in preflight
        )

        assert has_string_check, (
            "Pre-flight must retain the typeof-string check for bare-string args."
        )
        assert has_object_extraction, (
            "Pre-flight must ALSO extract the target from object args "
            "(args.target / args.target_branch). "
            "Current code only has the typeof-string check; object args collapse to empty. "
            "FIN-100g-2 requires BOTH string and object forms to resolve identically."
        )

    def test_ac_fin100g2_preflight_accepts_object_target_key(self):
        # covers: FIN-100g-2
        """FIN-100g-2: {target: 'ge-116a-1'} resolves to 'ge-116a-1'.

        The pre-flight normalization must explicitly read args.target when args is
        an object. The current code (typeof args === 'string' ? args.trim() : '')
        never checks args.target, so the {target: ...} form silently collapses to
        empty string and routes to CWD detection instead of the named branch.

        Must be implemented to make green:
          The epicArg normalization must contain args.target (e.g. extracting it
          as: const epicArg = typeof args === 'string' ? args.trim()
                              : (args && (args.target || args.target_branch) || '').trim())
        """
        preflight = _get_preflight_block(_js_text())

        assert "args.target" in preflight, (
            "Pre-flight normalization must reference args.target to handle "
            "{target: 'ge-116a-1'} invocations. "
            "Current code: `typeof args === 'string' ? args.trim() : ''` "
            "never reads args.target, collapsing the object form to empty string. "
            "FIN-100g-2 requires {target: 'ge-116a-1'} to resolve to 'ge-116a-1'."
        )

    def test_ac_fin100g2_preflight_accepts_object_target_branch_key(self):
        # covers: FIN-100g-2
        """FIN-100g-2: {target_branch: 'ge-116a-1'} resolves to 'ge-116a-1'.

        The pre-flight normalization must explicitly read args.target_branch when
        args is an object carrying that key. The current code never checks
        args.target_branch, so this form also silently collapses to empty string.

        Must be implemented to make green:
          The epicArg normalization must contain args.target_branch (in addition to
          args.target) so that both {target: ...} and {target_branch: ...} forms
          resolve to the same target string.
        """
        preflight = _get_preflight_block(_js_text())

        assert "args.target_branch" in preflight, (
            "Pre-flight normalization must reference args.target_branch to handle "
            "{target_branch: 'ge-116a-1'} invocations. "
            "Current code: `typeof args === 'string' ? args.trim() : ''` "
            "never reads args.target_branch, collapsing the object form to empty string. "
            "FIN-100g-2 requires {target_branch: 'ge-116a-1'} to resolve identically "
            "to the bare-string and {target: ...} forms."
        )

    def test_ac_fin100g2_preflight_object_form_does_not_collapse_to_empty(self):
        # covers: FIN-100g-2
        """FIN-100g-2: object form does NOT collapse to an empty target.

        The original (broken) code:
            const epicArg = (typeof args === 'string' ? args.trim() : '');
        produces '' for ANY non-string argument, including {target: 'ge-116a-1'}.
        This test asserts that this pattern is NOT the sole normalization present —
        explicit object-key extraction (args.target / args.target_branch) must also
        be present so that the object form carries through its target value.

        Must be implemented to make green:
          Replace the single-line collapse with a normalization that extracts
          args.target / args.target_branch when args is an object, ensuring a
          non-empty target is NOT reduced to empty string.
        """
        preflight = _get_preflight_block(_js_text())

        # The collapse pattern: typeof args === 'string' ? args.trim() : ''
        # with no additional object-key extraction is the broken state.
        collapse_pattern_present = (
            "typeof args === 'string' ? args.trim() : ''" in preflight
            or "typeof args === 'string' ? args.trim() : \"\"" in preflight
        )
        object_extraction_present = (
            "args.target" in preflight
            or "args.target_branch" in preflight
        )

        assert not (collapse_pattern_present and not object_extraction_present), (
            "Pre-flight uses `typeof args === 'string' ? args.trim() : ''` as the "
            "SOLE normalization, which collapses {target: 'ge-116a-1'} to empty string. "
            "FIN-100g-2 requires object-key extraction (args.target / args.target_branch) "
            "to be present alongside the string check so that the object form does NOT "
            "collapse to an empty target."
        )


# ---------------------------------------------------------------------------
# FIN-100g-2-i: empty/missing-key object falls back to CWD detection
# ---------------------------------------------------------------------------

class TestPreflightArgNormalizationFIN100g2i:
    """FIN-100g-2-i: when the object argument has no target/target_branch key
    (e.g. {}) or carries an empty value (e.g. {target: ''}), the pre-flight
    treats the invocation as 'no explicit target supplied' and routes to the
    existing CWD-based branch/worktree detection (FIN-100g-1).

    It must NOT abort with 'must be run from a feature branch, not main' solely
    because the object argument could not be reduced to a non-empty string.

    All tests are RED against the current code because explicit object extraction
    (args.target / args.target_branch) is absent — the accidental CWD fallback
    via the collapse-to-empty pattern does not satisfy the AC requirement for
    intentional, documented fallback logic.
    """

    def test_ac_fin100g2i_empty_object_falls_back_to_cwd_detection(self):
        # covers: FIN-100g-2-i
        """FIN-100g-2-i: {} is treated as 'no target supplied' → CWD detection.

        When args is {} (empty object with no target/target_branch key), the
        pre-flight must treat this as 'no explicit target supplied' and fall back
        to the CWD-based detection path (FIN-100g-1), NOT produce an empty-target
        collapse that bypasses the resolution step in an undocumented way.

        The current code achieves the CWD fallback accidentally (via '' being falsy)
        but does not explicitly handle the case. This test asserts that explicit
        object extraction (args.target / args.target_branch) is present so the
        fallback is intentional.

        Must be implemented to make green:
          Extend the normalization to check (args.target || args.target_branch || '')
          for object args; the resulting '' for {} triggers the documented CWD
          fallback path.
        """
        preflight = _get_preflight_block(_js_text())

        # Explicit object extraction must be present.
        has_object_extraction = (
            "args.target" in preflight
            or "args.target_branch" in preflight
        )

        assert has_object_extraction, (
            "Pre-flight must explicitly extract args.target / args.target_branch "
            "from object args so that {} is intentionally recognized as 'no target "
            "supplied' and routes to CWD-based detection. "
            "The current accidental fallback (via collapse-to-empty '') does not "
            "satisfy FIN-100g-2-i's requirement for intentional/documented handling."
        )

    def test_ac_fin100g2i_object_empty_target_string_falls_back_to_cwd(self):
        # covers: FIN-100g-2-i
        """FIN-100g-2-i: {target: ''} is treated as 'no target supplied' → CWD detection.

        When args is {target: ''} (object with an empty-string target value), the
        pre-flight must also treat this as 'no explicit target supplied'. This requires
        the normalization to trim the extracted value and check for emptiness, rather
        than merely reading args.target and using it verbatim.

        This test asserts that the normalization contains both object-key extraction
        AND a trim/empty-check so that {target: ''} routes to CWD detection the
        same way {} does.

        Must be implemented to make green:
          The normalization must apply .trim() to the extracted value and treat an
          empty-trimmed result as 'no target supplied' (same CWD fallback as {}).
        """
        preflight = _get_preflight_block(_js_text())

        # Must have explicit object extraction…
        has_object_extraction = (
            "args.target" in preflight
            or "args.target_branch" in preflight
        )
        # …and must apply trim() to handle whitespace/empty values.
        has_trim_on_extraction = ".trim()" in preflight

        assert has_object_extraction, (
            "Pre-flight must explicitly extract args.target / args.target_branch "
            "from object args to handle the {target: ''} empty-value case. "
            "Current code has no object extraction — FIN-100g-2-i is unsatisfied."
        )
        assert has_trim_on_extraction, (
            "Pre-flight normalization must call .trim() on the extracted target value "
            "so that {target: ''} (or {target: '  '}) produces an empty string that "
            "routes to CWD detection rather than a non-empty whitespace target."
        )

    def test_ac_fin100g2i_missing_target_key_does_not_trigger_main_abort(self):
        # covers: FIN-100g-2-i
        """FIN-100g-2-i: the main-branch abort does NOT fire solely because the object
        arg had no resolvable target key.

        The 'must be run from a feature branch, not main' abort must be based on the
        RESOLVED BRANCH (from the pre-flight agent call), not on epicArg alone. An
        empty epicArg from {} or {target: ''} must trigger the CWD-detection path,
        which then returns the actual branch. Only if THAT branch is main/master does
        the abort fire — not as a direct consequence of the object failing to normalize.

        This test asserts:
        (a) the abort check is on BRANCH (not epicArg) — already correct in current code.
        (b) explicit object extraction is present so the empty-epicArg path is reached
            intentionally (not via accidental collapse) for the no-key object case.

        Must be implemented to make green:
          Implement explicit object-key extraction in the normalization so (b) is met.
          The abort check (a) must remain on BRANCH, unchanged from the current code.
        """
        preflight = _get_preflight_block(_js_text())

        # (a) The abort condition must reference BRANCH, not epicArg directly.
        # This ensures the abort fires on the resolved branch, not the raw arg.
        abort_on_branch = (
            'BRANCH === "main"' in preflight
            or "BRANCH === 'main'" in preflight
            or "BRANCH === \"master\"" in preflight
            or "BRANCH === 'master'" in preflight
        )
        # (b) Explicit object extraction must be present (the missing piece in current code).
        has_object_extraction = (
            "args.target" in preflight
            or "args.target_branch" in preflight
        )

        assert abort_on_branch, (
            "Pre-flight main-branch abort must check the resolved BRANCH variable, "
            "not the raw epicArg. This ensures the abort fires on the actual branch "
            "returned by CWD detection, not on an empty epicArg from a missing-key object."
        )
        assert has_object_extraction, (
            "Pre-flight must have explicit object-key extraction (args.target / "
            "args.target_branch) so that the no-key object case reaches the CWD-detection "
            "fallback intentionally. "
            "FIN-100g-2-i requires the fallback to be the documented path, not an "
            "accidental side-effect of the collapse-to-empty pattern."
        )

    def test_ac_fin100g2i_non_string_target_does_not_reach_trim(self):
        # covers: FIN-100g-2-i
        """A truthy non-string target (e.g. {target: 5}) must NOT reach .trim()
        (which would raise a TypeError); it falls back to the empty/CWD path.

        Regression guard for M-1: the normalization must NOT call .trim() directly on
        the raw object extraction `(args.target || args.target_branch) || ''`, because a
        non-string extracted value would crash. The trim must be guarded behind a
        typeof-string check on the extracted candidate.
        """
        preflight = _get_preflight_block(_js_text())
        trims_raw_extraction = (
            "args.target_branch) || '').trim()" in preflight
            or 'args.target_branch) || "").trim()' in preflight
        )
        assert not trims_raw_extraction, (
            "Normalization calls .trim() directly on the object extraction "
            "(args.target || args.target_branch); a truthy non-string target would raise "
            "a TypeError. Guard the trim behind a typeof-string check so a non-string "
            "target falls back to CWD detection (FIN-100g-2-i / M-1)."
        )


# ---------------------------------------------------------------------------
# FIN-100g-3: unresolvable target -> single actionable error naming the target,
# the expected argument forms, and the candidate worktrees.
# ---------------------------------------------------------------------------

class TestUnresolvableTargetErrorFIN100g3:
    """FIN-100g-3: when a supplied target resolves to no registered worktree, the
    pre-flight emits ONE actionable error naming (a) the target, (b) the expected
    argument forms, and (c) the candidate worktrees + branches — more specific than
    the generic FIN-100g-1 branch-named error.
    """

    def test_unresolvable_target_error_names_target(self):
        # covers: FIN-100g-3
        preflight = _get_preflight_block(_js_text())
        assert "No worktree found matching target '${epicArg}'" in preflight, (
            "The no-matching-worktree error must name the unresolved target "
            "(interpolate ${epicArg})."
        )

    def test_unresolvable_target_error_lists_expected_forms(self):
        # covers: FIN-100g-3
        preflight = _get_preflight_block(_js_text())
        assert "bare branch-name string" in preflight, (
            "The unresolved-target error must name the bare-string argument form."
        )
        assert "target/target_branch key" in preflight, (
            "The unresolved-target error must name the object {target/target_branch} form."
        )

    def test_unresolvable_target_error_lists_candidate_worktrees(self):
        # covers: FIN-100g-3
        preflight = _get_preflight_block(_js_text())
        assert "git worktree list --porcelain" in preflight, (
            "The unresolved-target error must source candidates from "
            "`git worktree list --porcelain`."
        )
        assert "andidate worktree" in preflight, (
            "The unresolved-target error must list the candidate worktrees "
            "(and their checked-out branches)."
        )

    def test_unresolvable_target_error_distinct_from_generic(self):
        # covers: FIN-100g-3
        preflight = _get_preflight_block(_js_text())
        # Distinct from the generic FIN-100g-1 error: the FIN-100g-3 message adds
        # BOTH the expected-forms guidance AND the candidate list.
        assert "target/target_branch key" in preflight and "andidate worktree" in preflight, (
            "The unresolved-target error must be more specific than the generic "
            "branch-named error — it must add expected-forms guidance and a candidate list."
        )


# ---------------------------------------------------------------------------
# FIN-100g-4: deploy-parity self-check runs between Step 3 and FIN-100c triage;
# a missing deployed artifact triggers a re-deploy and is classified as
# build-state, never a regression. FIN-100g-4-i: exclusion is data-driven.
# ---------------------------------------------------------------------------

class TestDeployParitySelfCheckFIN100g4:
    """FIN-100g-4: before triaging post-merge failures, the workflow verifies the
    deployed layer is consistent (incl. gitignored deployed copies), re-deploys on
    a miss, and classifies deploy-skew as build-state — never a regression.
    """

    def test_deploy_parity_check_runs_before_triage(self):
        # covers: FIN-100g-4
        js = _js_text()
        dp = js.find('label: "step-3-deploy-parity"')
        triage = js.find('label: "step-3-triage"')
        assert dp != -1, "The deploy-parity self-check (label step-3-deploy-parity) must exist."
        assert triage != -1, "The triage dispatch (label step-3-triage) must exist."
        assert dp < triage, (
            "The deploy-parity self-check must run BEFORE the FIN-100c triage dispatch."
        )

    def test_missing_deployed_artifact_triggers_redeploy(self):
        # covers: FIN-100g-4
        js = _js_text()
        assert 'scripts/build.py" --target-dir' in js, (
            "On a missing deployed artifact the self-check must re-run the deterministic "
            "deploy (build.py --target-dir <WORKTREE_ROOT>)."
        )
        assert "gitignored" in js and "non-git-tracked" in js, (
            "The self-check must verify gitignored, non-git-tracked deployed copies "
            "(e.g. scripts/commit_guardian/*), not just git-tracked files."
        )

    def test_triage_runs_only_after_deploy_verified_consistent(self):
        # covers: FIN-100g-4
        js = _js_text()
        # The self-check filters build-state failures out of postMergeFailures BEFORE
        # the triage branch consumes them, so triage only ever sees a consistent layer.
        assert "build_state_only_failures" in js, (
            "The self-check must produce a build_state_only_failures set."
        )
        assert "postMergeFailures = postMergeFailures.filter" in js, (
            "Build-state failures must be filtered out of the set handed to triage."
        )

    def test_deploy_inconsistency_reported_as_build_state_not_regression(self):
        # covers: FIN-100g-4
        js = _js_text()
        assert "build-state, not regressions" in js, (
            "A build/deploy inconsistency must be reported as a build-state condition, "
            "never classified as a test regression."
        )

    def test_build_state_exclusion_is_data_driven_not_name_based(self):
        # covers: FIN-100g-4-i
        js = _js_text()
        assert "data-driven" in js and "hard-coded name" in js, (
            "FIN-100g-4-i: the build-state exclusion must be data-driven "
            "(passes-after-verified-redeploy), never keyed on a hard-coded test/helper name."
        )
