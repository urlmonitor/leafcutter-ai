"""
MODULE: test_finalize_feature_preflight_branch_detection
GOAL: Verify that finalize-feature.js pre-flight resolves branch and worktree_root
    from the epic/ticket worktree (via git worktree list --porcelain + git -C),
    not from the ambient session CWD. Regression guard for the bug observed when
    invoking /finalize-feature from a session CWD on main — which caused a false
    "must be run from a feature branch" abort even when a valid epic worktree existed.

AC: TICKET-20260707-Finalize_Preflight_Branch_Detection / AC-1

Tests run without invoking Claude Code — they validate the JS file as text
and use node --check for syntax validation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _js_text() -> str:
    return _JS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1 — JS file passes node --check (no syntax errors)
# ---------------------------------------------------------------------------


def test_finalize_feature_js_is_valid_javascript():
    """The edited file must parse without syntax errors."""
    result = subprocess.run(
        ["node", "--check", str(_JS_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"node --check failed with exit {result.returncode}:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 2 — epicArg is derived from `args`
# ---------------------------------------------------------------------------


class TestEpicArgExtraction:
    """The pre-flight must extract epicArg from the `args` global."""

    def test_epic_arg_variable_declared(self):
        """epicArg is declared from args before the pre-flight agent call."""
        js = _js_text()
        assert "const epicArg" in js, (
            "epicArg must be declared at the top of the pre-flight block"
        )

    def test_epic_arg_derives_from_args(self):
        """epicArg reads from the `args` global (not a hardcoded value)."""
        js = _js_text()
        # The declaration must reference `args` as the source.
        assert "typeof args === 'string'" in js, (
            "epicArg must guard against non-string args with typeof args === 'string'"
        )

    def test_epic_arg_trimmed(self):
        """epicArg must be trimmed to avoid leading/trailing whitespace issues."""
        js = _js_text()
        # Both occurrences: trim() on the extraction and possibly on the variable use.
        assert ".trim()" in js, (
            "epicArg extraction must call .trim() on the args string"
        )


# ---------------------------------------------------------------------------
# Test 3 — git worktree list --porcelain used for resolution
# ---------------------------------------------------------------------------


class TestWorktreeListUsed:
    """The pre-flight must use git worktree list --porcelain to resolve the
    target worktree when an epicArg is provided."""

    def test_git_worktree_list_porcelain_present(self):
        """git worktree list --porcelain must appear in the pre-flight agent prompt."""
        js = _js_text()
        assert "git worktree list --porcelain" in js, (
            "The pre-flight must run 'git worktree list --porcelain' to resolve "
            "the target worktree — not rely on the session CWD"
        )

    def test_worktree_resolution_in_preflight_phase(self):
        """The worktree list call must appear before Step 0 (in the pre-flight)."""
        js = _js_text()
        idx_worktree_list = js.find("git worktree list --porcelain")
        idx_step0 = js.find("phase('Step 0')")
        assert idx_worktree_list != -1, "git worktree list --porcelain not found"
        assert idx_step0 != -1, "phase('Step 0') not found"
        assert idx_worktree_list < idx_step0, (
            "git worktree list --porcelain must appear in the Pre-flight section, "
            "before phase('Step 0')"
        )


# ---------------------------------------------------------------------------
# Test 4 — git -C anchor used in pre-flight detection
# ---------------------------------------------------------------------------


class TestGitCAnchorInPreflight:
    """The pre-flight branch/toplevel detection must use git -C <worktree_path>
    so it reads from the resolved worktree, not the session CWD."""

    def test_git_c_anchor_in_preflight_agent_prompt(self):
        """git -C must appear in the pre-flight agent prompt string."""
        js = _js_text()
        # The pre-flight region is between phase('Pre-flight') and phase('Pre-flight 2').
        preflight_start = js.find("phase('Pre-flight')")
        preflight2_start = js.find("phase('Pre-flight 2')")
        assert preflight_start != -1, "phase('Pre-flight') marker not found"
        assert preflight2_start != -1, "phase('Pre-flight 2') marker not found"
        preflight_region = js[preflight_start:preflight2_start]
        assert "git -C" in preflight_region, (
            "The pre-flight region must use 'git -C <path>' to anchor branch "
            "and toplevel detection at the resolved worktree, not the session CWD"
        )

    def test_no_bare_git_branch_show_current_in_preflight(self):
        """The pre-flight must NOT issue a bare `git branch --show-current` without
        a -C anchor when an epicArg path is taken.

        The bare call IS allowed in the fallback path (no-arg CWD detection), so
        we verify the anchored variant is also present — meaning the fix is wired in.
        """
        js = _js_text()
        preflight_start = js.find("phase('Pre-flight')")
        preflight2_start = js.find("phase('Pre-flight 2')")
        preflight_region = js[preflight_start:preflight2_start]
        # The anchored variant must be present (the fix is active).
        assert 'git -C' in preflight_region and 'branch --show-current' in preflight_region, (
            "The pre-flight must contain both 'git -C' and 'branch --show-current', "
            "confirming the anchored detection path is implemented"
        )


# ---------------------------------------------------------------------------
# Test 5 — found === false early return with clear error
# ---------------------------------------------------------------------------


class TestNoWorktreeFoundError:
    """When no matching worktree is found, the workflow must return a clear,
    actionable error — not silently misdetect the branch as 'main'."""

    def test_found_false_early_return_present(self):
        """An early return on found === false must be present."""
        js = _js_text()
        assert "preflightInfo.found === false" in js, (
            "Pre-flight must check 'preflightInfo.found === false' and return early "
            "with a clear error when no matching worktree is found"
        )

    def test_no_worktree_error_has_actionable_message(self):
        """The error returned when no worktree is found must be actionable."""
        js = _js_text()
        # The error message must mention git worktree list so the user knows what to do.
        assert "git worktree list" in js, (
            "The no-worktree-found error must mention 'git worktree list' so the "
            "user can see all registered worktrees and retry with the correct name"
        )

    def test_no_worktree_error_action_required_field(self):
        """The early-return object must include action_required for structured routing."""
        js = _js_text()
        assert "resolve_worktree_argument" in js, (
            "The no-worktree-found error must include "
            "action_required: 'resolve_worktree_argument'"
        )


# ---------------------------------------------------------------------------
# Test 6 — main/master guard preserved but reads resolved branch
# ---------------------------------------------------------------------------


class TestMainMasterGuardPreserved:
    """The main/master guard must still exist, but must now check the BRANCH
    resolved from the worktree (not from the ambient CWD)."""

    def test_main_master_guard_present(self):
        """BRANCH === 'main' guard must still be in the pre-flight."""
        js = _js_text()
        assert 'BRANCH === "main"' in js or "BRANCH === 'main'" in js, (
            "The main/master guard must be preserved — "
            "running finalize-feature on main is still an error"
        )

    def test_branch_derived_from_preflight_info(self):
        """BRANCH must be set from preflightInfo (the resolved worktree result),
        not from a separate CWD-anchored shell call."""
        js = _js_text()
        assert "const BRANCH = (preflightInfo.branch" in js, (
            "BRANCH must be derived from preflightInfo.branch "
            "(the resolved-worktree response), not from a raw shell call"
        )

    def test_worktree_root_derived_from_preflight_info(self):
        """WORKTREE_ROOT must be set from preflightInfo (the resolved worktree result)."""
        js = _js_text()
        assert "const WORKTREE_ROOT = (preflightInfo.worktree_root" in js, (
            "WORKTREE_ROOT must be derived from preflightInfo.worktree_root "
            "(the resolved-worktree response)"
        )


# ---------------------------------------------------------------------------
# Test 7 — fallback path for no-arg invocation present
# ---------------------------------------------------------------------------


class TestNoArgFallback:
    """When no epicArg is provided, the pre-flight must fall back to CWD-based
    detection (backward-compatible with callers that pass no argument)."""

    def test_fallback_path_present(self):
        """The agent prompt must include a fallback branch for when epicArg is empty."""
        js = _js_text()
        # The ternary structure: epicArg ? <resolution path> : <fallback path>
        # Detect the fallback by looking for the CWD git branch call in the no-arg branch.
        assert "fall back to CWD-based detection" in js, (
            "The pre-flight must include a fallback to CWD-based detection "
            "when no epicArg is provided (backward compatibility)"
        )
