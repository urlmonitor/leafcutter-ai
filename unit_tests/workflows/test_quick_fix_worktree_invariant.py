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
        # angle: criterion
        """No dispatch of a run tells an agent to run 'git worktree add'.

        BO-4300c-3 (test-drift repair, classification: test_drift): the Guards
        prompt used to carry a 'Do NOT invoke git worktree add' prohibition that
        this test looked for. The workspace is now the maker's ready answer, so
        there is no isolation step left for such a prohibition to guard, and the
        invariant it enforced is asserted on the RECORDED dispatches instead: in
        a full run, no prompt sent to any agent contains 'git worktree add'.
        """
        result = run_workflow_under_e2(_JS_PATH, label_responses=_full_success_responses())
        assert result.agent_calls, f"the run dispatched nothing; stderr={result.stderr!r}"
        offenders = [c.label for c in result.agent_calls if "git worktree add" in str(c.prompt)]
        assert offenders == [], (
            "quick-fix must never have an agent run 'git worktree add' (BP-600a-1, "
            f"BP-600a-2); the workspace maker owns that. Dispatches that do: {offenders}"
        )


# ===========================================================================
# BP-600a-2 — never dispatches worktree-agent or feature skill
# ===========================================================================

class TestBP600a2NoIsolationInfra:
    """BP-600a-2: Never dispatches worktree-agent or feature skill."""

    def test_ac_bp600a2_no_worktree_agent_dispatch(self):
        # covers: BP-600a-2
        # angle: criterion
        """The only dispatch of a run to 'worktree-agent' is the one workspace step.

        BO-4300c-3 (test-drift repair, classification: test_drift): quick-fix used
        to dispatch nothing to 'worktree-agent' and said so in its Guards prompt.
        The workspace is now the maker's answer; when the run is not handed that
        answer it makes exactly ONE shell-permitted dispatch for it (ADR-073),
        labelled 'workspace-ensure', and nothing else in the run goes to
        'worktree-agent' -- no isolation infrastructure beyond that step.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses={
                **_full_success_responses(),
                "workspace-ensure": {"status": "ok", "workspace_path": "/ws/fix", "branch": "fix/some-branch"},
            },
            args={"project_root": "/tmp/bp600a2-project"},
        )
        to_worktree_agent = [c.label for c in result.agent_calls if c.agent_type == "worktree-agent"]
        assert to_worktree_agent == ["workspace-ensure"], (
            "Only the workspace step may be dispatched to 'worktree-agent' "
            f"(BP-600a-2, BO-4300c-3). Got: {to_worktree_agent}; labels={_labels(result)}"
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

    # BO-4300c-3: test_ac_bp600a2_guard_instructs_no_isolation stood here. It looked
    # for a 'do not invoke worktree-agent' sentence in the Guards prompt; the Guards
    # step no longer has an isolation phase to forbid, and the invariant is now
    # held behaviourally by test_ac_bp600a2_no_worktree_agent_dispatch above.


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
        # angle: criterion
        """When the maker's ready answer is handed in, no workspace dispatch is
        made, and the workspace path and branch it names are the ones the
        guards operate on.

        BO-4300c-3 (test-drift repair, classification: test_drift): the test used
        to script an 'isolation-check' reporting a usable non-default branch and
        assert 'self-isolate' was skipped. Both steps are gone; the same intent
        (no isolation step of the run's own, and the reported location and branch
        -- not a re-derived value -- anchor later phases) is stated against the
        maker's answer.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(),
            args={
                "workspace": {
                    "status": "ok",
                    "workspace_path": "/repo",
                    "branch": "fix/some-branch",
                }
            },
        )
        labels = _labels(result)
        assert "workspace-ensure" not in labels and "self-isolate" not in labels, (
            "No workspace or isolation dispatch may be made when the maker's "
            f"answer is handed in (BP-600a-1). Labels dispatched: {labels}"
        )
        guard_call = next(c for c in result.agent_calls if c.label == "guard-checks")
        assert "/repo" in guard_call.prompt and "fix/some-branch" in guard_call.prompt, (
            "The guard-checks prompt must be anchored to the workspace path "
            "and branch the maker reported, not a re-derived value (BP-600a-1)."
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
        # angle: seam
        """The workspace step runs before the guards, and the workspace_path the
        maker's answer returns is actually threaded into later phases -- not
        merely produced and discarded.

        BO-4300c-3 (test-drift repair, classification: test_drift): restated from
        the 'isolation-check' / 'self-isolate' pair onto the one workspace
        dispatch. The maker's reply is scripted for that dispatch, the run names
        a project root so the maker is asked, and the location the reply names
        must appear in a later phase's prompt.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses={
                **_full_success_responses(),
                "workspace-ensure": {
                    "status": "ok",
                    "workspace_path": "/isolated/wt-threaded",
                    "branch": "feature/threaded-slug",
                },
            },
            args={"project_root": "/tmp/bp600a1-project"},
        )
        calls_by_label = {c.label: c for c in result.agent_calls}
        assert "workspace-ensure" in calls_by_label and "guard-checks" in calls_by_label
        assert (
            calls_by_label["workspace-ensure"].call_index
            < calls_by_label["guard-checks"].call_index
        ), "the workspace step must be dispatched before the guards (BP-600a-1)."
        later_call = calls_by_label["ac-creation"]
        assert "/isolated/wt-threaded" in later_call.prompt, (
            "The workspace_path in the maker's answer must be consumed by a "
            "later phase's prompt (here: ac-creation) — proving the value is "
            "actually used, not just returned and dropped (BP-600a-2)."
        )


# BO-4300c-3: the run no longer decides for itself whether to isolate. The four
# triggers below (not a repo, on main, on master, detached HEAD) were that
# decision; the workspace maker owns it now, and what the run does with the
# maker's answer is held by the tests above and by test_bo_4300c_3.py. They stay
# as strict expected failures (see unit_tests/workflows/_bo4300c3_retired.py).
from _bo4300c3_retired import retire  # noqa: E402

retire(
    globals(),
    "TestBP600WorkflowInPlaceAndSelfIsolation.test_ac_bp600a2_self_isolate_dispatched_when_not_a_repo",
    "TestBP600WorkflowInPlaceAndSelfIsolation.test_ac_bp600a2_self_isolate_dispatched_on_main",
    "TestBP600WorkflowInPlaceAndSelfIsolation.test_ac_bp600a2_self_isolate_dispatched_on_master",
    "TestBP600WorkflowInPlaceAndSelfIsolation.test_ac_bp600a2_self_isolate_dispatched_on_detached_head",
)
