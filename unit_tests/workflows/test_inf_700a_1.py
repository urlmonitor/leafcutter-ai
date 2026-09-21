"""
MODULE: unit_tests/workflows/test_inf_700a_1.py
GOAL: RED behavioral test baseline for INF-700a-1 — "Work that finishes
    leaves its learnings on their surfaces, with nobody having run anything".

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1.yaml

CONTRACT THIS TEST FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

  The driver's completion sequence (templates/workflows-js/fast-lane-ship.js,
  chosen here as the completion path under test — it already has a
  well-established full-success E2 harness fixture in
  unit_tests/workflows/test_bo2400f_10i_release_wiring.py) must dispatch a
  knowledge-routing step BEFORE the phase that publishes the unit of work's
  own output (the "fastlane-commit" agent() call). The dispatch:

    - carries `label: "knowledge-routing-step"` (a NEW agent() call site the
      completion sequence must add; no such label is dispatched today, which
      is why every test below is RED).
    - returns a JSON object shaped
      `{ "read": <int>, "written": <int>, "unwritten": <int>,
         "case": "completed" | "could_not_complete" | "did_not_run" }`.
    - its read/written/unwritten figures must be CONSUMED by the driver —
      they must reach the driver's own final reported result under a
      `knowledge_routing` key, not merely be dispatched and discarded
      (BP-1100f-4-style anti-fire-and-forget requirement, restated in this
      AC's own it_requirements: "THE RESULT MUST BE CONSUMED, NOT MERELY
      PRODUCED").

  Per this repository's "Gate / Workflow ACs — Verify Behaviorally, Not by
  Grep" convention (also restated in this AC's own it_requirements as "NOT
  COVERABLE BY GREP"), every test below drives the REAL fast-lane-ship.js
  script through the Node.js-backed E2 stub harness
  (unit_tests/_workflow_engine_harness.py) and asserts on the OBSERVED
  agent() dispatch sequence and the OBSERVED terminal payload — never on a
  grep of the JS source.

RED baseline: no "knowledge-routing-step" label is dispatched anywhere in
fast-lane-ship.js today (ADR-034: "Nothing invokes the harvester"), so every
assertion below that looks for it fails.
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

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"
_TIMEOUT = 30


def _worktree_label_response(worktree_root: Path) -> dict[str, Any]:
    return {
        "worktree_path": str(worktree_root),
        "branch": "fast-lane/test-inf700a1",
        "ac_store_path": str(worktree_root / "docs" / "acceptance-criteria"),
        "created": True,
    }


def _full_success_responses(worktree_root: Path, ac_ids: list[str]) -> dict[str, Any]:
    """Label-keyed stub responses that drive fast-lane-ship.js end-to-end to a
    successful close (status: ok, commit + PR both succeed).

    Mirrors the base fixture already established and exercised in
    unit_tests/workflows/test_bo2400f_10i_release_wiring.py, plus the
    "fastlane-pr" response needed to sail all the way past the PR phase to
    the terminal payload (that file's fixture stops at the commit phase).
    coder-connected's files_modified is deliberately empty so
    changelogRequired resolves False and the changelog phase is skipped,
    keeping this fixture minimal.
    """
    return {
        "fastlane-worktree": _worktree_label_response(worktree_root),
        "resolve-connected": {"ac_ids": ac_ids, "message": f"{len(ac_ids)} to build"},
        "claim-connected": {
            "claimed": ac_ids,
            "excluded_claimed": [],
            "target_refused": False,
            "message": f"claimed {len(ac_ids)} ACs",
        },
        "test-writer-connected": {
            "status": "ok",
            "tests_written": ["unit_tests/x/test_stub.py"],
            "gate_passed": True,
            "reason": None,
            "green_at_baseline": [],
            "message": "red baseline established",
        },
        "coder-connected": {
            "status": "ok",
            "files_modified": [],
            "green": True,
            "coverage_ok": True,
            "uncovered_ac_ids": [],
            "message": "implemented",
        },
        "fastlane-review": {
            "verdict_obtained": True,
            "high_findings": [],
            "medium_findings": [],
            "low_suppressed_count": 0,
            "message": "clean review",
        },
        "fastlane-commit": {
            "status": "ok",
            "branch": "fast-lane/test-inf700a1",
            "message": "committed",
        },
        "fastlane-pr": {
            "status": "ok",
            "pr_url": "https://github.com/example/example/pull/1",
            "message": "PR opened",
        },
    }


def _calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def _dispatched_labels(result: HarnessResult) -> list:
    return [c.label for c in result.agent_calls]


class TestKnowledgeRoutingDispatchedBeforeCommit(unittest.TestCase):
    """AC INF-700a-1: the routing step must be dispatched, and must be
    dispatched before the phase that publishes the unit of work's own
    output — here, the "fastlane-commit" agent() call."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_ids = ["INF-9111a", "INF-9111b"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_completion_step_dispatches_knowledge_routing_before_commit(self) -> None:
        # covers: INF-700a-1
        # angle: criterion
        """Drive fast-lane-ship.js to completion; a 'knowledge-routing-step'
        dispatch must occur, and it must occur BEFORE the 'fastlane-commit'
        dispatch — so its writes can ride the commit the path already makes
        (INF-700a-1's ordering clause).
        """
        label_responses = _full_success_responses(self.worktree_root, self.ac_ids)
        label_responses["knowledge-routing-step"] = {
            "read": 3,
            "written": 3,
            "unwritten": 0,
            "case": "completed",
        }
        result = run_workflow_under_e2(
            _WORKFLOW_PATH,
            timeout=_TIMEOUT,
            label_responses=label_responses,
            args={"ac": self.ac_ids[0]},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        routing_calls = _calls_with_label(result, "knowledge-routing-step")
        self.assertGreaterEqual(
            len(routing_calls),
            1,
            "Expected a 'knowledge-routing-step' agent() dispatch somewhere in "
            "the completion sequence — none was found. Dispatched labels: "
            f"{_dispatched_labels(result)}",
        )

        commit_calls = _calls_with_label(result, "fastlane-commit")
        self.assertGreaterEqual(
            len(commit_calls),
            1,
            "Sanity check failed: 'fastlane-commit' was not dispatched at "
            f"all. Dispatched labels: {_dispatched_labels(result)}",
        )

        self.assertLess(
            routing_calls[0].call_index,
            commit_calls[0].call_index,
            "The knowledge-routing-step dispatch must occur BEFORE the "
            "fastlane-commit dispatch, so its writes can ride the commit "
            "the path already makes (INF-700a-1's ordering clause: 'the "
            "routing step ran early enough ... for its writes to be "
            "carried by the publication the unit of work already makes'). "
            f"Dispatched labels in order: {_dispatched_labels(result)}",
        )


class TestReportedResultCarriesRoutingFigures(unittest.TestCase):
    """AC INF-700a-1: the driver's reported result must carry the
    read/written/unwritten figures the routing step reported — a result
    whose figures are absent (or zero when the run actually routed
    something) fails this criterion."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_ids = ["INF-9112a"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_reported_result_carries_nonzero_read_written_and_unwritten_figures(
        self,
    ) -> None:
        # covers: INF-700a-1
        # angle: reachability
        # surface_invoked: the completion path dispatched through the
        # workflow engine harness (run_workflow_under_e2), not the routing
        # step (harvest_learnings.harvest()) called directly.
        """The terminal payload (result.result) must expose the routing
        figures under a 'knowledge_routing' key, with values matching the
        run just performed — three read, two written, one unwritten — not
        zeros or an absent key."""
        label_responses = _full_success_responses(self.worktree_root, self.ac_ids)
        label_responses["knowledge-routing-step"] = {
            "read": 3,
            "written": 2,
            "unwritten": 1,
            "case": "completed",
        }
        result = run_workflow_under_e2(
            _WORKFLOW_PATH,
            timeout=_TIMEOUT,
            label_responses=label_responses,
            args={"ac": self.ac_ids[0]},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        payload = result.result or {}
        knowledge_routing = payload.get("knowledge_routing")
        self.assertIsInstance(
            knowledge_routing,
            dict,
            "The driver's terminal payload must carry a 'knowledge_routing' "
            "object consuming the routing step's figures. Got terminal "
            f"payload: {payload!r}",
        )
        self.assertEqual(
            knowledge_routing.get("read"),
            3,
            f"Expected knowledge_routing.read == 3. Got: {knowledge_routing!r}",
        )
        self.assertEqual(
            knowledge_routing.get("written"),
            2,
            f"Expected knowledge_routing.written == 2. Got: {knowledge_routing!r}",
        )
        self.assertEqual(
            knowledge_routing.get("unwritten"),
            1,
            f"Expected knowledge_routing.unwritten == 1. Got: {knowledge_routing!r}",
        )


class TestRoutingResultIsConsumedNotFireAndForget(unittest.TestCase):
    """AC INF-700a-1 / it_requirements 'THE RESULT MUST BE CONSUMED, NOT
    MERELY PRODUCED'. Runs the same completion path twice against routing
    outcomes that differ and asserts the driver's reported result DIFFERS
    between the two — the anti-fire-and-forget test. An invocation whose
    output goes nowhere produces identical reports and goes red here."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_ids = ["INF-9113a"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_with_routing(self, routing_response: dict[str, Any]) -> HarnessResult:
        label_responses = _full_success_responses(self.worktree_root, self.ac_ids)
        label_responses["knowledge-routing-step"] = routing_response
        return run_workflow_under_e2(
            _WORKFLOW_PATH,
            timeout=_TIMEOUT,
            label_responses=label_responses,
            args={"ac": self.ac_ids[0]},
        )

    def test_the_routing_result_is_consumed_in_the_driver_control_flow(self) -> None:
        # covers: INF-700a-1
        # angle: seam
        succeeding = self._run_with_routing(
            {"read": 3, "written": 3, "unwritten": 0, "case": "completed"}
        )
        degraded = self._run_with_routing(
            {"read": 3, "written": 1, "unwritten": 2, "case": "completed"}
        )
        self.assertEqual(succeeding.error, "", f"Harness error: {succeeding.error}")
        self.assertEqual(degraded.error, "", f"Harness error: {degraded.error}")

        self.assertNotEqual(
            (succeeding.result or {}).get("knowledge_routing"),
            (degraded.result or {}).get("knowledge_routing"),
            "Two runs with DIFFERING routing outcomes (0 unwritten vs 2 "
            "unwritten) must produce DIFFERING driver-reported results. "
            "Identical reports across differing routing outcomes means the "
            "routing step's output goes nowhere — the exact fire-and-forget "
            "shape this repository has shipped twice before (fast-lane-"
            "build.js gates whose results were never read; fast_lane.py's "
            f"silent select_batch no-op). succeeding.result={succeeding.result!r} "
            f"degraded.result={degraded.result!r}",
        )


if __name__ == "__main__":
    unittest.main()
