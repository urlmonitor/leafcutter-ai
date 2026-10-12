"""
MODULE: unit_tests/workflows/test_inf_700a_5_quick_fix_wiring.py
GOAL: Prove quick-fix.js CONSUMES the INF-700a-5 durability step in its control
    flow -- the real workflow driven under the engine harness, never a grep.

    What the path must do (the same contract fast-lane-ship.js meets):
      - the routing step runs the completion_routing CLI's `stage` IN THE
        WORKTREE, before the fix commit, not the harvester "from the repository
        root" (which marks records routed the moment it writes them);
      - the fix commit stages the stage's manifest BY NAME (INF-700a-1-iii's
        numbered stage list, now fed by the manifest instead of a git-status
        diff, which missed destinations that were already dirty);
      - exactly one "knowledge-routing-observe" dispatch follows the fix
        commit, on the success AND the commit-failure path, and ITS answer is
        the terminal `knowledge_routing`;
      - an observation that cannot be obtained never lets a staged write count
        as written; none of it changes the run's own status (fail-open).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _quick_fix_harness import (  # noqa: E402
    _JS_PATH,
    _full_success_responses,
    run_workflow_under_e2,
)

_STAGED = {
    "case": "completed", "read": 1, "written": 1, "unwritten": 0,
    "manifest": ["memory/project_learning.md"], "detail": None,
}


def _observed(written: int, unwritten: int, reason: str = "left_out_of_commit") -> dict[str, Any]:
    return {
        "case": "completed", "read": 1, "written": written, "unwritten": unwritten,
        "manifest": ["memory/project_learning.md"][:written],
        "unwritten_records": [
            {"destination": "memory/project_learning.md", "text": "t", "reason": reason,
             "eligible": True}
        ][:unwritten],
        "waiting": {"present": 1, "read": 1, "difference": 0, "records": [], "note": "n"},
        "detail": None,
    }


class _QuickFixCase(unittest.TestCase):
    def run_fix(self, observe: Any = None, commit_blocked: bool = False, staged: Any = _STAGED):
        overrides: dict[str, Any] = {"knowledge-routing-step": staged}
        if observe is not None:
            overrides["knowledge-routing-observe"] = observe
        if commit_blocked:
            overrides["commit"] = {"status": "blocked", "message": "pre-commit hook refused"}
        result = run_workflow_under_e2(
            _JS_PATH, timeout=30, label_responses=_full_success_responses(**overrides)
        )
        self.assertEqual(result.error, "", f"harness error: {result.error}")
        return result

    @staticmethod
    def calls(result, label: str) -> list:
        return [c for c in result.agent_calls if c.label == label]


class TestQuickFixStagesInTheWorktreeAndObservesTheCommit(_QuickFixCase):
    def test_the_stage_runs_the_cli_in_the_worktree_before_the_fix_commit(self) -> None:
        # covers: INF-700a-5
        # angle: seam
        result = self.run_fix(observe=_observed(1, 0))
        stage = self.calls(result, "knowledge-routing-step")[0]
        commit = self.calls(result, "commit")[0]
        self.assertLess(stage.call_index, commit.call_index)
        self.assertIn("completion_routing_cli.py stage --working-dir /repo", stage.prompt)
        self.assertNotIn("harvest_learnings.py", stage.prompt)
        self.assertNotIn("from the repository root", stage.prompt)
        self.assertRegex(commit.prompt, r"\n\s*5\. memory/project_learning\.md\b")

    def test_exactly_one_observation_follows_the_fix_commit_and_drives_the_report(self) -> None:
        # covers: INF-700a-5, INF-700a-5-i
        # angle: reachability
        result = self.run_fix(observe=_observed(0, 1))
        observes = self.calls(result, "knowledge-routing-observe")
        commit = self.calls(result, "commit")[0]
        self.assertEqual(len(observes), 1)
        self.assertGreater(observes[0].call_index, commit.call_index)
        self.assertIn("--commit-status ok", observes[0].prompt)
        report = result.result["knowledge_routing"]
        self.assertEqual((report["written"], report["unwritten"]), (0, 1), report)
        self.assertEqual(report["unwritten_records"][0]["reason"], "left_out_of_commit")

    def test_differing_observations_change_the_report_but_not_the_status(self) -> None:
        # covers: INF-700a-5-i
        # angle: criterion
        carried = self.run_fix(observe=_observed(1, 0))
        dropped = self.run_fix(observe=_observed(0, 1))
        self.assertNotEqual(
            carried.result["knowledge_routing"], dropped.result["knowledge_routing"]
        )
        self.assertEqual(carried.result["status"], dropped.result["status"])

    def test_an_unobtainable_observation_never_counts_a_staged_write_as_written(self) -> None:
        # covers: INF-700a-5
        # angle: failure
        result = self.run_fix(observe={"status": "ok", "message": "no case"})
        report = result.result["knowledge_routing"]
        self.assertEqual((report["written"], report["unwritten"]), (0, 1), report)
        self.assertEqual(report["case"], "could_not_complete")

    def test_a_blocked_fix_commit_is_observed_and_reported_on_the_blocked_payload(self) -> None:
        # covers: INF-700a-5-i
        # angle: failure
        result = self.run_fix(observe=_observed(0, 1, "publication_refused"), commit_blocked=True)
        observes = self.calls(result, "knowledge-routing-observe")
        self.assertEqual(len(observes), 1)
        self.assertIn("--commit-status failed", observes[0].prompt)
        self.assertEqual(result.result["status"], "blocked")
        self.assertEqual(result.result["knowledge_routing"]["unwritten"], 1)


if __name__ == "__main__":
    unittest.main()
