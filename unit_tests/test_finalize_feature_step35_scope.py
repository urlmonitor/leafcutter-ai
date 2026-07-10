"""
MODULE: test_finalize_feature_step35_scope
GOAL: Verify that step 3.5 of finalize-feature.js scopes ticket closure to the
    epic/branch being finalized (AC-1) and includes a pre-commit scope guard
    that aborts the closure commit when out-of-scope paths are staged (AC-2).

BUSINESS CONTEXT: Before the fix, step 3.5 performed a global ticket-store scan
    and produced a closure commit that flipped status on unrelated epics' tickets.
    These tests confirm the structural guards that prevent cross-epic contamination.
    The tests were designed to FAIL before the fix and PASS after, ensuring they
    serve as a regression barrier.

ARCHITECTURE: Pure structural (static-analysis) tests — read finalize-feature.js
    as text and assert the presence or absence of specific patterns. No external
    process calls, no LLM invocations, no file-system side-effects.

TICKET: tickets/00_inbox/TICKET-20260707-Finalize_Step35_CrossEpic_Closure.md
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-1: Scope-limited discovery — ticket candidates must come from git diff only
# ---------------------------------------------------------------------------


class TestScopeRestrictedDiscovery:
    """AC-1: step 3.5 must restrict ticket discovery to the branch/epic being finalized."""

    def test_scope_prefix_variable_defined(self) -> None:
        """SCOPE_PREFIX must be computed from the branch name before the closure call."""
        js = _js_text()
        assert "SCOPE_PREFIX" in js, (
            "step 3.5 must define a SCOPE_PREFIX from the branch name "
            "to restrict ticket closure to the correct epic folder"
        )

    def test_scope_prefix_epic_branch_uses_epic_folder(self) -> None:
        """For EPIC-* branches, SCOPE_PREFIX must point to tickets/00_inbox/epics/<branch>/."""
        js = _js_text()
        assert "tickets/00_inbox/epics/" in js, (
            "SCOPE_PREFIX must reference the canonical epic folder path "
            "tickets/00_inbox/epics/<branch>/"
        )

    def test_scope_prefix_derived_from_epic_branch_name(self) -> None:
        """SCOPE_PREFIX must be conditional on whether the branch starts with EPIC-."""
        js = _js_text()
        assert 'BRANCH.startsWith("EPIC-")' in js, (
            'SCOPE_PREFIX must use BRANCH.startsWith("EPIC-") to detect epic branches '
            "and set the epic folder as the scope"
        )

    def test_no_whole_store_scan_instruction(self) -> None:
        """The ambiguous 'any ticket file in the worktree that has status != done'
        phrase must be removed — it was the trigger for the global-scan bug."""
        js = _js_text()
        assert "any ticket file in the worktree that has status != done" not in js, (
            "The global-scan trigger phrase must be absent from step 3.5; "
            "its presence caused the agent to walk the entire ticket store"
        )

    def test_git_diff_used_for_ticket_discovery(self) -> None:
        """Ticket discovery must use git diff (branch-scoped) rather than a worktree walk."""
        js = _js_text()
        assert "diff --name-only origin/main HEAD" in js, (
            "step 3.5 must use 'git diff --name-only origin/main HEAD' "
            "to find branch-changed ticket files"
        )

    def test_scope_filter_applied_to_git_diff_results(self) -> None:
        """After the git diff, the result list must be filtered by SCOPE_PREFIX."""
        js = _js_text()
        assert "does NOT start with SCOPE_PREFIX" in js or "not start with SCOPE_PREFIX" in js, (
            "step 3.5 must discard git diff results that do NOT start with SCOPE_PREFIX "
            "when SCOPE_PREFIX is non-empty"
        )

    def test_no_worktree_walk_instruction(self) -> None:
        """The agent prompt must not instruct a walk of the entire ticket tree."""
        js = _js_text()
        # The old code's second instruction (not the git command itself) told the
        # agent to "include any ticket file in the worktree" — this must be gone.
        assert "any ticket file in the worktree" not in js, (
            "step 3.5 agent prompt must not mention 'any ticket file in the worktree' "
            "since that phrase triggers a global ticket-store scan"
        )


# ---------------------------------------------------------------------------
# AC-2: Pre-commit scope guard — abort if staged paths fall outside epic scope
# ---------------------------------------------------------------------------


class TestPreCommitScopeGuard:
    """AC-2: step 3.5 must verify every staged path before committing."""

    def test_scope_guard_section_in_agent_prompt(self) -> None:
        """The closure agent prompt must contain a SCOPE GUARD section."""
        js = _js_text()
        assert "SCOPE GUARD" in js, (
            "step 3.5 agent prompt must include a 'SCOPE GUARD' section "
            "that verifies staged paths before the commit runs"
        )

    def test_scope_violation_field_in_return_schema(self) -> None:
        """The REPORTING schema must declare a scope_violation field."""
        js = _js_text()
        assert '"scope_violation"' in js, (
            "step 3.5 REPORTING must include a 'scope_violation' field "
            "so the caller can detect and surface the abort"
        )

    def test_out_of_scope_paths_field_in_return_schema(self) -> None:
        """The REPORTING schema must declare an out_of_scope_paths field."""
        js = _js_text()
        assert '"out_of_scope_paths"' in js, (
            "step 3.5 REPORTING must include 'out_of_scope_paths' "
            "listing every path that triggered the scope violation"
        )

    def test_git_reset_on_scope_violation(self) -> None:
        """A scope violation must trigger git reset HEAD to unstage all changes."""
        js = _js_text()
        assert "reset HEAD" in js, (
            "step 3.5 must run 'git reset HEAD' when a scope violation is detected "
            "so no out-of-scope paths remain staged"
        )

    def test_scope_violation_surfaced_in_javascript_handler(self) -> None:
        """The JS handler after the agent call must surface scope violations via log()."""
        js = _js_text()
        assert "SCOPE VIOLATION" in js, (
            "The JS code after the closure agent call must log a 'SCOPE VIOLATION' "
            "message so the operator sees the abort in workflow output"
        )

    def test_out_of_scope_paths_logged_in_javascript_handler(self) -> None:
        """The JS handler must surface the offending paths from out_of_scope_paths."""
        js = _js_text()
        assert "out_of_scope_paths" in js and "offendingPaths" in js, (
            "The JS handler must read out_of_scope_paths and log each offending path"
        )

    def test_ac_files_explicitly_allowed_in_scope_guard(self) -> None:
        """The scope guard must allow docs/acceptance-criteria/ paths (AC closure files)."""
        js = _js_text()
        # Verify the guard's allow-list includes AC files so valid closure is not rejected.
        assert "docs/acceptance-criteria/" in js, (
            "The scope guard must explicitly allow paths under docs/acceptance-criteria/ "
            "since those are valid AC closure files produced by mark_ac_done.py"
        )


# ---------------------------------------------------------------------------
# Regression baseline: patterns that were present in the buggy version
# (these tests confirm the bug-triggering code is gone)
# ---------------------------------------------------------------------------


class TestBugRegressionBaseline:
    """Tests that the specific patterns from the buggy step 3.5 are absent.

    These tests would have PASSED on the original (buggy) code because they
    check for the absence of the bug-triggering patterns — the bug allowed
    the listed patterns to be PRESENT. After the fix, those patterns are gone,
    so these tests now FAIL on old code and PASS on new code.

    Clarification: each test below asserts the ABSENCE of the bug pattern,
    so 'test fails before fix, passes after fix' means:
      - Before fix: assertion fails (pattern IS present, assertion says it must NOT be)
      - After fix:  assertion passes (pattern is absent)
    """

    def test_global_scan_phrase_absent(self) -> None:
        """The global-scan trigger phrase must not appear in the JS file."""
        js = _js_text()
        assert "any ticket file in the worktree that has status != done" not in js

    def test_scope_guard_instruction_present(self) -> None:
        """The scope guard instruction must be present (was absent before fix)."""
        js = _js_text()
        assert "SCOPE GUARD" in js

    def test_scope_prefix_logic_present(self) -> None:
        """SCOPE_PREFIX computation must be present (was absent before fix)."""
        js = _js_text()
        assert "SCOPE_PREFIX" in js

    def test_scope_violation_handling_present(self) -> None:
        """scope_violation handling in JS must be present (was absent before fix)."""
        js = _js_text()
        assert "scope_violation" in js
