"""
MODULE: unit_tests/workflows/test_inf_700a_1_ii.py
GOAL: RED behavioral test baseline for INF-700a-1-ii — "A routing step that
    cannot finish says so where the work is reported, and changes nothing
    about the work."

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1-ii.yaml

CONTRACT THIS TEST FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

  Building on the "knowledge-routing-step" dispatch contract established in
  test_inf_700a_1.py (fast-lane-ship.js), the driver's terminal payload must
  carry a `knowledge_routing.case` field taking exactly one of three
  enumerated values:

    - "completed"          — the routing step ran and finished.
    - "could_not_complete" — the routing step ran but could not finish (the
                              sink could not be read, or a destination could
                              not be written); the payload also carries what
                              it could not do.
    - "did_not_run"         — the routing step did not run at all. This must
                              NOT be rendered as "completed" with zero
                              figures.

  Whichever case occurs, the driver's own reported status/outcome (here:
  `status: "ok"`, matching a clean fast-lane-ship.js run) and exit
  status must be UNCHANGED — a knowledge step never fails, retries, or
  blocks the unit of work's own outcome (fail-open, ADR-034).

  Per this repository's "Gate / Workflow ACs — Verify Behaviorally, Not by
  Grep" convention, every test below drives the REAL fast-lane-ship.js
  script through the Node.js-backed E2 stub harness and asserts on the
  OBSERVED terminal payload — never a grep of the JS source.

RED baseline: no "knowledge_routing" key of any shape exists in the terminal
payload today (INF-700a-1 is itself unimplemented), so every assertion below
fails.
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

_KNOWN_CASES = frozenset({"completed", "could_not_complete", "did_not_run"})


def _worktree_label_response(worktree_root: Path) -> dict[str, Any]:
    return {
        "worktree_path": str(worktree_root),
        "branch": "fast-lane/test-inf700a1ii",
        "ac_store_path": str(worktree_root / "docs" / "acceptance-criteria"),
        "created": True,
    }


def _full_success_responses(worktree_root: Path, ac_ids: list[str]) -> dict[str, Any]:
    """Same fixture shape as test_inf_700a_1.py — kept independent on
    purpose, since each AC's test file must stand alone under the fast-lane
    'one-red-rule' gate."""
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
            "branch": "fast-lane/test-inf700a1ii",
            "message": "committed",
        },
        "fastlane-pr": {
            "status": "ok",
            "pr_url": "https://github.com/example/example/pull/1",
            "message": "PR opened",
        },
    }


class _BaseCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_ids = ["INF-9116a"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, routing_response: dict[str, Any] | None) -> HarnessResult:
        label_responses = _full_success_responses(self.worktree_root, self.ac_ids)
        if routing_response is not None:
            label_responses["knowledge-routing-step"] = routing_response
        return run_workflow_under_e2(
            _WORKFLOW_PATH,
            timeout=_TIMEOUT,
            label_responses=label_responses,
            args={"ac": self.ac_ids[0]},
        )


class TestDriverStatusIsEqualWithFailingAndSucceedingRoutingStep(_BaseCase):
    def test_driver_status_is_equal_with_a_failing_and_a_succeeding_routing_step(
        self,
    ) -> None:
        # covers: INF-700a-1-ii
        # angle: criterion
        """Drive the same unit of work twice: once with the routing step
        succeeding, once with it failing (destination write failed). The
        driver's own reported `status` must be EQUAL between the two runs —
        equality between runs, not equality to success, so the same
        assertion also holds for work that failed on its own merits (see
        the failed-drive companion test below)."""
        succeeding = self._run(
            {"read": 1, "written": 1, "unwritten": 0, "case": "completed"}
        )
        failing = self._run(
            {
                "read": 1,
                "written": 0,
                "unwritten": 1,
                "case": "could_not_complete",
                "detail": "destination file could not be written",
            }
        )
        self.assertEqual(succeeding.error, "", f"Harness error: {succeeding.error}")
        self.assertEqual(failing.error, "", f"Harness error: {failing.error}")

        succeeding_status = (succeeding.result or {}).get("status")
        failing_status = (failing.result or {}).get("status")
        self.assertEqual(
            succeeding_status,
            failing_status,
            "The driver's reported status must be identical whether the "
            "knowledge-routing step succeeded or failed — a knowledge step "
            "must never fail, retry, or block the unit of work's own "
            f"outcome. succeeding.result={succeeding.result!r} "
            f"failing.result={failing.result!r}",
        )
        self.assertEqual(
            succeeding_status,
            "ok",
            "Sanity check failed: the succeeding-routing-step run itself "
            f"did not report status 'ok'. Got: {succeeding.result!r}",
        )

        # Anti-vacuous-pass guard: the equality above holds trivially if the
        # routing step never runs at all (status is always "ok" either way).
        # Require the dispatch to have actually happened in BOTH runs, so
        # this test cannot pass merely because nothing was wired yet.
        succeeding_routing_calls = [
            c for c in succeeding.agent_calls if c.label == "knowledge-routing-step"
        ]
        failing_routing_calls = [
            c for c in failing.agent_calls if c.label == "knowledge-routing-step"
        ]
        self.assertGreaterEqual(
            len(succeeding_routing_calls),
            1,
            "Expected a 'knowledge-routing-step' dispatch on the succeeding "
            "run — the equal-status assertion above is vacuous if the "
            "routing step never runs. Dispatched labels: "
            f"{[c.label for c in succeeding.agent_calls]}",
        )
        self.assertGreaterEqual(
            len(failing_routing_calls),
            1,
            "Expected a 'knowledge-routing-step' dispatch on the failing "
            "run too — the equal-status assertion above is vacuous if the "
            "routing step never runs. Dispatched labels: "
            f"{[c.label for c in failing.agent_calls]}",
        )


class TestThreeCasesAreDistinguishableByADataField(_BaseCase):
    def test_the_three_routing_cases_are_distinguishable_by_a_data_field(self) -> None:
        # covers: INF-700a-1-ii
        # angle: seam
        """Produce all three cases and assert the reported result carries a
        distinct enumerated value for each — critically, 'did_not_run' must
        NOT equal 'completed' rendered with zero figures. The 'did_not_run'
        case is produced by NOT overriding the knowledge-routing-step label
        at all, i.e. today's actual behaviour (no such dispatch happens)."""
        completed = self._run(
            {"read": 1, "written": 1, "unwritten": 0, "case": "completed"}
        )
        could_not_complete = self._run(
            {
                "read": 1,
                "written": 0,
                "unwritten": 1,
                "case": "could_not_complete",
                "detail": "sink could not be read",
            }
        )
        did_not_run = self._run(None)

        for label, run in (
            ("completed", completed),
            ("could_not_complete", could_not_complete),
            ("did_not_run", did_not_run),
        ):
            self.assertEqual(run.error, "", f"[{label}] Harness error: {run.error}")

        completed_case = ((completed.result or {}).get("knowledge_routing") or {}).get(
            "case"
        )
        could_not_case = (
            (could_not_complete.result or {}).get("knowledge_routing") or {}
        ).get("case")
        did_not_run_case = (
            (did_not_run.result or {}).get("knowledge_routing") or {}
        ).get("case")

        for name, value in (
            ("completed", completed_case),
            ("could_not_complete", could_not_case),
            ("did_not_run", did_not_run_case),
        ):
            self.assertIn(
                value,
                _KNOWN_CASES,
                f"knowledge_routing.case for the '{name}' scenario must be one "
                f"of {sorted(_KNOWN_CASES)}. Got: {value!r}",
            )

        self.assertNotEqual(
            did_not_run_case,
            completed_case,
            "A unit of work during which the routing step did not run at "
            "all must be reported as a THIRD case, distinct from a routing "
            "step that ran and wrote nothing because there was nothing to "
            "write — 'did_not_run' must not be rendered as 'completed' with "
            "zero figures, which is exactly how an unwired pipeline reads "
            f"as a healthy one. did_not_run reported: {did_not_run_case!r}",
        )
        self.assertEqual(
            completed_case,
            "completed",
            f"Expected the completed-run case to read 'completed'. Got: {completed_case!r}",
        )
        self.assertEqual(
            could_not_case,
            "could_not_complete",
            "Expected the failed-write run's case to read 'could_not_complete'. "
            f"Got: {could_not_case!r}",
        )
        self.assertEqual(
            did_not_run_case,
            "did_not_run",
            "With no knowledge-routing-step dispatch at all (today's actual "
            "behaviour), the driver must report the case as 'did_not_run'. "
            f"Got: {did_not_run_case!r}",
        )


class TestCouldNotCompleteCaseStatesWhatItCouldNotDo(_BaseCase):
    def test_the_could_not_complete_case_states_what_it_could_not_do(self) -> None:
        # covers: INF-700a-1-ii
        # angle: reachability
        # surface_invoked: the completion path dispatched through the
        # workflow engine harness (run_workflow_under_e2), not the routing
        # step called directly.
        """With the routing step reporting a could_not_complete case, the
        reported result must carry the specific cause (e.g. 'sink could not
        be read' vs 'destination file could not be written'), and the two
        causes must be distinguishable from each other."""
        sink_unreadable = self._run(
            {
                "read": 0,
                "written": 0,
                "unwritten": 0,
                "case": "could_not_complete",
                "detail": "sink could not be read",
            }
        )
        destination_unwritable = self._run(
            {
                "read": 1,
                "written": 0,
                "unwritten": 1,
                "case": "could_not_complete",
                "detail": "destination file could not be written",
            }
        )
        self.assertEqual(
            sink_unreadable.error, "", f"Harness error: {sink_unreadable.error}"
        )
        self.assertEqual(
            destination_unwritable.error,
            "",
            f"Harness error: {destination_unwritable.error}",
        )

        sink_detail = (
            (sink_unreadable.result or {}).get("knowledge_routing") or {}
        ).get("detail")
        destination_detail = (
            (destination_unwritable.result or {}).get("knowledge_routing") or {}
        ).get("detail")

        self.assertTrue(
            sink_detail,
            "The 'could_not_complete' case must carry a non-empty 'detail' "
            f"stating what could not be done. Got: {sink_unreadable.result!r}",
        )
        self.assertTrue(
            destination_detail,
            "The 'could_not_complete' case must carry a non-empty 'detail' "
            f"stating what could not be done. Got: {destination_unwritable.result!r}",
        )
        self.assertNotEqual(
            sink_detail,
            destination_detail,
            "A sink-unreadable failure and a destination-unwritable failure "
            "are different causes and must be reported distinguishably from "
            f"each other. sink_detail={sink_detail!r} "
            f"destination_detail={destination_detail!r}",
        )


class TestRoutingFailureDoesNotEnterTheFailureCount(_BaseCase):
    def test_the_routing_failure_does_not_enter_the_unit_of_work_failure_count(
        self,
    ) -> None:
        # covers: INF-700a-1-ii
        # angle: criterion
        """With a failing routing step on an otherwise clean unit of work,
        the driver's own status must be identical to the run with a
        succeeding routing step — fail-open means the knowledge step cannot
        fail, retry, or block the work. (This mirrors the first test in
        this file but is kept as its own descriptor per this AC's
        test_spec, asserting specifically on the fail-open guarantee rather
        than on general status equality.)"""
        succeeding = self._run(
            {"read": 1, "written": 1, "unwritten": 0, "case": "completed"}
        )
        failing = self._run(
            {
                "read": 1,
                "written": 0,
                "unwritten": 1,
                "case": "could_not_complete",
                "detail": "destination file could not be written",
            }
        )
        self.assertEqual(succeeding.error, "", f"Harness error: {succeeding.error}")
        self.assertEqual(failing.error, "", f"Harness error: {failing.error}")

        self.assertEqual(
            (succeeding.result or {}).get("status"),
            (failing.result or {}).get("status"),
            "A failing knowledge-routing step must not enter the unit of "
            "work's own failure/status determination. "
            f"succeeding.result={succeeding.result!r} failing.result={failing.result!r}",
        )

        # Anti-vacuous-pass guard: the equality above holds trivially if the
        # routing step never runs at all. Require the dispatch to have
        # actually happened in both runs.
        succeeding_routing_calls = [
            c for c in succeeding.agent_calls if c.label == "knowledge-routing-step"
        ]
        failing_routing_calls = [
            c for c in failing.agent_calls if c.label == "knowledge-routing-step"
        ]
        self.assertGreaterEqual(
            len(succeeding_routing_calls),
            1,
            "Expected a 'knowledge-routing-step' dispatch on the succeeding "
            "run — the equal-status assertion above is vacuous if the "
            "routing step never runs. Dispatched labels: "
            f"{[c.label for c in succeeding.agent_calls]}",
        )
        self.assertGreaterEqual(
            len(failing_routing_calls),
            1,
            "Expected a 'knowledge-routing-step' dispatch on the failing "
            "run too — the equal-status assertion above is vacuous if the "
            "routing step never runs. Dispatched labels: "
            f"{[c.label for c in failing.agent_calls]}",
        )


if __name__ == "__main__":
    unittest.main()
