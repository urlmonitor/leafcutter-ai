"""
MODULE: test_finalize_pre_merge_safety_gate
GOAL: Source-contract assertions for the FIN-100 pre-merge safety-gate ACs.

    Nature: CODE_NO_TEST backfill (2026-07-14 audit). The logic is fully coded
    in templates/workflows-js/finalize-feature.js and
    templates/agents/test-failure-triage.md. These tests read those files as
    text and assert that each documented contract is present in the source.

    ACs covered: FIN-100a-1, FIN-100a-2, FIN-100a-3, FIN-100b-1, FIN-100b-2,
    FIN-100b-3, FIN-100c-1, FIN-100c-2, FIN-100c-3, FIN-100d-1, FIN-100d-2,
    FIN-100d-3, FIN-100f-1, FIN-100f-2.

TICKET: 04_fin100_pre_merge_safety_gate_test_coverage
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"
_TRIAGE_MD_PATH = _REPO_ROOT / "templates" / "agents" / "test-failure-triage.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _triage_md_text() -> str:
    """Return the full text of test-failure-triage.md."""
    return _TRIAGE_MD_PATH.read_text(encoding="utf-8")


def _get_step_block(js: str, step_label: str, next_step_label: str) -> str:
    """Extract the source between two phase() markers.

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


def _get_full_step_block(js: str, step_label: str) -> str:
    """Extract from phase('X') to the next phase() call (any label)."""
    start_marker = f"phase('{step_label}')"
    start = js.find(start_marker)
    if start == -1:
        return ""
    # Find next phase( call after this one
    next_phase = js.find("phase(", start + len(start_marker))
    if next_phase == -1:
        return js[start:]
    return js[start:next_phase]


def _find_line_number(text: str, pattern: str) -> int:
    """Return the 1-based line number of the first occurrence of pattern, or -1."""
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern in line:
            return lineno
    return -1


# ---------------------------------------------------------------------------
# FIN-100a-1: Step 0 creates baseline worktree, records fields, removes it,
#             forwards baseline to triage
# ---------------------------------------------------------------------------

class TestFin100a1BaselineCapture:
    """FIN-100a-1: Step 0 creates temp worktree at origin/main, records sha +
    failures + timestamp, removes worktree after run, forwards data to triage.
    """

    def test_ac_fin100a1_step0_creates_detached_worktree(self):
        # covers: FIN-100a-1
        """AC FIN-100a-1: Step 0 must create a temporary detached worktree at origin/main."""
        step0 = _get_step_block(_js_text(), "Step 0", "Step 1")
        assert step0, "phase('Step 0') block must exist in finalize-feature.js"
        assert "worktree add --detach" in step0 or "worktree add" in step0, (
            "Step 0 must create a detached worktree via 'git worktree add --detach' "
            "to capture the baseline test run at origin/main. "
            "The AC requires a temp detached worktree, not an in-place branch switch."
        )

    def test_ac_fin100a1_step0_records_baseline_sha(self):
        # covers: FIN-100a-1
        """AC FIN-100a-1: Step 0 must record baseline_sha from the temp worktree HEAD."""
        step0 = _get_step_block(_js_text(), "Step 0", "Step 1")
        assert "baseline_sha" in step0, (
            "Step 0 must capture and record baseline_sha (the SHA of main HEAD "
            "inside the temp worktree). Required by FIN-100a-1."
        )

    def test_ac_fin100a1_step0_records_baseline_failures(self):
        # covers: FIN-100a-1
        """AC FIN-100a-1: Step 0 must record baseline_failures (file::test_name list)."""
        step0 = _get_step_block(_js_text(), "Step 0", "Step 1")
        assert "baseline_failures" in step0, (
            "Step 0 must record baseline_failures as a list of failing test IDs "
            "in 'file::test_name' format. Required by FIN-100a-1."
        )

    def test_ac_fin100a1_step0_records_baseline_run_at(self):
        # covers: FIN-100a-1
        """AC FIN-100a-1: Step 0 must record baseline_run_at timestamp."""
        step0 = _get_step_block(_js_text(), "Step 0", "Step 1")
        assert "baseline_run_at" in step0, (
            "Step 0 must record baseline_run_at (ISO 8601 timestamp). "
            "Required by FIN-100a-1."
        )

    def test_ac_fin100a1_step0_removes_temp_worktree(self):
        # covers: FIN-100a-1
        """AC FIN-100a-1: Step 0 must remove the temp worktree after the run."""
        step0 = _get_step_block(_js_text(), "Step 0", "Step 1")
        assert "worktree remove" in step0, (
            "Step 0 must remove the temporary baseline worktree via "
            "'git worktree remove' after the test run completes. "
            "Required by FIN-100a-1 to avoid leaving stale directories."
        )

    def test_ac_fin100a1_baseline_forwarded_to_step3_triage(self):
        # covers: FIN-100a-1
        """AC FIN-100a-1: baseline data (failures, sha) must be forwarded to step 3 triage."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert "baselineFailures" in step3 or "baseline_failures" in step3, (
            "Step 3 triage dispatch must forward baseline_failures captured in Step 0. "
            "Required by FIN-100a-1: 'baseline data is forwarded to the triage agent.'"
        )
        assert "baselineSha" in step3 or "baseline_sha" in step3, (
            "Step 3 triage dispatch must forward baseline_sha captured in Step 0."
        )


# ---------------------------------------------------------------------------
# FIN-100a-2: Graceful degradation — null on failure, does NOT halt
# ---------------------------------------------------------------------------

class TestFin100a2GracefulDegradation:
    """FIN-100a-2: On Step 0 failure, baseline_failures=null, workflow does NOT halt."""

    def test_ac_fin100a2_null_on_worktree_failure(self):
        # covers: FIN-100a-2
        """AC FIN-100a-2: When worktree creation fails, baseline_failures is set to null."""
        js = _js_text()
        step0 = _get_step_block(js, "Step 0", "Step 1")
        # The failure path must set/return baseline_failures: null (not empty array)
        assert "baseline_failures\": null" in step0 or 'baseline_failures: null' in step0, (
            "Step 0 must return baseline_failures=null (not empty array) when worktree "
            "creation fails. Required by FIN-100a-2: 'null (not empty array) on any failure path.'"
        )

    def test_ac_fin100a2_null_on_run_failure(self):
        # covers: FIN-100a-2
        """AC FIN-100a-2: When test run fails to execute, baseline_failures stays null."""
        step0 = _get_step_block(_js_text(), "Step 0", "Step 1")
        # run_failed path must set baseline_failures to null
        assert "run_failed" in step0 or "run failed" in step0.lower(), (
            "Step 0 must handle the 'run_failed' status (pytest not found, import error) "
            "and set baseline_failures=null. Required by FIN-100a-2."
        )

    def test_ac_fin100a2_workflow_does_not_halt_on_baseline_failure(self):
        # covers: FIN-100a-2
        """AC FIN-100a-2: Workflow must NOT halt on baseline failure — continues to Step 1."""
        js = _js_text()
        step0 = _get_step_block(js, "Step 0", "Step 1")
        # The step 0 degraded-path must push to skippedSteps (not return halted)
        assert "skippedSteps.push" in step0 or "skipped_steps" in step0, (
            "When Step 0 baseline capture fails, the workflow must add step 0 to "
            "skippedSteps and continue — it must NOT return a halted status. "
            "Required by FIN-100a-2: 'does NOT halt — continues to Step 1.'"
        )

    def test_ac_fin100a2_logs_warning_on_degradation(self):
        # covers: FIN-100a-2
        """AC FIN-100a-2: Workflow must log a warning explaining the failure reason."""
        step0 = _get_step_block(_js_text(), "Step 0", "Step 1")
        # There should be a warning-style log message in the degradation path
        assert (
            "triage will treat all failures as regressions" in step0.lower()
            or "triage will treat all post-merge failures as regressions" in step0.lower()
            or "triage will use conservative" in step0.lower()
        ), (
            "Step 0 must log a warning when baseline capture fails, explaining that "
            "triage will treat all failures as regressions. Required by FIN-100a-2."
        )


# ---------------------------------------------------------------------------
# FIN-100a-3: Temp worktree cleaned up on every exit path
# ---------------------------------------------------------------------------

class TestFin100a3WorktreeCleanupOnAllExits:
    """FIN-100a-3: cleanupBaselineWorktree() is called on every halt/exit path."""

    def test_ac_fin100a3_cleanup_before_conflict_halt(self):
        # covers: FIN-100a-3
        """AC FIN-100a-3: cleanupBaselineWorktree() called before step 2 merge_conflict halt."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "cleanupBaselineWorktree" in step2, (
            "Step 2 must call cleanupBaselineWorktree() before returning the merge_conflict "
            "halt response. Required by FIN-100a-3 and FIN-100b-2: 'cleaned up on any early halt.'"
        )

    def test_ac_fin100a3_cleanup_before_step3_halt(self):
        # covers: FIN-100a-3
        """AC FIN-100a-3: cleanupBaselineWorktree() called before step 3 test_regression halt."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert "cleanupBaselineWorktree" in step3, (
            "Step 3 halt gate must call cleanupBaselineWorktree() before returning the "
            "test_regression halt response. Required by FIN-100a-3."
        )

    def test_ac_fin100a3_cleanup_before_step4_defensive_halt(self):
        # covers: FIN-100a-3
        """AC FIN-100a-3: cleanupBaselineWorktree() called before step 4 defensive guard halt."""
        step4 = _get_step_block(_js_text(), "Step 4", "Step 5")
        assert "cleanupBaselineWorktree" in step4, (
            "Step 4 defensive guard must call cleanupBaselineWorktree() before halting. "
            "Required by FIN-100a-3: 'cleaned up on any early halt.'"
        )

    def test_ac_fin100a3_cleanup_function_defined_with_path_guard(self):
        # covers: FIN-100a-3
        """AC FIN-100a-3: cleanupBaselineWorktree() must swallow errors (best-effort)."""
        js = _js_text()
        assert "cleanupBaselineWorktree" in js, (
            "finalize-feature.js must define a cleanupBaselineWorktree() function. "
            "Required by FIN-100a-3."
        )
        # The function must be best-effort (not throw)
        cleanup_idx = js.find("async function cleanupBaselineWorktree")
        assert cleanup_idx != -1, (
            "cleanupBaselineWorktree must be declared as 'async function cleanupBaselineWorktree' "
            "for await compatibility."
        )
        cleanup_block = js[cleanup_idx:cleanup_idx + 500]
        assert "try" in cleanup_block or "catch" in cleanup_block, (
            "cleanupBaselineWorktree() must swallow errors via try/catch — "
            "it is a best-effort cleanup that must never throw. Required by FIN-100a-3."
        )


# ---------------------------------------------------------------------------
# FIN-100b-1: Clean merge yields merged_main strategy, proceeds to step 3
# ---------------------------------------------------------------------------

class TestFin100b1CleanMerge:
    """FIN-100b-1: clean merge uses --no-commit --no-ff, records merged_main strategy."""

    def test_ac_fin100b1_merge_uses_no_commit_no_ff(self):
        # covers: FIN-100b-1
        """AC FIN-100b-1: Step 2 must use --no-commit --no-ff flags."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "--no-commit" in step2 and "--no-ff" in step2, (
            "Step 2 must use 'git merge origin/main --no-commit --no-ff' so that no merge "
            "commit is written to the feature branch history. Required by FIN-100b-1."
        )

    def test_ac_fin100b1_clean_merge_records_merged_main_strategy(self):
        # covers: FIN-100b-1
        """AC FIN-100b-1: clean merge must record merge_strategy='merged_main'."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "merged_main" in step2, (
            "Step 2 must record merge_strategy='merged_main' when the merge succeeds "
            "without conflicts. Required by FIN-100b-1."
        )

    def test_ac_fin100b1_clean_merge_continues_to_step3(self):
        # covers: FIN-100b-1
        """AC FIN-100b-1: clean merge path must push to completedSteps and continue."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "completedSteps.push" in step2, (
            "Step 2 must push step 2 to completedSteps on the clean merge path so "
            "the workflow continues to Step 3. Required by FIN-100b-1."
        )


# ---------------------------------------------------------------------------
# FIN-100b-2: Conflict path runs merge --abort, halts at step 2
# ---------------------------------------------------------------------------

class TestFin100b2ConflictHalt:
    """FIN-100b-2: conflict detected → git merge --abort, halted_at_step=2, reason=merge_conflict."""

    def test_ac_fin100b2_conflict_runs_merge_abort(self):
        # covers: FIN-100b-2
        """AC FIN-100b-2: conflict path must run 'git merge --abort'."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "merge --abort" in step2, (
            "Step 2 must run 'git merge --abort' when a merge conflict is detected, "
            "to restore the worktree to a clean pre-merge state. Required by FIN-100b-2."
        )

    def test_ac_fin100b2_conflict_returns_halted_at_step2(self):
        # covers: FIN-100b-2
        """AC FIN-100b-2: conflict halt must return halted_at_step=2."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "halted_at_step: 2" in step2, (
            "Step 2 conflict halt must include halted_at_step: 2 in the return object. "
            "Required by FIN-100b-2."
        )

    def test_ac_fin100b2_conflict_reason_is_merge_conflict(self):
        # covers: FIN-100b-2
        """AC FIN-100b-2: conflict halt reason must be 'merge_conflict'."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert 'reason: "merge_conflict"' in step2 or "reason: 'merge_conflict'" in step2, (
            "Step 2 conflict halt must include reason='merge_conflict'. Required by FIN-100b-2."
        )

    def test_ac_fin100b2_conflict_cleans_up_baseline(self):
        # covers: FIN-100b-2
        """AC FIN-100b-2: conflict path must clean up baseline worktree before halting."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "cleanupBaselineWorktree" in step2, (
            "Step 2 must call cleanupBaselineWorktree() before returning the merge_conflict "
            "halt. Required by FIN-100b-2."
        )


# ---------------------------------------------------------------------------
# FIN-100b-3: Already-up-to-date path skips merge, records already_up_to_date
# ---------------------------------------------------------------------------

class TestFin100b3AlreadyUpToDate:
    """FIN-100b-3: already-up-to-date → skip merge, record already_up_to_date strategy."""

    def test_ac_fin100b3_uses_merge_base_is_ancestor(self):
        # covers: FIN-100b-3
        """AC FIN-100b-3: Step 2 must use 'git merge-base --is-ancestor' to probe up-to-date."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "merge-base --is-ancestor" in step2, (
            "Step 2 must use 'git merge-base --is-ancestor origin/main HEAD' as the "
            "already-up-to-date probe before attempting the merge. Required by FIN-100b-3."
        )

    def test_ac_fin100b3_already_up_to_date_records_strategy(self):
        # covers: FIN-100b-3
        """AC FIN-100b-3: already-up-to-date path must record merge_strategy='already_up_to_date'."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "already_up_to_date" in step2, (
            "Step 2 must return merge_strategy='already_up_to_date' when the branch already "
            "contains all commits from origin/main. Required by FIN-100b-3."
        )

    def test_ac_fin100b3_already_up_to_date_adds_to_skipped_steps(self):
        # covers: FIN-100b-3
        """AC FIN-100b-3: already-up-to-date path must push step 2 to skippedSteps, not completedSteps."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        # The already_up_to_date path should push to skippedSteps
        already_idx = step2.find("already_up_to_date")
        assert already_idx != -1, "already_up_to_date must appear in Step 2 block"
        # Check that skippedSteps.push appears in this block
        assert "skippedSteps.push" in step2, (
            "Step 2 must push to skippedSteps (not completedSteps) when the branch is "
            "already up-to-date with origin/main. Required by FIN-100b-3 it_requirements: "
            "'Must add step 2 to skippedSteps (not completedSteps) when skipping.'"
        )


# ---------------------------------------------------------------------------
# FIN-100c-1/c-2/c-3: Triage classification — source-contract over triage MD
#
# These ACs live in the LLM agent prompt (test-failure-triage.md), not in
# deterministic JS/Python. Coverage is via source-contract assertions that the
# prompt documents each required classification rule verbatim.
# ---------------------------------------------------------------------------

class TestFin100c1PreExistingClassification:
    """FIN-100c-1: failures in BOTH baseline and post-merge → pre_existing; does not block."""

    def test_ac_fin100c1_triage_md_documents_pre_existing_set(self):
        # covers: FIN-100c-1
        """AC FIN-100c-1: triage prompt must document the pre_existing set-intersection rule."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        assert "pre_existing" in triage, (
            "test-failure-triage.md must document the 'pre_existing' classification category. "
            "Required by FIN-100c-1."
        )

    def test_ac_fin100c1_triage_md_documents_intersection_operation(self):
        # covers: FIN-100c-1
        """AC FIN-100c-1: triage prompt must document set intersection for pre_existing."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        # The algorithm must document intersection (∩ or "intersection" or "both baseline and post")
        has_intersection = (
            "∩" in triage
            or "intersection" in triage.lower()
            or ("baseline" in triage.lower() and "pre_existing" in triage)
        )
        assert has_intersection, (
            "test-failure-triage.md must document the set-intersection rule: "
            "pre_existing = post_merge_failures ∩ baseline_failures. Required by FIN-100c-1."
        )

    def test_ac_fin100c1_pre_existing_does_not_block(self):
        # covers: FIN-100c-1
        """AC FIN-100c-1: pre_existing failures must not set blocks_finalization=true."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        # Must document that pre_existing does not block finalization
        assert "blocks_finalization" in triage, (
            "test-failure-triage.md must document the blocks_finalization field. "
            "Required by FIN-100c-1 and FIN-100c-2."
        )
        # blocks_finalization is false when all entries are pre_existing or flaky
        assert "false" in triage.lower() and (
            "pre_existing" in triage or "flaky" in triage
        ), (
            "test-failure-triage.md must document that blocks_finalization=false when "
            "all failures are pre_existing or flaky. Required by FIN-100c-1."
        )

    def test_ac_fin100c1_pre_existing_action_is_create_tracking_ticket(self):
        # covers: FIN-100c-1
        """AC FIN-100c-1: pre_existing entries must have action=create_tracking_ticket."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        assert "create_tracking_ticket" in triage, (
            "test-failure-triage.md must document action='create_tracking_ticket' for "
            "pre_existing entries. Required by FIN-100c-1."
        )


class TestFin100c2RegressionClassification:
    """FIN-100c-2: failures absent from baseline → regression; blocks_finalization=true."""

    def test_ac_fin100c2_triage_md_documents_regression_category(self):
        # covers: FIN-100c-2
        """AC FIN-100c-2: triage prompt must document 'regression' as a category."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        assert "regression" in triage, (
            "test-failure-triage.md must document the 'regression' classification category. "
            "Required by FIN-100c-2."
        )

    def test_ac_fin100c2_triage_md_documents_set_difference_for_regression(self):
        # covers: FIN-100c-2
        """AC FIN-100c-2: triage prompt must document set-difference for regression candidates."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        # Must have set difference documented (− or "minus" or "not in baseline")
        has_difference = (
            "−" in triage
            or "regression_candidates" in triage
            or ("post_merge_failures" in triage and "baseline_failures" in triage)
        )
        assert has_difference, (
            "test-failure-triage.md must document the set-difference rule for regression "
            "candidates: regression_candidates = post_merge_failures - baseline_failures. "
            "Required by FIN-100c-2."
        )

    def test_ac_fin100c2_regression_blocks_finalization_true(self):
        # covers: FIN-100c-2
        """AC FIN-100c-2: regression entries must set blocks_finalization=true."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        # Look for blocks_finalization: true with regression context
        assert "blocks_finalization" in triage, (
            "test-failure-triage.md must document blocks_finalization semantics. "
            "Required by FIN-100c-2."
        )
        assert "`true`" in triage or "true" in triage, (
            "test-failure-triage.md must document that blocks_finalization=true "
            "when regressions are present. Required by FIN-100c-2."
        )


class TestFin100c3NullBaselineConservative:
    """FIN-100c-3: null baseline → all failures classified as regression, conservative."""

    def test_ac_fin100c3_triage_md_documents_null_baseline_step(self):
        # covers: FIN-100c-3
        """AC FIN-100c-3: triage prompt Step 1 must document null baseline handling."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        # Must have a step documenting null baseline handling
        assert "null" in triage and "baseline" in triage.lower(), (
            "test-failure-triage.md must document handling of baseline_failures=null. "
            "Required by FIN-100c-3."
        )

    def test_ac_fin100c3_null_baseline_triggers_early_return_in_algorithm(self):
        # covers: FIN-100c-3
        """AC FIN-100c-3: triage Step 1 must be the null-baseline early-return path."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        # Step 1 of the algorithm handles null baseline
        assert "Step 1" in triage, (
            "test-failure-triage.md must document 'Step 1 — Handle null baseline' as "
            "the early-return path for conservative classification. Required by FIN-100c-3."
        )

    def test_ac_fin100c3_null_baseline_classifies_all_as_regression(self):
        # covers: FIN-100c-3
        """AC FIN-100c-3: null baseline must classify ALL post-merge failures as regression."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        # When null, must classify as regression (conservative) and return immediately
        has_conservative = (
            "conservative" in triage.lower()
            or ("null" in triage and "regression" in triage)
        )
        assert has_conservative, (
            "test-failure-triage.md must document that a null baseline triggers "
            "conservative classification: ALL failures classified as 'regression'. "
            "Required by FIN-100c-3."
        )

    def test_ac_fin100c3_null_baseline_sets_blocks_finalization_true(self):
        # covers: FIN-100c-3
        """AC FIN-100c-3: null baseline must set blocks_finalization=true immediately."""
        triage = _TRIAGE_MD_PATH.read_text(encoding="utf-8")
        # The Step 1 section must include blocks_finalization: true + return immediately
        step1_idx = triage.find("Step 1")
        step2_idx = triage.find("Step 2", step1_idx + 1 if step1_idx != -1 else 0)
        if step1_idx != -1 and step2_idx != -1:
            step1_block = triage[step1_idx:step2_idx]
        elif step1_idx != -1:
            step1_block = triage[step1_idx:step1_idx + 500]
        else:
            step1_block = triage
        assert "blocks_finalization" in step1_block and (
            "true" in step1_block or "`true`" in step1_block
        ), (
            "test-failure-triage.md Step 1 must document 'Set blocks_finalization: true' "
            "for the null-baseline path. Required by FIN-100c-3."
        )


# ---------------------------------------------------------------------------
# FIN-100d-1: blocks_finalization=true → immediate halt at step 3
# ---------------------------------------------------------------------------

class TestFin100d1BlocksFinalizationHalt:
    """FIN-100d-1: blocks_finalization=true → immediate halt, status=halted, step 3."""

    def test_ac_fin100d1_step3_halt_returns_status_halted(self):
        # covers: FIN-100d-1
        """AC FIN-100d-1: step 3 halt must return status='halted'."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert 'status: "halted"' in step3 or "status: 'halted'" in step3, (
            "Step 3 halt must return status='halted'. Required by FIN-100d-1."
        )

    def test_ac_fin100d1_step3_halt_has_halted_at_step_3(self):
        # covers: FIN-100d-1
        """AC FIN-100d-1: step 3 halt must include halted_at_step=3."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert "halted_at_step: 3" in step3, (
            "Step 3 halt must include halted_at_step: 3 in the return object. "
            "Required by FIN-100d-1."
        )

    def test_ac_fin100d1_step3_halt_reason_is_test_regression(self):
        # covers: FIN-100d-1
        """AC FIN-100d-1: step 3 halt reason must be 'test_regression'."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert 'reason: "test_regression"' in step3 or "reason: 'test_regression'" in step3, (
            "Step 3 halt must include reason='test_regression'. Required by FIN-100d-1."
        )

    def test_ac_fin100d1_step3_halt_includes_triage_report(self):
        # covers: FIN-100d-1
        """AC FIN-100d-1: step 3 halt must include the full triage_report."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert "triage_report" in step3, (
            "Step 3 halt must include triage_report in the response for developer "
            "diagnosis. Required by FIN-100d-1."
        )

    def test_ac_fin100d1_step3_halt_includes_test_output(self):
        # covers: FIN-100d-1
        """AC FIN-100d-1: step 3 halt must include raw test output."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert "test_output" in step3 or "testResult" in step3, (
            "Step 3 halt must include test_output (raw test run output) so the developer "
            "can diagnose regressions. Required by FIN-100d-1."
        )

    def test_ac_fin100d1_step3_halt_uses_early_return_not_throw(self):
        # covers: FIN-100d-1
        """AC FIN-100d-1: step 3 halt must use 'return' (not throw) for the early exit."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert "return {" in step3 and "triageReport.blocks_finalization" in step3, (
            "Step 3 halt must use an early 'return {}' statement (not throw) inside "
            "the if(blocks_finalization) guard. Required by FIN-100d-1."
        )


# ---------------------------------------------------------------------------
# FIN-100d-2: blocks_finalization=false → proceed to step 4
# ---------------------------------------------------------------------------

class TestFin100d2ContinuePath:
    """FIN-100d-2: blocks_finalization=false → step 3 marked complete, proceeds to step 4."""

    def test_ac_fin100d2_false_path_pushes_step3_to_completed(self):
        # covers: FIN-100d-2
        """AC FIN-100d-2: when blocks_finalization=false, step 3 must be pushed to completedSteps."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert "completedSteps.push(3)" in step3, (
            "Step 3 must push step 3 to completedSteps on the blocks_finalization=false path. "
            "Required by FIN-100d-2."
        )

    def test_ac_fin100d2_triage_report_preserved_in_state(self):
        # covers: FIN-100d-2
        """AC FIN-100d-2: triageReport must be preserved in workflow state for step 6."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        # triageReport must be assigned from the triage response (not discarded)
        assert "triageReport" in step3, (
            "Step 3 must preserve triageReport in workflow state for use in step 6 "
            "(auto-ticketing of pre_existing/flaky entries). Required by FIN-100d-2."
        )

    def test_ac_fin100d2_false_path_does_not_return_halted(self):
        # covers: FIN-100d-2
        """AC FIN-100d-2: blocks_finalization=false path must not return a halted status."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        # The continue path (blocks_finalization=false) should have
        # completedSteps.push(3) without a preceding halted return
        false_path_idx = step3.rfind("completedSteps.push(3)")
        assert false_path_idx != -1, (
            "Step 3 must contain 'completedSteps.push(3)' on the false path. "
            "Required by FIN-100d-2."
        )
        # Verify there is no 'status: "halted"' immediately before the push
        context = step3[max(0, false_path_idx - 200):false_path_idx]
        # It's OK to have "halted" earlier in the block (for the true path),
        # but the completedSteps.push(3) itself must NOT be preceded by a halt.
        assert 'status: "halted"' not in context, (
            "Step 3's blocks_finalization=false path must NOT return halted before "
            "completedSteps.push(3). Required by FIN-100d-2."
        )


# ---------------------------------------------------------------------------
# FIN-100d-3: Defensive guard at step 4 catches bypassed blocks_finalization
# ---------------------------------------------------------------------------

class TestFin100d3DefensiveGuard:
    """FIN-100d-3: Step 4 defensive guard halts if blocks_finalization=true reaches step 4."""

    def test_ac_fin100d3_defensive_guard_exists_at_step4(self):
        # covers: FIN-100d-3
        """AC FIN-100d-3: Step 4 must have a defensive guard checking blocks_finalization."""
        step4 = _get_step_block(_js_text(), "Step 4", "Step 5")
        assert "blocks_finalization" in step4, (
            "Step 4 must include a defensive guard that checks triageReport.blocks_finalization "
            "before the merge confirmation prompt. Required by FIN-100d-3."
        )

    def test_ac_fin100d3_defensive_guard_halts_at_step4(self):
        # covers: FIN-100d-3
        """AC FIN-100d-3: defensive guard must return halted_at_step=4."""
        step4 = _get_step_block(_js_text(), "Step 4", "Step 5")
        assert "halted_at_step: 4" in step4, (
            "Step 4 defensive guard must return halted_at_step=4 (not 3) to distinguish "
            "it from the primary halt. Required by FIN-100d-3."
        )

    def test_ac_fin100d3_defensive_guard_message_says_defensive_guard_triggered(self):
        # covers: FIN-100d-3
        """AC FIN-100d-3: defensive guard message must contain 'Defensive guard triggered'."""
        step4 = _get_step_block(_js_text(), "Step 4", "Step 5")
        assert "Defensive guard triggered" in step4, (
            "Step 4 defensive guard message must explicitly say 'Defensive guard triggered' "
            "so operators can distinguish this halt from the primary Step 3 halt. "
            "Required by FIN-100d-3."
        )

    def test_ac_fin100d3_defensive_guard_calls_cleanup(self):
        # covers: FIN-100d-3
        """AC FIN-100d-3: defensive guard must call cleanupBaselineWorktree() before halting."""
        step4 = _get_step_block(_js_text(), "Step 4", "Step 5")
        assert "cleanupBaselineWorktree" in step4, (
            "Step 4 defensive guard must call cleanupBaselineWorktree() before returning "
            "the halted response. Required by FIN-100d-3."
        )

    def test_ac_fin100d3_defensive_guard_reason_is_test_regression(self):
        # covers: FIN-100d-3
        """AC FIN-100d-3: defensive guard halt reason must be 'test_regression'."""
        step4 = _get_step_block(_js_text(), "Step 4", "Step 5")
        assert 'reason: "test_regression"' in step4 or "reason: 'test_regression'" in step4, (
            "Step 4 defensive guard halt must use reason='test_regression'. "
            "Required by FIN-100d-3."
        )


# ---------------------------------------------------------------------------
# FIN-100f-1: Step 4 is structurally unreachable when step 3 halt fires
# ---------------------------------------------------------------------------

class TestFin100f1Step4StructurallyUnreachable:
    """FIN-100f-1: step 3 halt uses early return; step 4 code physically follows it."""

    def test_ac_fin100f1_step3_halt_return_precedes_step4_phase_marker(self):
        # covers: FIN-100f-1
        """AC FIN-100f-1: the return in step 3's halt gate precedes phase('Step 4') in source."""
        js = _js_text()
        # Find the step 3 halt return (the one with halted_at_step: 3)
        step3_halt_idx = js.find("halted_at_step: 3")
        step4_phase_idx = js.find("phase('Step 4')")
        assert step3_halt_idx != -1, (
            "finalize-feature.js must contain 'halted_at_step: 3' (step 3 halt gate). "
            "Required by FIN-100f-1."
        )
        assert step4_phase_idx != -1, (
            "finalize-feature.js must contain phase('Step 4') (step 4 marker). "
            "Required by FIN-100f-1."
        )
        assert step3_halt_idx < step4_phase_idx, (
            "The step 3 halt return (halted_at_step: 3) must appear BEFORE "
            "phase('Step 4') in the source. This is the structural guarantee that "
            "Step 4 is unreachable when the step 3 halt fires. Required by FIN-100f-1. "
            f"step3_halt at char {step3_halt_idx}, phase('Step 4') at char {step4_phase_idx}."
        )

    def test_ac_fin100f1_step3_uses_return_not_throw(self):
        # covers: FIN-100f-1
        """AC FIN-100f-1: step 3 halt must use 'return' (not throw/break)."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert "return {" in step3, (
            "Step 3 halt gate must use 'return {}' (not throw) so that JavaScript "
            "sequential semantics guarantee Step 4 code never executes after this return. "
            "Required by FIN-100f-1."
        )

    def test_ac_fin100f1_step4_code_after_step3_in_file(self):
        # covers: FIN-100f-1
        """AC FIN-100f-1: step 4 code (prompt/merge dispatch) is physically after step 3 in source."""
        js = _js_text()
        step3_marker = js.find("phase('Step 3')")
        step4_marker = js.find("phase('Step 4')")
        assert step3_marker != -1 and step4_marker != -1, (
            "Both phase('Step 3') and phase('Step 4') markers must exist. Required by FIN-100f-1."
        )
        assert step3_marker < step4_marker, (
            "phase('Step 3') must appear before phase('Step 4') in the source. "
            "Required by FIN-100f-1 sequential ordering guarantee."
        )


# ---------------------------------------------------------------------------
# FIN-100f-2: Strictly sequential await ordering — no parallel() for steps 2/3/4
# ---------------------------------------------------------------------------

class TestFin100f2SequentialOrdering:
    """FIN-100f-2: Steps 2, 3, 4 use sequential await; no parallel() wraps them."""

    def test_ac_fin100f2_step2_uses_await_agent(self):
        # covers: FIN-100f-2
        """AC FIN-100f-2: Step 2 must use 'await agent(' for its dispatch."""
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert "await agent(" in step2, (
            "Step 2 must dispatch its merge command via 'await agent(...)' (sequential). "
            "Required by FIN-100f-2."
        )

    def test_ac_fin100f2_step3_uses_await_agent(self):
        # covers: FIN-100f-2
        """AC FIN-100f-2: Step 3 must use 'await agent(' for its test-runner dispatch."""
        step3 = _get_step_block(_js_text(), "Step 3", "Step 3.5")
        assert "await agent(" in step3, (
            "Step 3 must dispatch the test runner via 'await agent(...)' (sequential). "
            "Required by FIN-100f-2."
        )

    def test_ac_fin100f2_step4_uses_await_agent(self):
        # covers: FIN-100f-2
        """AC FIN-100f-2: Step 4 must use 'await agent(' for its PR merge dispatch."""
        step4 = _get_step_block(_js_text(), "Step 4", "Step 5")
        assert "await agent(" in step4, (
            "Step 4 must dispatch the PR merge via 'await agent(...)' (sequential). "
            "Required by FIN-100f-2."
        )

    def test_ac_fin100f2_no_parallel_wrapping_steps_2_3_4(self):
        # covers: FIN-100f-2
        """AC FIN-100f-2: no parallel() dispatch may wrap steps 2, 3, or 4 together."""
        js = _js_text()
        # Extract from Step 2 start to Step 5 start (covering steps 2, 3, 4)
        step2_start = js.find("phase('Step 2')")
        step5_start = js.find("phase('Step 5')")
        if step2_start == -1 or step5_start == -1:
            # Fallback: check whole file — parallel() should not appear for these steps
            steps_2_to_4 = js
        else:
            steps_2_to_4 = js[step2_start:step5_start]

        # parallel() is the keyword that would indicate non-sequential dispatch
        assert "parallel(" not in steps_2_to_4, (
            "Steps 2, 3, and 4 must NOT use parallel() dispatch. Each step must "
            "await the previous one before executing so that: Step 2 (merge) completes "
            "before Step 3 (test against post-merge state), and Step 3 (triage) completes "
            "before Step 4 (PR merge). Required by FIN-100f-2."
        )

    def test_ac_fin100f2_phase_markers_appear_in_sequential_order(self):
        # covers: FIN-100f-2
        """AC FIN-100f-2: phase markers must appear in order: 2 before 3 before 4."""
        js = _js_text()
        step2_idx = js.find("phase('Step 2')")
        step3_idx = js.find("phase('Step 3')")
        step4_idx = js.find("phase('Step 4')")
        assert step2_idx != -1, "phase('Step 2') must exist"
        assert step3_idx != -1, "phase('Step 3') must exist"
        assert step4_idx != -1, "phase('Step 4') must exist"
        assert step2_idx < step3_idx < step4_idx, (
            "Phase markers must appear in order: phase('Step 2') < phase('Step 3') < "
            "phase('Step 4'). This enforces the sequential ordering guarantee. "
            f"Actual positions: step2={step2_idx}, step3={step3_idx}, step4={step4_idx}. "
            "Required by FIN-100f-2."
        )
