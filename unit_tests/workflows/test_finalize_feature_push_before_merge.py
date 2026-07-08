"""
MODULE: test_finalize_feature_push_before_merge
GOAL: Verify that finalize-feature.js includes a pre-Step-4 sync check that
    compares the local branch HEAD against origin and pushes (or halts) before
    invoking gh pr merge. Without this check, local commits made after the last
    ticket's pull-request phase are silently dropped from main.

    Tests parse finalize-feature.js as text, mirroring the pattern in
    test_finalize_feature_preflight.py and test_finalize_feature_step6a.py.

TICKET: TICKET-20260708-Finalize_Push_Before_Merge
ACs:
  - AC-1: Pre-Step-4 sync check that pushes or halts when local is ahead of origin
  - AC-2: Command doc uses plain-string argument (checked in test_command_doc_string_arg)

DECISION HISTORY
----------------
2026-07-08: Initial tests written as part of the ticket-supervisor drive.
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
# AC-1: Pre-Step-4 sync check — push or halt when local is ahead of origin
# ---------------------------------------------------------------------------

class TestPreStep4SyncCheck:
    """AC-1: finalize-feature.js must compare local HEAD to origin/<branch>
    before Step 4 and push (or halt) when local is ahead.
    """

    def test_sync_check_exists_before_step4(self):
        """A sync check must appear between Step 3.5 and Step 4.

        The check compares local branch HEAD to origin and pushes when the
        local copy is ahead. Without it, local commits after the last
        pull-request phase are silently excluded from the PR merge.
        """
        js = _js_text()
        # Find the region between the end of Step 3.5 block and Step 4
        step35_end = js.find("phase('Step 4')")
        step35_start = js.rfind("phase('Step 3.5')", 0, step35_end)
        pre_step4_region = js[step35_start:step35_end]

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
        js = _js_text()
        step35_end = js.find("phase('Step 4')")
        step35_start = js.rfind("phase('Step 3.5')", 0, step35_end)
        pre_step4_region = js[step35_start:step35_end]

        has_status_checker = "status-checker" in pre_step4_region
        assert has_status_checker, (
            "The pre-Step-4 sync check must dispatch a status-checker agent "
            "to compare local vs origin branch HEAD. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_push_failed_halt_path_exists(self):
        """finalize-feature.js must HALT with action_required: push_local_commits
        when the push fails.

        A push failure should not be silently swallowed — the user must
        be informed that local commits could not reach origin, so the PR
        was NOT merged and no work is lost.
        """
        js = _js_text()
        step35_end = js.find("phase('Step 4')")
        step35_start = js.rfind("phase('Step 3.5')", 0, step35_end)
        pre_step4_region = js[step35_start:step35_end]

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
        js = _js_text()
        step35_end = js.find("phase('Step 4')")
        step35_start = js.rfind("phase('Step 3.5')", 0, step35_end)
        pre_step4_region = js[step35_start:step35_end]

        has_fetch = "fetch" in pre_step4_region
        assert has_fetch, (
            "The pre-Step-4 sync check must include a git fetch before "
            "comparing local to origin SHA. Without it, stale tracking refs "
            "can produce a false up-to-date result. "
            "AC-1: TICKET-20260708-Finalize_Push_Before_Merge"
        )

    def test_up_to_date_path_does_not_halt(self):
        """When local and origin are in sync, finalize must NOT halt.

        The up-to-date path should log and proceed (no return / halt).
        Halting when nothing needs to be pushed would break normal finalize runs.
        """
        js = _js_text()
        step35_end = js.find("phase('Step 4')")
        step35_start = js.rfind("phase('Step 3.5')", 0, step35_end)
        pre_step4_region = js[step35_start:step35_end]

        assert "up_to_date" in pre_step4_region, (
            "The pre-Step-4 sync check must handle the 'up_to_date' case "
            "by logging and proceeding (not halting). "
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
        cmd = _cmd_text()
        has_workflow_call = 'Workflow("finalize-feature"' in cmd or "Workflow('finalize-feature'" in cmd
        assert has_workflow_call, (
            "The /finalize-feature command doc must contain a Workflow() "
            "invocation example after the AC-2 fix. "
            "AC-2: TICKET-20260708-Finalize_Push_Before_Merge"
        )
