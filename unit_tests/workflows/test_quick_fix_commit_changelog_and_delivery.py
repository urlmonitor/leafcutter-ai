"""
MODULE: test_quick_fix_commit_changelog_and_delivery
GOAL: /quick-fix (BP-600 ACs) coverage for the delivery tail of the
      workflow: dispatching the commit agent rather than calling `git
      commit` directly (BP-600d-3), pushing to the branch remote and
      surfacing a pr_url in the final result (BP-600d-4), the no-PR case
      that still completes with status: ok (BP-600d-4-i), PLUS
      harness-driven behavioral proof that (a) the commit prompt actually
      carries BOTH the parent and child AC paths — not just declares it will
      — so the covered_by back-link lands in the same commit, (b) the
      Changelog phase runs before push and a changelog-authoring failure
      halts the run before a PR is opened, and (c) all three PR outcomes
      (opened / declined / already-exists) are threaded correctly into the
      terminal payload.

Split out of the former monolithic test_quick_fix_workflow.py (1731 content
lines) — see _quick_fix_harness.py's module docstring for the shared-fixture
rationale.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600d-3, BP-600d-4, BP-600d-4-i
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/workflows/ must be on sys.path so the flat sibling import below
# resolves — this package has __init__.py, so pytest's rootdir insertion
# does not add it automatically (mirrors the unit_tests/ insertion pattern
# _quick_fix_harness.py itself uses for _workflow_engine_harness).
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _quick_fix_harness import (  # noqa: E402
    _JS_PATH,
    _full_success_responses,
    _js,
    _labels,
    _skill,
    run_workflow_under_e2,
)


# ===========================================================================
# BP-600d-3 — dispatches commit agent (not git commit directly)
# ===========================================================================

class TestBP600d3CommitAgentDispatch:
    """BP-600d-3: Dispatches commit agent; never git commit directly."""

    def test_ac_bp600d3_no_direct_git_commit(self):
        # covers: BP-600d-3
        """quick-fix.js must never call 'git commit' directly."""
        js = _js()
        # 'git commit' as a shell command (not as part of a comment or string about
        # the commit agent) should not appear
        assert "git commit" not in js, (
            "quick-fix.js must not call 'git commit' directly — must dispatch the "
            "commit agent (BP-600d-3)."
        )

    def test_ac_bp600d3_skill_prohibits_direct_git_commit(self):
        # covers: BP-600d-3
        """SKILL.md must state to dispatch the commit agent, not call git commit."""
        skill = _skill()
        assert (
            "commit agent" in skill
            and ("not call" in skill or "never call" in skill or "Do not" in skill)
        ), (
            "SKILL.md must explicitly state to dispatch the commit agent and never "
            "call git commit directly (BP-600d-3)."
        )


# ===========================================================================
# BP-600d-4 — pushes to branch remote; updates PR; closes ticket lifecycle
# ===========================================================================

class TestBP600d4PushAndClose:
    """BP-600d-4: Pushes to origin; checks for existing PR; closes ticket lifecycle."""

    def test_ac_bp600d4_result_includes_pr_url(self):
        # covers: BP-600d-4
        """The workflow's final return must include pr_url."""
        js = _js()
        assert "pr_url" in js, (
            "quick-fix.js must include pr_url in return value (BP-600d-4)."
        )


# ===========================================================================
# BP-600d-4-i — no PR: pushes but does not create one; exact message
# ===========================================================================

class TestBP600d4iNoPRCase:
    """BP-600d-4-i: No PR case — pushes; does not create a PR; reports exact message."""

    def test_ac_bp600d4i_push_schema_has_pr_url_field(self):
        # covers: BP-600d-4-i
        """PUSH_SCHEMA must include pr_url as an optional field."""
        js = _js()
        # Check that PUSH_SCHEMA has pr_url
        push_schema_idx = js.find("PUSH_SCHEMA")
        push_schema_end = js.find("}", push_schema_idx) + 100
        push_schema_block = js[push_schema_idx:push_schema_end] if push_schema_idx >= 0 else ""
        assert "pr_url" in push_schema_block, (
            "PUSH_SCHEMA must include pr_url field so both PR-present and no-PR paths "
            "are represented (BP-600d-4-i)."
        )


# ===========================================================================
# Behavioral (harness-driven) coverage — BP-600d-3 data threading
#
# Supersedes test_ac_bp600d3_dispatches_commit_agent,
# test_ac_bp600d3_commit_message_references_ac_id, and
# test_ac_bp600a3i_commit_stages_only_quick_fix_files — all three grepped
# the Commit prompt for a substring ('commit', 'ac_id', 'Do not stage any
# other files') that says nothing about whether the actual parent_ac_path
# VALUE returned by the AC-creation phase reaches the commit prompt. This
# test threads a fake parent_ac_path through ac-creation and asserts it is
# literally present in the commit call's prompt — proving consumption, not
# just declaration.
# ===========================================================================

class TestBP600WorkflowCommitDataThreading:
    """The commit phase must stage BOTH the child AC and its parent (the
    covered_by back-link), not just the child.
    """

    def test_ac_bp600d3_commit_prompt_includes_parent_and_child_ac_paths(self):
        # covers: BP-600d-3
        # covers: BP-600a-3-i
        """The commit prompt must include both parent_ac_path (the back-link
        target) and ac_path (the new child) — proving the parent is staged
        alongside the child, not just the child."""
        result = run_workflow_under_e2(_JS_PATH, label_responses=_full_success_responses())
        commit_call = next(c for c in result.agent_calls if c.label == "commit")
        assert (
            "docs/acceptance-criteria/build-pipeline/bp-900/BP-900.yaml"
            in commit_call.prompt
        ), (
            "The commit prompt must include the PARENT AC path so the "
            "covered_by back-link is staged in the same commit (BP-600d-3)."
        )
        assert (
            "docs/acceptance-criteria/build-pipeline/bp-900/BP-9001.yaml"
            in commit_call.prompt
        ), "The commit prompt must include the new child AC path (BP-600d-3)."
        assert "BP-9001" in commit_call.prompt, (
            "The commit prompt must reference the ac_id produced by AC Creation "
            "so the commit message can cite it (BP-600d-3)."
        )


# ===========================================================================
# Behavioral (harness-driven) coverage — Changelog phase (new since the old
# test suite was written): it must run before Close/push, and a changelog
# authoring failure must halt the run rather than push a branch that will
# fail the required 'Changelog entry present' CI check.
# ===========================================================================

class TestBP600WorkflowChangelogBeforePush:
    """The Changelog phase must run before push-and-pr, and its failure halts."""

    def test_ac_bp600d4_changelog_runs_before_push(self):
        # covers: BP-600d-4
        """Changelog phases must be dispatched, in order, before push-and-pr."""
        result = run_workflow_under_e2(_JS_PATH, label_responses=_full_success_responses())
        labels = _labels(result)
        for required in ("commit", "changelog-author", "commit/changelog", "push-and-pr"):
            assert required in labels, f"Expected '{required}' to be dispatched. Got: {labels}"
        assert labels.index("changelog-author") < labels.index("push-and-pr"), (
            "changelog-author must be dispatched before push-and-pr (BP-600d-4)."
        )
        assert labels.index("commit/changelog") < labels.index("push-and-pr"), (
            "The changelog entry must be committed before push-and-pr (BP-600d-4)."
        )

    def test_ac_bp600d4_changelog_authoring_failure_halts_before_push(self):
        # covers: BP-600d-4
        """A blocked changelog-author response must halt the run — push-and-pr
        must never be dispatched — so a /quick-fix PR is never opened without
        the changelog entry the required CI check demands."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "changelog-author": {
                        "status": "blocked",
                        "message": "changelog script failed",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "changelog_missing"
        assert "push-and-pr" not in _labels(result), (
            "push-and-pr must not be dispatched when the changelog entry was "
            "not authored (BP-600d-4)."
        )


# ===========================================================================
# Behavioral (harness-driven) coverage — BP-600d-4 / BP-600d-4-i's PR outcomes
#
# Supersedes test_ac_bp600d4_pushes_to_origin,
# test_ac_bp600d4_checks_for_existing_pr,
# test_ac_bp600d4_skill_step_6_push_then_pr_check,
# test_ac_bp600d4i_no_gh_pr_create, and
# test_ac_bp600d4i_skill_includes_no_pr_message.
#
# IMPORTANT — contradicts the old AC text this rewrite superseded:
# test_ac_bp600d4i_no_gh_pr_create asserted 'gh pr create' must NEVER
# appear in quick-fix.js. That is no longer true: quick-fix.js now
# dispatches a confirmation-gated 'push-and-pr' phase whose prompt
# (Phase 7.4 / SKILL.md Step 7.4) explicitly instructs `gh pr create` on
# user confirmation — opening a PR is now a first-class, if
# confirmation-gated, part of the workflow (see the SKILL.md
# "Isolation is conditional" rewrite and the module docstring in
# quick-fix.js). The code's real behavior wins over the old brief here:
# these tests assert the actual (PR-creating, confirmation-gated) contract
# instead of the retired (never-creates-a-PR) one.
# ===========================================================================

class TestBP600WorkflowPrResult:
    """PR-opened, PR-declined, and existing-PR outcomes all thread correctly
    into the terminal payload.
    """

    def test_ac_bp600d4_pr_opened_case_final_result_carries_pr_url(self):
        # covers: BP-600d-4
        """When push-and-pr reports a newly opened PR, the terminal payload
        must carry that URL — proving the response value was consumed into
        the final result, not just returned and dropped."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "push-and-pr": {
                        "status": "ok",
                        "branch": "fix/some-branch",
                        "pr_url": "https://github.com/org/repo/pull/42",
                        "pr_opened": True,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "ok"
        assert result.result.get("pr_url") == "https://github.com/org/repo/pull/42"

    def test_ac_bp600d4i_no_pr_case_final_result_has_empty_pr_url_but_ok_status(self):
        # covers: BP-600d-4-i
        """When the user declines to open a PR (pr_opened: false, pr_url:
        ''), the run must still complete with status: ok — pushing without a
        PR is a valid terminal state, not a blocker — and the terminal
        payload's pr_url must be empty, not a stale value from an earlier
        phase."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "push-and-pr": {
                        "status": "ok",
                        "branch": "fix/some-branch",
                        "pr_url": "",
                        "pr_opened": False,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "ok"
        assert result.result.get("pr_url") == ""

    def test_ac_bp600d4_existing_pr_case_final_result_carries_existing_url(self):
        # covers: BP-600d-4
        """When push-and-pr detects an existing PR for the branch
        (pr_opened: false but pr_url set), the terminal payload must carry
        THAT url — proving the 'gh pr list --head' detection path (not just
        the 'gh pr create' path) is threaded into the final result."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "push-and-pr": {
                        "status": "ok",
                        "branch": "fix/some-branch",
                        "pr_url": "https://github.com/org/repo/pull/7",
                        "pr_opened": False,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "ok"
        assert result.result.get("pr_url") == "https://github.com/org/repo/pull/7"
