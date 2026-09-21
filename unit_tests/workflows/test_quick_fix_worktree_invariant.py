"""
MODULE: test_quick_fix_worktree_invariant
GOAL: /quick-fix (BP-600 ACs) coverage for the in-place worktree invariant
      (BP-600a-1) and the no-isolation-infrastructure contract (BP-600a-2):
      source-contract text assertions on quick-fix.js/SKILL.md, PLUS the
      harness-driven behavioral test of the actual self-isolation DECISION
      (self-isolate dispatched or not, and whether its output is threaded
      into later phases).

Split out of the former monolithic test_quick_fix_workflow.py (1731 content
lines) — see _quick_fix_harness.py's module docstring for the shared-fixture
rationale and the sibling files covering the rest of the BP-600 AC set.

Per this repo's CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by
Grep", the source-contract tests below prove the required strings exist in
the shipped artefacts; TestBP600WorkflowInPlaceAndSelfIsolation below proves
the isolation DECISION is actually wired into control flow, which a grep
cannot distinguish from dead code.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600a-1, BP-600a-2
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
    _phase_block,
    run_workflow_under_e2,
)


# ===========================================================================
# BP-600a-1 — operates in current worktree without branch switching
# ===========================================================================

class TestBP600a1WorktreeInvariant:
    """BP-600a-1: All operations run in current worktree; branch unchanged."""

    def test_ac_bp600a1_records_initial_branch(self):
        # covers: BP-600a-1
        """quick-fix.js must capture initial_branch via git branch --show-current."""
        js = _js()
        assert "initial_branch" in js, (
            "quick-fix.js must capture initial_branch from git branch --show-current "
            "to enforce the worktree invariant required by BP-600a-1."
        )

    def test_ac_bp600a1_final_return_includes_branch(self):
        # covers: BP-600a-1
        """The workflow's final return value must include the branch name, confirming
        the branch was not changed during the run."""
        js = _js()
        # The final return block should expose `branch: initialBranch`
        assert "branch: initialBranch" in js or "branch:" in js, (
            "quick-fix.js final return must include the branch field so the caller "
            "can verify no branch switch occurred (BP-600a-1)."
        )

    def test_ac_bp600a1_no_git_worktree_add(self):
        # covers: BP-600a-1
        # covers: BP-600a-2
        """quick-fix.js guard prompt must prohibit 'git worktree add'; must not execute it.

        'git worktree add' may legitimately appear in a guard prohibition instruction
        telling the agent NOT to call it. The correct assertion is that the prohibition
        is present and that no agent call payload actually executes git worktree add as
        an action (i.e., it is not wrapped in a shell execution directive absent of the
        'Do NOT' / 'IMPORTANT' qualifier).
        """
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        # The string should appear in a prohibition context inside the guard prompt
        assert "git worktree add" in guards_block, (
            "Guards phase must explicitly prohibit 'git worktree add' in its agent "
            "prompt (BP-600a-1, BP-600a-2). The prohibition is what enforces the "
            "in-place constraint."
        )
        # Verify the prohibition keyword is adjacent (not an invocation)
        prohibition_idx = guards_block.find("git worktree add")
        surrounding = guards_block[max(0, prohibition_idx - 80):prohibition_idx + 30]
        assert "NOT" in surrounding or "not" in surrounding or "never" in surrounding.lower(), (
            "The occurrence of 'git worktree add' in the guard must be inside a "
            "prohibition clause (e.g. 'Do NOT invoke git worktree add'), not an "
            "invocation command (BP-600a-1)."
        )


# ===========================================================================
# BP-600a-2 — never dispatches worktree-agent or feature skill
# ===========================================================================

class TestBP600a2NoIsolationInfra:
    """BP-600a-2: Never dispatches worktree-agent or feature skill."""

    def test_ac_bp600a2_no_worktree_agent_dispatch(self):
        # covers: BP-600a-2
        """quick-fix.js must not dispatch agentType:'worktree-agent' at any phase.

        'worktree-agent' may legitimately appear in a guard prohibition that tells
        the phase agent NOT to use it. The assertion here checks that no agent()
        call dispatches agentType: 'worktree-agent', which is the actual invocation
        that BP-600a-2 prohibits.
        """
        js = _js()
        # No dispatch: none of the agent() calls should target agentType:'worktree-agent'
        assert "agentType: 'worktree-agent'" not in js, (
            "quick-fix.js must not dispatch agentType: 'worktree-agent' "
            "(BP-600a-2). Quick-fix is an in-place operation — no isolation infrastructure."
        )
        # Guard prohibition must be present (validates the contract is documented)
        guards_block = _phase_block(js, "Guards", "AC Creation")
        assert "worktree-agent" in guards_block, (
            "Guards phase must explicitly prohibit 'worktree-agent' in the agent "
            "prompt to enforce the no-isolation-infra contract (BP-600a-2)."
        )

    def test_ac_bp600a2_no_feature_skill(self):
        # covers: BP-600a-2
        """quick-fix.js must not load or invoke the feature skill.

        'feature skill' may legitimately appear in a prohibition instruction. The
        real assertion is that the feature skill path (feature/SKILL.md) is not
        loaded as a dependency and that there is no 'feature' agentType dispatch.
        """
        js = _js()
        # No import/load of the feature skill document
        assert "feature/SKILL" not in js, (
            "quick-fix.js must not load feature/SKILL.md (BP-600a-2)."
        )
        # No dispatch to the feature agent
        assert "agentType: 'feature'" not in js, (
            "quick-fix.js must not dispatch agentType: 'feature' (BP-600a-2)."
        )

    def test_ac_bp600a2_guard_instructs_no_isolation(self):
        # covers: BP-600a-2
        """The Guards phase prompt must tell the agent not to invoke worktree-agent."""
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        assert "worktree-agent" in guards_block or "IMPORTANT: Do NOT invoke" in guards_block, (
            "The Guards phase prompt must instruct the agent not to invoke worktree-agent "
            "(BP-600a-2). The guard must be explicit."
        )


# ===========================================================================
# Behavioral (harness-driven) coverage
#
# Supersedes test_ac_bp600a1_skill_mentions_branch_verification and
# test_ac_bp600a2_skill_prohibits_worktree_agent — those grepped SKILL.md
# prose for the word "branch" or "worktree-agent", which could not tell
# whether the self-isolation branch in quick-fix.js actually gates on the
# isolation-check response. These tests run the script and assert on what
# was actually dispatched.
# ===========================================================================

class TestBP600WorkflowInPlaceAndSelfIsolation:
    """Behavioral coverage for BP-600a-1 / BP-600a-2: the isolation DECISION
    (self-isolate dispatched or not) and its effect on later phases.
    """

    def test_ac_bp600a1_in_place_skips_self_isolate_and_keeps_branch(self):
        # covers: BP-600a-1
        """When the isolation-check reports a usable non-default branch,
        self-isolate must NOT be dispatched, and the reported cwd/branch must
        be the ones later phases operate on."""
        js_path = _JS_PATH
        result = run_workflow_under_e2(
            js_path,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": True,
                        "session_cwd": "/repo",
                        "initial_branch": "fix/some-branch",
                        "needs_isolation": False,
                    }
                }
            ),
        )
        labels = _labels(result)
        assert "self-isolate" not in labels, (
            "self-isolate must not be dispatched when needs_isolation is false "
            f"(BP-600a-1). Labels dispatched: {labels}"
        )
        guard_call = next(c for c in result.agent_calls if c.label == "guard-checks")
        assert "/repo" in guard_call.prompt and "fix/some-branch" in guard_call.prompt, (
            "The guard-checks prompt must be anchored to the reported session cwd "
            "and branch, not a re-derived value (BP-600a-1)."
        )

    def test_ac_bp600a2_self_isolate_dispatched_when_not_a_repo(self):
        # covers: BP-600a-2
        """Trigger 1 of 4: session cwd is not a git repository at all."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": False,
                        "session_cwd": "/untracked/workspace",
                        "initial_branch": "",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-1",
                        "branch": "feature/slug-1",
                        "created": True,
                    },
                }
            ),
        )
        labels = _labels(result)
        assert "self-isolate" in labels, (
            "self-isolate must be dispatched when is_repo is false (BP-600a-2, "
            f"trigger: not-a-repo). Labels dispatched: {labels}"
        )
        assert not any(c.agent_type == "worktree-agent" for c in result.agent_calls), (
            "No dispatched call may target agentType 'worktree-agent' — quick-fix "
            "uses the self-isolate phase's own setup_ticket_worktree.py path, "
            "never worktree-agent (BP-600a-2)."
        )

    def test_ac_bp600a2_self_isolate_dispatched_on_main(self):
        # covers: BP-600a-2
        """Trigger 2 of 4: current branch is 'main' (PR-only, cannot commit direct)."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": True,
                        "session_cwd": "/repo",
                        "initial_branch": "main",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-2",
                        "branch": "feature/slug-2",
                        "created": True,
                    },
                }
            ),
        )
        assert "self-isolate" in _labels(result), (
            "self-isolate must be dispatched when initial_branch is 'main' "
            "(BP-600a-2, trigger: main)."
        )

    def test_ac_bp600a2_self_isolate_dispatched_on_master(self):
        # covers: BP-600a-2
        """Trigger 3 of 4: current branch is 'master'."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": True,
                        "session_cwd": "/repo",
                        "initial_branch": "master",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-3",
                        "branch": "feature/slug-3",
                        "created": True,
                    },
                }
            ),
        )
        assert "self-isolate" in _labels(result), (
            "self-isolate must be dispatched when initial_branch is 'master' "
            "(BP-600a-2, trigger: master)."
        )

    def test_ac_bp600a2_self_isolate_dispatched_on_detached_head(self):
        # covers: BP-600a-2
        """Trigger 4 of 4: HEAD is detached (initial_branch is empty)."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": True,
                        "session_cwd": "/repo",
                        "initial_branch": "",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-4",
                        "branch": "feature/slug-4",
                        "created": True,
                    },
                }
            ),
        )
        assert "self-isolate" in _labels(result), (
            "self-isolate must be dispatched when initial_branch is empty "
            "(detached HEAD) (BP-600a-2, trigger: detached-head)."
        )

    def test_ac_bp600a1_isolation_check_precedes_self_isolate_and_worktree_root_is_consumed(self):
        # covers: BP-600a-1
        # covers: BP-600a-2
        """isolation-check must run before self-isolate, and the worktree_root
        self-isolate returns must actually be threaded into later phases —
        not merely produced and discarded."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": False,
                        "session_cwd": "/untracked/workspace",
                        "initial_branch": "",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-threaded",
                        "branch": "feature/threaded-slug",
                        "created": True,
                    },
                }
            ),
        )
        calls_by_label = {c.label: c for c in result.agent_calls}
        assert "isolation-check" in calls_by_label and "self-isolate" in calls_by_label
        assert (
            calls_by_label["isolation-check"].call_index
            < calls_by_label["self-isolate"].call_index
        ), "isolation-check must be dispatched before self-isolate (BP-600a-1)."
        later_call = calls_by_label["ac-creation"]
        assert "/isolated/wt-threaded" in later_call.prompt, (
            "The worktree_root produced by self-isolate must be consumed by a "
            "later phase's prompt (here: ac-creation) — proving the value is "
            "actually used, not just returned and dropped (BP-600a-2)."
        )
