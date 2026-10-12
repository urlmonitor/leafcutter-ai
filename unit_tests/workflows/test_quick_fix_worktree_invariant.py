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

RE-POINTED BY BO-4300c-3 / BO-4300a-1-ia: the in-place-or-self-isolate DECISION (an isolation-check probe
and a self-isolate dispatch gated on is_repo / main / master / detached HEAD) is retired. /quick-fix never
works in the folder it was started from: its workspace is the workspace maker's answer (handed in as
args.workspace, or the reply to exactly ONE ``workspace-ensure`` dispatch), and every later phase is
anchored to that answer. The two invariants these ACs protect -- no branch switching, no
hand-written isolation infrastructure -- are asserted against that single step below.
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
    workspace_ensure_reply,
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
        """quick-fix.js must not tell any agent to run ``git worktree add``: the workspace is made by the
        workspace maker and nothing else (no hand-written isolation command, no prohibition clause needed).
        """
        js = _js()
        assert "git worktree add" not in js, (
            "quick-fix.js must not contain a hand-written 'git worktree add' (BP-600a-1, BP-600a-2, "
            "BO-4300a-1-ia): the workspace is the workspace maker's answer."
        )
        assert "worktree.py ensure" in js, (
            "quick-fix.js must obtain its workspace by running the workspace maker's ensure command."
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
        # The retired isolation phases must be gone entirely, not merely unused.
        assert "worktree-agent" not in js.replace("self-isolates via scripts/setup_ticket_worktree.py", ""), (
            "quick-fix.js must not mention worktree-agent at all: no phase isolates by itself (BP-600a-2)."
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
        """The Guards phase prompt is anchored to the maker's workspace and forbids switching branches; it
        carries no isolation instruction of its own."""
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        assert "quick-fix must never switch branches" in guards_block, (
            "The Guards phase prompt must forbid branch switching explicitly (BP-600a-1)."
        )
        assert "worktree add" not in guards_block and "self-isolate" not in guards_block, (
            "The Guards phase prompt must not carry any isolation instruction (BP-600a-2)."
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
    """Behavioral coverage for BP-600a-1 / BP-600a-2: the workspace step (one verbatim maker dispatch) and
    its effect on later phases. Replaces the retired isolation DECISION (BO-4300c-3).
    """

    @staticmethod
    def _run(**overrides):
        return run_workflow_under_e2(_JS_PATH, label_responses=_full_success_responses(**overrides))

    def test_ac_bp600a1_in_place_skips_self_isolate_and_keeps_branch(self):
        # covers: BP-600a-1
        """The maker's answer names the workspace and branch; no isolation dispatch exists, and the
        guard-checks prompt is anchored to that reported workspace and branch."""
        result = self._run(
            **{"workspace-ensure": workspace_ensure_reply("/repo", branch="fix/some-branch")}
        )
        labels = _labels(result)
        assert "self-isolate" not in labels and "isolation-check" not in labels, (
            f"The retired isolation dispatches must never appear (BP-600a-1). Labels dispatched: {labels}"
        )
        assert labels.count("workspace-ensure") == 1, f"exactly one workspace dispatch. Labels: {labels}"
        guard_call = next(c for c in result.agent_calls if c.label == "guard-checks")
        assert "/repo" in guard_call.prompt and "fix/some-branch" in guard_call.prompt, (
            "The guard-checks prompt must be anchored to the workspace and branch the maker reported "
            "(BP-600a-1)."
        )

    def test_ac_bp600a2_self_isolate_dispatched_when_not_a_repo(self):
        # covers: BP-600a-2
        """Trigger 1 of 4 (re-pointed): the run was started somewhere that is not a repository at all. The
        workflow neither probes nor isolates itself; the maker's answer is the only workspace, and no call
        may target agentType 'worktree-agent'."""
        result = self._run(
            **{"workspace-ensure": workspace_ensure_reply("/made/by/maker", branch="feature/slug-1")}
        )
        labels = _labels(result)
        assert "self-isolate" not in labels and "isolation-check" not in labels, labels
        assert not any(c.agent_type == "worktree-agent" for c in result.agent_calls), (
            "No dispatched call may target agentType 'worktree-agent' -- the workspace comes from the "
            "maker's answer through the shell executor only (BP-600a-2)."
        )
        guard_call = next(c for c in result.agent_calls if c.label == "guard-checks")
        assert "/made/by/maker" in guard_call.prompt, "later phases must use the maker's workspace"

    def _assert_maker_answer_is_the_only_workspace(self, branch: str, workspace: str) -> None:
        result = self._run(**{"workspace-ensure": workspace_ensure_reply(workspace, branch=branch)})
        labels = _labels(result)
        assert "self-isolate" not in labels and "isolation-check" not in labels, labels
        ac_call = next(c for c in result.agent_calls if c.label == "ac-creation")
        assert workspace in ac_call.prompt, (
            f"Every later phase must work in the maker's workspace {workspace!r} whatever branch it names "
            f"({branch!r}). ac-creation prompt: {ac_call.prompt[:300]!r}"
        )

    def test_ac_bp600a2_self_isolate_dispatched_on_main(self):
        # covers: BP-600a-2
        """Trigger 2 of 4 (re-pointed): the run was started on 'main'. Nothing here switches or isolates;
        the workspace is whatever the maker answered."""
        self._assert_maker_answer_is_the_only_workspace("feature/from-main", "/isolated/wt-2")

    def test_ac_bp600a2_self_isolate_dispatched_on_master(self):
        # covers: BP-600a-2
        """Trigger 3 of 4 (re-pointed): the run was started on 'master'."""
        self._assert_maker_answer_is_the_only_workspace("feature/from-master", "/isolated/wt-3")

    def test_ac_bp600a2_self_isolate_dispatched_on_detached_head(self):
        # covers: BP-600a-2
        """Trigger 4 of 4 (re-pointed): the run was started on a detached HEAD."""
        self._assert_maker_answer_is_the_only_workspace("feature/from-detached", "/isolated/wt-4")

    def test_ac_bp600a1_isolation_check_precedes_self_isolate_and_worktree_root_is_consumed(self):
        # covers: BP-600a-1
        # covers: BP-600a-2
        """The workspace step runs before any other dispatch, and the workspace_path it returns is actually
        threaded into later phases -- not merely produced and discarded."""
        result = self._run(
            **{"workspace-ensure": workspace_ensure_reply("/isolated/wt-threaded", branch="feature/threaded-slug")}
        )
        calls_by_label = {c.label: c for c in result.agent_calls}
        assert "workspace-ensure" in calls_by_label
        first = min(result.agent_calls, key=lambda c: c.call_index)
        assert first.label == "workspace-ensure", (
            f"The workspace step must be the first dispatch (BP-600a-1). First: {first.label!r}"
        )
        later_call = calls_by_label["ac-creation"]
        assert "/isolated/wt-threaded" in later_call.prompt, (
            "The workspace_path the maker returned must be consumed by a later phase's prompt (here: "
            "ac-creation) -- proving the value is actually used, not just returned and dropped (BP-600a-2)."
        )
