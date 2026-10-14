"""
MODULE: unit_tests/workflows/test_inf_700a_5_fast_lane_wiring.py
GOAL: Prove fast-lane-ship.js CONSUMES the INF-700a-5 durability step in its
    control flow -- driven through the real workflow under the Node-backed
    engine harness, never by grepping the JS source.

    What the path must do (INF-700a-5 / -5-i, BrainCandy's 2026-10-08 answers):
      - the routing step ("knowledge-routing-step") runs the completion_routing
        CLI's `stage` IN THE WORKTREE, before "fastlane-commit";
      - every path the stage reports in its manifest is staged BY NAME by the
        commit phase (the commit agent stages by name; `git add -A` working by
        accident is not relied on);
      - after the commit -- on the success path AND on the commit-failure
        path -- exactly one "knowledge-routing-observe" dispatch asks git what
        the commit actually carried, and ITS answer is what the terminal
        payload reports under `knowledge_routing`;
      - an observation that cannot be obtained never lets a staged write be
        counted as written;
      - none of it changes the run's own status (fail-open).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

import workflows.test_inf_700a_1 as _base  # noqa: E402

_WORKFLOW = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"
_MANIFEST = ["memory/project_learning.md", "docs/reference/some-surface.md"]
_STAGED = {
    "case": "completed",
    "read": 2,
    "written": 2,
    "unwritten": 0,
    "manifest": _MANIFEST,
    "detail": None,
}


def _observed(written: int, unwritten: int, reason: str = "left_out_of_commit") -> dict[str, Any]:
    return {
        "case": "completed",
        "read": 2,
        "written": written,
        "unwritten": unwritten,
        "unwritten_records": [
            {"destination": _MANIFEST[1], "text": "t", "reason": reason, "eligible": True}
        ][:unwritten],
        "waiting": {"present": 2, "read": 2, "difference": 0, "records": [], "note": "n"},
        "detail": None,
    }


class _FastLaneCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_lane(self, observe: Any = None, commit_ok: bool = True, staged: Any = _STAGED):
        responses = _base._full_success_responses(self.worktree, ["INF-9150a"])
        responses["knowledge-routing-step"] = staged
        if observe is not None:
            responses["knowledge-routing-observe"] = observe
        if not commit_ok:
            responses["fastlane-commit"] = {"status": "error", "message": "hook refused"}
        result = run_workflow_under_e2(
            _WORKFLOW, timeout=30, label_responses=responses, args={"ac": "INF-9150a"}
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")
        return result

    @staticmethod
    def calls(result, label: str) -> list:
        return [c for c in result.agent_calls if c.label == label]

    @staticmethod
    def prompt(call) -> str:
        return call.prompt if isinstance(call.prompt, str) else str(call.prompt)


class TestStageRunsInTheWorktreeBeforeTheCommit(_FastLaneCase):
    def test_the_stage_runs_the_cli_in_the_worktree_and_the_commit_stages_its_manifest(
        self,
    ) -> None:
        # covers: INF-700a-5
        # angle: seam
        result = self.run_lane(observe=_observed(2, 0))
        stage = self.calls(result, "knowledge-routing-step")[0]
        commit = self.calls(result, "fastlane-commit")[0]
        self.assertLess(stage.call_index, commit.call_index)
        self.assertIn("completion_routing_cli.py stage", self.prompt(stage))
        self.assertIn(f"--working-dir {self.worktree}", self.prompt(stage))
        self.assertNotIn("from the repository root", self.prompt(stage))
        for path in _MANIFEST:
            self.assertIn(path, self.prompt(commit), "manifest paths must be staged by name")


class TestObservationDecidesTheReport(_FastLaneCase):
    def test_exactly_one_observation_follows_the_commit_and_drives_the_report(self) -> None:
        # covers: INF-700a-5, INF-700a-5-i
        # angle: reachability
        result = self.run_lane(observe=_observed(1, 1))
        observes = self.calls(result, "knowledge-routing-observe")
        commit = self.calls(result, "fastlane-commit")[0]
        self.assertEqual(len(observes), 1, "exactly one observation per path")
        self.assertGreater(observes[0].call_index, commit.call_index)
        self.assertIn("--commit-status ok", self.prompt(observes[0]))
        report = (result.result or {}).get("knowledge_routing")
        self.assertEqual((report["written"], report["unwritten"]), (1, 1), report)
        self.assertEqual(report["unwritten_records"][0]["destination"], _MANIFEST[1])

    def test_differing_observations_produce_differing_reports_with_equal_status(self) -> None:
        # covers: INF-700a-5-i
        # angle: criterion
        carried = self.run_lane(observe=_observed(2, 0))
        dropped = self.run_lane(observe=_observed(1, 1))
        self.assertNotEqual(
            carried.result["knowledge_routing"], dropped.result["knowledge_routing"]
        )
        self.assertEqual(carried.result["status"], dropped.result["status"])

    def test_an_unobtainable_observation_never_counts_a_staged_write_as_written(self) -> None:
        # covers: INF-700a-5
        # angle: failure
        result = self.run_lane(observe={"status": "ok", "message": "no case field"})
        report = result.result["knowledge_routing"]
        self.assertEqual(report["written"], 0, report)
        self.assertEqual(report["unwritten"], 2, report)
        self.assertEqual(report["case"], "could_not_complete", report)

    def test_a_refused_commit_is_observed_and_reported_on_the_blocked_payload(self) -> None:
        # covers: INF-700a-5-i
        # angle: failure
        result = self.run_lane(
            observe=_observed(0, 2, reason="publication_refused"), commit_ok=False
        )
        observes = self.calls(result, "knowledge-routing-observe")
        self.assertEqual(len(observes), 1)
        self.assertIn("--commit-status failed", self.prompt(observes[0]))
        self.assertEqual(result.result["status"], "blocked")
        report = result.result["knowledge_routing"]
        self.assertEqual((report["written"], report["unwritten"]), (0, 2), report)

    def test_a_stage_that_did_not_run_is_reported_as_did_not_run(self) -> None:
        # covers: INF-700a-5
        # angle: boundary
        result = self.run_lane(
            observe={"case": "did_not_run", "detail": None}, staged={"status": "ok"}
        )
        self.assertEqual(result.result["knowledge_routing"]["case"], "did_not_run")


if __name__ == "__main__":
    unittest.main()
