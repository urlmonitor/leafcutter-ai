"""
MODULE: unit_tests/workflows/test_bo4000b_branch_staleness_decision.py
GOAL: Behavioral tests for BO-4000b -- a local branch behind origin/main is never silently checked out into
    a new worktree.
BUSINESS CONTEXT: FIELD EVIDENCE -- run wf_0e0872f9-453, 2026-09-14: the stale local branch
    `epic/truthful-project-record`, 47 commits behind origin/main, was checked out as-is. See BO-4000b.yaml.
RE-POINTED BY BO-4300c-3 / BO-4300a-1-ia: comparing the branch with origin/main, starting from origin/main,
    and refusing a branch with unique commits are the workspace MAKER's decisions now; the workflow no longer
    dispatches branch-standing or worktree-setup. What the workflow owes is proven here: it sends the maker
    one command that picks no base itself, adopts an ok answer, and when the maker REFUSES (a branch behind
    with unique commits, an origin/main that cannot be fetched) it stops before any phase agent with a
    message that quotes the maker's reply -- the branch, the counts and the reason reach the operator
    verbatim -- and never works on the stale branch.
ARCHITECTURE: The workflow-body cases drive templates/workflows-js/build-feature.js through
    unit_tests/_workflow_engine_harness.py. BO-4300f-2 removed the branch-standing lookup of
    worktree_repo_facts.py; the maker now decides whether an existing branch is reusable (see
    unit_tests/build_orchestration/test_bo_4300b_2_ii.py and test_bo_4300a_1.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2, workspace_answer_of  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
TICKET = "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/07_TICKET-x.md"


def _run(label_responses, **extra_args):
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS, label_responses=label_responses, args={"target": bfx.EPIC_NAME, **extra_args}
    )


def _workspace_calls(result):
    return [c for c in result.agent_calls if c.label == bfx.WORKSPACE_LABEL]


def _phase_calls(result):
    return [c for c in result.agent_calls if c.label not in bfx.RESOLVE_PHASE_LABELS]


def _git(cwd, args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


class TestBehindBranchWithNoUniqueCommitsStartsFromOriginMain(unittest.TestCase):
    def test_behind_branch_with_no_unique_commits_starts_the_worktree_from_origin_main(self) -> None:
        # covers: BO-4000b
        # angle: criterion
        """A 47-behind, 0-ahead branch: the maker starts the workspace from origin/main and says so in its
        ok answer. The workflow adopts it -- one workspace dispatch whose command picks no base itself, and
        every phase rooted at the answer's location.
        """
        answer = bfx.ready_workspace(
            bfx.NAMED_LOCATION, created=True, base_matches_origin_main=True, base_commit="a" * 40,
            behind=47, ahead=0,
        )
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=answer))
        calls = _workspace_calls(result)
        self.assertEqual(len(calls), 1, f"stderr={result.stderr!r}")
        self.assertNotIn("origin/main", calls[0].prompt or "", "the workflow must not pick the base itself")
        self.assertTrue(_phase_calls(result), f"stderr={result.stderr!r}")
        planner = [c for c in result.agent_calls if c.label == "ticket-planner"]
        self.assertIn(bfx.NAMED_LOCATION, planner[0].prompt or "")


class TestBehindBranchWithUniqueCommitsStops(unittest.TestCase):
    def test_behind_branch_with_unique_commits_stops_and_names_both_counts(self) -> None:
        # covers: BO-4000b
        # angle: failure
        """A 47-behind, 3-ahead branch: the maker refuses. The run dispatches no phase agent and its error
        quotes the refusal, so the branch, 3, and 47 reach the operator.
        """
        refusal = bfx.refused_workspace(
            "BRANCH_HAS_UNIQUE_COMMITS",
            f"branch {bfx.TARGET_BRANCH} is behind origin/main and holds commits of its own",
            branch=bfx.TARGET_BRANCH, ahead=3, behind=47,
        )
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=refusal))
        self.assertEqual(_phase_calls(result), [])
        payload = result.result or {}
        self.assertEqual(payload.get("status"), "error")
        message = str(payload.get("message"))
        self.assertIn(bfx.TARGET_BRANCH, message)
        self.assertIn("BRANCH_HAS_UNIQUE_COMMITS", message)
        self.assertRegex(message, r"ahead\W+3")
        self.assertRegex(message, r"behind\W+47")
        self.assertNotEqual((payload.get("resolved_target") or {}).get("worktree_path"), bfx.NAMED_LOCATION)


class TestUpToDateBranchUsedWithoutStalenessReport(unittest.TestCase):
    def test_up_to_date_branch_is_used_without_a_staleness_report(self) -> None:
        # covers: BO-4000b
        # angle: boundary
        """A 0-behind branch is used as it stands: the run proceeds on the answer's location and the report
        carries no staleness statement.
        """
        answer = bfx.ready_workspace(bfx.NAMED_LOCATION, created=False, base_matches_origin_main=True)
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=answer))
        self.assertTrue(_phase_calls(result), f"stderr={result.stderr!r}")
        payload = result.result or {}
        self.assertIsNone((payload.get("resolved_target") or {}).get("worktree_staleness"))
        self.assertNotIn("stale", json.dumps(payload).lower())


class TestUnfetchableOriginMainRefusesExistingBranch(unittest.TestCase):
    def test_unfetchable_origin_main_refuses_an_existing_branch(self) -> None:
        # covers: BO-4000b
        # angle: failure
        """When origin/main cannot be fetched the maker refuses (FETCH_FAILED); the run stops before any
        phase agent and the refusal says the branch's standing could not be checked.
        """
        refusal = bfx.refused_workspace(
            "FETCH_FAILED", "origin/main could not be fetched, so the standing of the existing branch cannot be checked",
        )
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=refusal))
        self.assertEqual(_phase_calls(result), [])
        payload = result.result or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertIn("FETCH_FAILED", str(payload.get("message")))
        self.assertIn("cannot be checked", str(payload.get("message")))


class TestReuseSkipsBranchComparisonEntirely(unittest.TestCase):
    def test_reused_worktree_branch_is_not_compared_moved_or_refused(self) -> None:
        # covers: BO-4000b
        # angle: seam
        """When the run is handed the workspace (``args.workspace``), no dispatch of any kind touches its
        branch: no workspace dispatch, no branch-standing call, no fetch-driven comparison.
        """
        result = _run(
            bfx.success_label_responses(ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE),
            workspace=workspace_answer_of(bfx.ready_workspace(bfx.UXP_WORKTREE, created=False)),
        )
        self.assertEqual(_workspace_calls(result), [])
        self.assertEqual([c for c in result.agent_calls if c.label == "branch-standing"], [])
        self.assertTrue(_phase_calls(result), f"stderr={result.stderr!r}")


class TestReachableFromTopLevelBody(unittest.TestCase):
    def test_branch_staleness_decision_is_reachable_from_the_workflow_top_level_body(self) -> None:
        # covers: BO-4000b
        # angle: reachability
        """The criterion, failure, and boundary cases are each driven through the harness running
        build-feature.js's own top-level body.
        """
        behind_only = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], workspace_reply=bfx.ready_workspace(bfx.NAMED_LOCATION, behind=47, ahead=0),
        ))
        self.assertTrue(_phase_calls(behind_only))

        both = _run(bfx.success_label_responses(
            ticket_paths=[TICKET],
            workspace_reply=bfx.refused_workspace("BRANCH_HAS_UNIQUE_COMMITS", "unique commits", ahead=3, behind=47),
        ))
        self.assertEqual(_phase_calls(both), [])

        current = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], workspace_reply=bfx.ready_workspace(bfx.NAMED_LOCATION, behind=0, ahead=0),
        ))
        self.assertTrue(_phase_calls(current))


if __name__ == "__main__":
    unittest.main()
