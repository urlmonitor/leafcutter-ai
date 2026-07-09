"""
SOURCE-ASSERTION TESTS — finalize-feature.js fail-closed sync-check contract.

The workflow JS in templates/workflows-js/ is executed by the leafcutter
Workflow engine, not by Node.js directly, so standard JS test runners cannot
run it under pytest. These tests parse finalize-feature.js as text and assert
that the safety-critical pre-Step-4 sync-check block contains the required
fail-closed invariants. This is the established pattern used in
test_finalize_feature_preflight.py and test_finalize_feature_step6a.py.

SAFETY CONTRACT LOCKED BY THESE TESTS:
  Any indeterminate, unknown, or unverifiable sync state must HALT the
  finalizer before `gh pr merge` runs. There must be NO fail-open path
  (no unknown/unrecognised status falls through to Step 4). SHA verification
  in JS is the final trust anchor — the agent's self-reported status word
  alone is insufficient. This prevents silently merging a stale PR head.

TICKET: TICKET-20260708-Finalize_Push_Before_Merge
ACs:
  - AC-1: Pre-Step-4 sync check that halts (fail-closed) or pushes when local
          branch HEAD differs from origin.
  - AC-2: Command doc uses plain-string argument (not object form) to
          /finalize-feature.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"
_CMD_PATH = _REPO_ROOT / "templates" / "commands" / "finalize-feature.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _cmd_text() -> str:
    """Return the full text of the finalize-feature command doc."""
    return _CMD_PATH.read_text(encoding="utf-8")


def _pre_step4_region(js: str) -> str:
    """Text from phase('Step 3.5') to phase('Step 4') — broad pre-Step-4 window.

    Used for tests that were written before the sync-check comment existed as a
    stable landmark. New tests should prefer _sync_check_region() for precision.
    """
    step4_pos = js.find("phase('Step 4')")
    step35_pos = js.rfind("phase('Step 3.5')", 0, step4_pos)
    if step35_pos == -1 or step4_pos == -1:
        return ""
    return js[step35_pos:step4_pos]


def _sync_check_region(js: str) -> str:
    """Text from the 'Pre-Step-4 Sync Check' header comment to phase('Step 4').

    This is the tighter region covering only the sync-check logic itself,
    not the Step 3.5 closure logic that precedes it in the same broad window.
    Used for precise safety-contract assertions where false positives from
    earlier code (e.g. the git-add 2>/dev/null lines in Step 3.5) must not
    pollute the assertion.
    """
    start_marker = "Pre-Step-4 Sync Check"
    end_marker = "phase('Step 4')"
    start = js.find(start_marker)
    end = js.find(end_marker)
    if start == -1 or end == -1 or start >= end:
        return ""
    return js[start:end]


# ---------------------------------------------------------------------------
# AC-1: Pre-Step-4 sync check — fail-closed safety contract
# ---------------------------------------------------------------------------

class TestPreStep4SyncCheck:
    """AC-1: finalize-feature.js must compare local HEAD to origin/<branch>
    before Step 4, push when local is ahead, and HALT CLOSED on any
    indeterminate, unverifiable, or diverged state.
    """

    # -- Existence / basic structure (original tests, kept for baseline) ------

    def test_sync_check_exists_before_step4(self):
        """A sync check must appear between Step 3.5 and Step 4.

        The check compares local branch HEAD to origin and pushes when the
        local copy is ahead. Without it, local commits after the last
        pull-request phase are silently excluded from the PR merge.
        """
        # covers: UNKNOWN
        js = _js_text()
        pre_step4_region = _pre_step4_region(js)
        assert pre_step4_region, "phase('Step 3.5') or phase('Step 4') not found in JS"
        has_push_check = (
            "push" in pre_step4_region
            or "sync" in pre_step4_region.lower()
            or "ahead" in pre_step4_region
        )
        assert has_push_check, (
            "finalize-feature.js must include a push/sync check between "
            "Step 3.5 and Step 4 (before gh pr merge). "
            "Without it, local commits are silently dropped from main. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_sync_check_dispatches_status_checker(self):
        """The sync check must use the status-checker agent type.

        The sync check runs as a status-checker agent turn (read-only probe
        + conditional push), consistent with the pre-flight pattern in the
        rest of finalize-feature.js.
        """
        # covers: UNKNOWN
        js = _js_text()
        pre_step4_region = _pre_step4_region(js)
        assert "status-checker" in pre_step4_region, (
            "The pre-Step-4 sync check must dispatch a status-checker agent "
            "to compare local vs origin branch HEAD. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_push_failed_halt_path_exists(self):
        """finalize-feature.js must HALT when the push fails.

        A push failure should not be silently swallowed. The user must be
        informed that local commits could not reach origin, so the PR was NOT
        merged and no work is lost.
        """
        # covers: UNKNOWN
        js = _js_text()
        pre_step4_region = _pre_step4_region(js)
        has_push_failed_halt = (
            "push_failed" in pre_step4_region
            or "push_local_commits" in pre_step4_region
        )
        assert has_push_failed_halt, (
            "finalize-feature.js must halt with action_required: push_local_commits "
            "(or equivalent) when the pre-Step-4 push fails. "
            "The HALT message must clarify the PR was NOT merged. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_sync_check_uses_fetch_before_compare(self):
        """The sync check must fetch origin before comparing SHAs.

        Without a fetch, the local tracking ref (origin/<branch>) may be
        stale. Comparing a stale origin ref to local HEAD can falsely report
        up-to-date when origin actually has different commits.
        """
        # covers: UNKNOWN
        js = _js_text()
        pre_step4_region = _pre_step4_region(js)
        assert "fetch" in pre_step4_region, (
            "The pre-Step-4 sync check must include a git fetch before "
            "comparing local to origin SHA. Without it, stale tracking refs "
            "can produce a false up-to-date result. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_up_to_date_status_is_handled(self):
        """The sync check must handle the up_to_date status explicitly.

        When local and origin are in sync the 'up_to_date' branch still
        performs SHA verification (H-2) before allowing Step 4 to proceed.
        """
        # covers: UNKNOWN
        js = _js_text()
        pre_step4_region = _pre_step4_region(js)
        assert "up_to_date" in pre_step4_region, (
            "The pre-Step-4 sync check must handle the 'up_to_date' case "
            "explicitly (with SHA verification). "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    # -- H-1: Fail-closed — indeterminate state must never fall through -------

    def test_h1_indeterminate_parse_halts_with_correct_keys(self):
        """H-1: malformed/null parse result halts with sync_check_indeterminate.

        When safeParseJSON returns malformed=true or value is null/undefined,
        the finalizer must halt immediately with reason: sync_check_indeterminate
        and action_required: verify_and_push. Failing to halt here would allow
        a completely unparseable agent response to fall through to gh pr merge.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert 'reason: "sync_check_indeterminate"' in region, (
            "H-1: malformed-parse halt must emit reason: \"sync_check_indeterminate\". "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )
        assert 'action_required: "verify_and_push"' in region, (
            "H-1: malformed-parse halt must emit action_required: \"verify_and_push\". "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_h1_no_fail_open_substring(self):
        """H-1: the sync-check region must not contain the substring 'fail-open'.

        A 'fail-open' comment or code path would indicate that an unknown or
        indeterminate sync state is allowed to fall through to Step 4. The
        contract after the hardening is strictly fail-closed.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert "fail-open" not in region, (
            "H-1: the sync-check region must NOT contain the substring 'fail-open'. "
            "The presence of 'fail-open' indicates old code that lets an unknown "
            "status continue to gh pr merge. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_h1_known_sync_statuses_gate_is_a_set(self):
        """H-1: KNOWN_SYNC_STATUSES must exist as a Set for the explicit status gate.

        Any sync status not in this Set is treated as indeterminate → HALT.
        This gate prevents a future new status string (e.g. from an agent
        prompt change) from silently falling through to the merge step.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert "KNOWN_SYNC_STATUSES" in region, (
            "H-1: KNOWN_SYNC_STATUSES variable must exist in the sync-check region. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )
        assert "new Set(" in region, (
            "H-1: KNOWN_SYNC_STATUSES must be declared as a JavaScript Set "
            "(new Set([...])) so membership checks are O(1) and explicit. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_h1_unknown_status_gate_halts(self):
        """H-1: a status not in KNOWN_SYNC_STATUSES must cause a halt.

        The gate on KNOWN_SYNC_STATUSES.has(syncStatus) must branch to a
        halt with reason: sync_check_indeterminate when the status is not
        recognised. Checking that both the gate conditional and the halt
        are present in the same region locks this structural invariant.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        # Gate: !KNOWN_SYNC_STATUSES.has(syncStatus) → halt
        assert "KNOWN_SYNC_STATUSES.has(syncStatus)" in region, (
            "H-1: the sync-check region must contain KNOWN_SYNC_STATUSES.has(syncStatus) "
            "as the explicit gate. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )
        # The halt on unknown status also emits sync_check_indeterminate —
        # confirm it appears at least twice (once for malformed parse, once for unknown gate).
        count = region.count('reason: "sync_check_indeterminate"')
        assert count >= 2, (
            f"H-1: reason: \"sync_check_indeterminate\" should appear at least twice "
            f"in the sync-check region (malformed-parse halt + unknown-status gate halt) "
            f"— found {count}. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    # -- H-2: SHA verification in JS — agent status word not trusted alone ----

    def test_h2_pushed_path_compares_local_and_origin_sha(self):
        """H-2: the 'pushed' path must compare local_sha to origin_sha in JS.

        After a push is reported as successful, the JS layer must re-read both
        SHAs and compare them. This prevents a buggy or dishonest agent from
        claiming 'pushed' when the remote ref was not actually updated.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert "local_sha" in region, (
            "H-2: the pushed path must extract local_sha from syncCheckInfo. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )
        assert "origin_sha" in region, (
            "H-2: the pushed path must extract origin_sha from syncCheckInfo. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_h2_push_not_confirmed_halt_exists(self):
        """H-2: SHA mismatch on the 'pushed' path halts with reason: push_not_confirmed.

        When the agent reports 'pushed' but local_sha !== origin_sha, the JS
        layer must halt with reason: push_not_confirmed. This halt must appear
        between the 'pushed' status handling and phase('Step 4').
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert 'reason: "push_not_confirmed"' in region, (
            "H-2: the sync-check region must contain reason: \"push_not_confirmed\" "
            "for the SHA-mismatch halt on the pushed path. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_h2_up_to_date_path_also_sha_verified(self):
        """H-2: the 'up_to_date' path also verifies SHAs; halts as indeterminate on mismatch.

        Trusting 'up_to_date' without checking SHAs would allow a buggy agent
        to let a stale or wrong head proceed. The up_to_date branch must
        perform the same local_sha vs origin_sha comparison and halt with
        sync_check_indeterminate if they disagree.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        # sync_check_indeterminate must appear at least 3 times:
        #   1. malformed parse halt
        #   2. unknown-status gate halt
        #   3. up_to_date SHA-mismatch halt
        count = region.count('reason: "sync_check_indeterminate"')
        assert count >= 3, (
            f"H-2: reason: \"sync_check_indeterminate\" should appear at least 3 times "
            f"(malformed-parse, unknown-status gate, up_to_date SHA-mismatch) "
            f"— found {count}. The up_to_date path must also halt when SHAs disagree. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    # -- M-1: Divergence detection — both directions, pull --rebase guidance ---

    def test_m1_ahead_count_uses_correct_git_range(self):
        """M-1: the agent prompt must compute ahead_count using origin/BRANCH..HEAD.

        This range counts commits in local HEAD not yet in origin — it is the
        authoritative measure of 'how far ahead' the local branch is. Without
        it the agent would have to guess, which is unreliable.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert 'origin/${BRANCH}..HEAD' in region, (
            "M-1: the agent prompt in the sync-check region must include the git range "
            "'origin/${BRANCH}..HEAD' to count ahead commits. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_m1_behind_count_uses_correct_git_range(self):
        """M-1: the agent prompt must compute behind_count using HEAD..origin/BRANCH.

        This range counts commits on origin that are not in local HEAD. Without
        it the diverged case (ahead AND behind) would be misclassified as
        push-only, causing gh push to be rejected by the remote.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert 'HEAD..origin/${BRANCH}' in region, (
            "M-1: the agent prompt in the sync-check region must include the git range "
            "'HEAD..origin/${BRANCH}' to count behind commits. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_m1_diverged_halts_with_reason_branch_diverged(self):
        """M-1: the diverged status must halt with reason: branch_diverged.

        A diverged branch (both ahead and behind, or strictly behind) cannot
        be pushed directly — the user must integrate origin changes first.
        Halting with a named reason allows external tooling to key on it.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert 'reason: "branch_diverged"' in region, (
            "M-1: the diverged halt must emit reason: \"branch_diverged\". "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_m1_diverged_recommends_pull_rebase_not_plain_push(self):
        """M-1: the diverged halt message must recommend 'pull --rebase', not a plain push.

        A plain push on a diverged branch would either be rejected (non-fast-
        forward) or — if forced — would silently overwrite origin commits.
        The halt message must steer the user toward 'pull --rebase' explicitly.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert "pull --rebase" in region, (
            "M-1: the diverged halt message must contain 'pull --rebase' as the "
            "recommended remediation. A plain 'git push' is dangerous on a diverged "
            "branch and must not be the sole guidance. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    # -- M-2: Fetch failure must not be swallowed ------------------------------

    def test_m2_fetch_not_silenced_with_dev_null_true(self):
        """M-2: the fetch command in the agent prompt must not be silenced with '|| true'.

        Appending '2>/dev/null || true' to the fetch line would hide fetch
        errors and cause the sync check to proceed on stale tracking refs.
        This test asserts the exact silencing pattern is absent from the
        sync-check-specific region (which excludes the Step 3.5 git-add lines
        that legitimately use '|| true' for non-critical operations).
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert "2>/dev/null || true" not in region, (
            "M-2: the sync-check region must NOT contain '2>/dev/null || true'. "
            "That pattern on the fetch line would silently swallow fetch errors, "
            "leaving tracking refs stale and the sync state unknown. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_m2_fetch_failed_status_halts_with_named_reason(self):
        """M-2: fetch_failed status must halt with reason: fetch_failed.

        When the fetch exits non-zero the agent returns { status: 'fetch_failed' }.
        The JS layer must catch this and halt — not skip the sync check and
        proceed with stale tracking refs.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        assert "fetch_failed" in region, (
            "M-2: 'fetch_failed' must appear in the sync-check region. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )
        assert 'reason: "fetch_failed"' in region, (
            "M-2: the fetch_failed halt must emit reason: \"fetch_failed\". "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    # -- Structural invariants -------------------------------------------------

    def test_structural_step4_marker_is_after_sync_check_comment(self):
        """Structural: phase('Step 4') must appear AFTER the sync-check comment.

        If phase('Step 4') is rearranged to precede the sync-check comment,
        the gh pr merge call could run before the safety gate — a catastrophic
        regression. This test locks the ordering.
        """
        # covers: UNKNOWN
        js = _js_text()
        sync_comment_pos = js.find("Pre-Step-4 Sync Check")
        step4_pos = js.find("phase('Step 4')")
        assert sync_comment_pos != -1, (
            "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        )
        assert step4_pos != -1, (
            "phase('Step 4') not found in finalize-feature.js"
        )
        assert sync_comment_pos < step4_pos, (
            "Structural: the 'Pre-Step-4 Sync Check' comment must appear BEFORE "
            "phase('Step 4') in finalize-feature.js. "
            "If Step 4 precedes the sync check, gh pr merge can run on a stale head. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_structural_cleanup_called_in_multiple_halt_branches(self):
        """Structural: cleanupBaselineWorktree() must be called before every halt.

        Each early-return path in the sync check must call
        cleanupBaselineWorktree() before returning so the baseline worktree
        is not left dangling. Asserting a count >= 5 locks the requirement
        that the distinct halt branches (malformed, unknown-status, fetch_failed,
        push_failed, diverged, pushed-SHA-mismatch, up_to_date-SHA-mismatch)
        each include cleanup.
        """
        # covers: UNKNOWN
        region = _sync_check_region(_js_text())
        assert region, "'Pre-Step-4 Sync Check' comment not found in finalize-feature.js"
        count = region.count("cleanupBaselineWorktree()")
        assert count >= 5, (
            f"Structural: cleanupBaselineWorktree() must appear in at least 5 halt "
            f"branches within the sync-check region — found {count}. "
            "Each early-return path must clean up the baseline worktree before halting. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )


# ---------------------------------------------------------------------------
# AC-2: Command doc uses plain-string argument
# ---------------------------------------------------------------------------

class TestCommandDocStringArg:
    """AC-2: The /finalize-feature command doc must document the plain-string
    invocation, not the object form that silently fails CWD detection.
    """

    def test_command_doc_uses_string_not_object(self):
        """The command doc must pass $ARGUMENTS as a string, not { branch: $ARGUMENTS }.

        The script checks typeof args === 'string'. Passing an object form
        silently falls through to CWD-based detection, which is usually wrong
        when /finalize-feature is run from a different working directory.
        """
        # covers: UNKNOWN
        cmd = _cmd_text()
        # The bad form: Workflow("finalize-feature", { branch: ... })
        has_bad_object_form = (
            '{ branch:' in cmd
            or '{ branch :' in cmd
            or '"branch"' in cmd
        )
        assert not has_bad_object_form, (
            "The /finalize-feature command doc must NOT instruct callers to "
            "pass { branch: $ARGUMENTS } — the script checks typeof args === 'string' "
            "and the object form silently falls through to CWD detection. "
            "Use the plain-string form: Workflow(\"finalize-feature\", $ARGUMENTS). "
            "AC-2: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_command_doc_contains_workflow_invocation(self):
        """The command doc must still contain a Workflow() invocation example.

        Fixing AC-2 should update the invocation, not remove it entirely.
        """
        # covers: UNKNOWN
        cmd = _cmd_text()
        has_workflow_call = (
            'Workflow("finalize-feature"' in cmd
            or "Workflow('finalize-feature'" in cmd
        )
        assert has_workflow_call, (
            "The /finalize-feature command doc must contain a Workflow() "
            "invocation example after the AC-2 fix. "
            "AC-2: TICKET-20260708-Finalize_Push_Before_Merge"
        )
