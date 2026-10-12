"""
MODULE: unit_tests/workflows/test_inf_700a_5_ii_case_with_waiting.py
GOAL: INF-700a-5-ii's second descriptor -- a record the routing step never
    read is not reported as routed, as written, or as nothing-to-do -- on the
    production path, per BrainCandy's 2026-10-09 decision ("Option A"):

      - `observe` reports `case: completed_with_waiting` when the run
        completed and its waiting difference is > 0; `completed` now means
        completed with nothing left waiting. `waiting` stays a field.
      - every consumer of the case (fast-lane-ship.js, quick-fix.js,
        build-epic.js) trusts `completed_with_waiting` as a completed run,
        reports it distinctly (never collapsed into `completed`, never
        counted as `did_not_run`), and lets it change nothing about the
        work's own status.

    The CLI tests run the real completion_routing_cli.py in a subprocess on a
    real sink (records from the real emit_knowledge.py) and a scratch git
    install + clone. The workflow tests drive the real workflow files under
    the Node-backed engine harness, never a grep.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._inf700a5_fixtures as fx  # noqa: E402
from workflows.test_inf_700a_1_iv_epic_drive_wiring import _routing, _run_epic  # noqa: E402
from workflows.test_inf_700a_5_cli import _OTHER, _CliCase  # noqa: E402
from workflows.test_inf_700a_5_fast_lane_wiring import _FastLaneCase  # noqa: E402
from workflows.test_inf_700a_5_quick_fix_wiring import _QuickFixCase  # noqa: E402

_LATE_TEXT = "emitted by a publishing phase after the stage"
_WAITING = {
    "present": 2, "read": 1, "difference": 1,
    "records": [{"text": _LATE_TEXT, "destination": "memory/other.md"}],
    "note": "still in the install's sink, waiting for the next completed unit of work",
}


def _observed(case: str, written: int, waiting: dict) -> dict:
    return {"case": case, "read": written, "written": written, "unwritten": 0,
            "manifest": ["memory/project_learning.md"][:written], "unwritten_records": [],
            "waiting": waiting, "detail": None}


_QUIET = {"present": 1, "read": 1, "difference": 0, "records": [], "note": "n"}


class TestObserveNamesTheWaitInItsCase(_CliCase):
    def _late_run(self, branch: str) -> dict:
        self.emit("read by the stage")
        wt = self.worktree(branch)
        staged = self.cli("stage", "--working-dir", str(wt))
        self.emit(_LATE_TEXT, destination=_OTHER)
        self.own_output(wt, branch)
        fx.commit_paths(wt, ["own_output.txt", *staged["manifest"]], branch)
        return self.cli("observe", "--working-dir", str(wt), "--commit-status", "ok")

    def test_a_record_emitted_after_stage_gives_completed_with_waiting(self) -> None:
        # covers: INF-700a-5-ii
        # angle: criterion
        observed = self._late_run("late")
        self.assertEqual(observed["case"], "completed_with_waiting", observed)
        self.assertEqual(observed["waiting"]["difference"], 1, "waiting stays a field")
        self.assertEqual([r["text"] for r in observed["waiting"]["records"]], [_LATE_TEXT])

    def test_a_quiet_run_gives_completed(self) -> None:
        # covers: INF-700a-5-ii
        # angle: boundary
        self.emit("quiet path")
        run = self.complete(self.worktree("quiet"), "quiet")
        self.assertEqual(run["observed"]["case"], "completed", run)
        self.assertEqual(run["observed"]["waiting"]["difference"], 0, run)

    def test_an_unread_record_is_not_reported_as_routed_written_or_nothing_to_do(self) -> None:
        # covers: INF-700a-5-ii
        # angle: failure
        # The nothing-to-do value is taken from a REAL nothing-to-do run (an
        # empty sink), not typed in, so the comparison tracks the CLI.
        nothing = self.complete(self.worktree("nothing"), "nothing")["observed"]
        self.assertEqual((nothing["read"], nothing["written"]), (0, 0), nothing)
        observed = self._late_run("unread")
        # 1. not the routed / wrote-everything value
        self.assertNotEqual(observed["case"], "completed", observed)
        # 2. not the nothing-to-do value
        self.assertNotEqual(observed["case"], nothing["case"], observed)
        # 3. not in the written count, nor among the written paths
        self.assertEqual(observed["written"], 1, "only the record the stage read is written")
        self.assertNotIn(_OTHER, observed["manifest"], observed)
        self.assertNotIn(_LATE_TEXT, json.dumps(observed["manifest"]), observed)


class TestFastLaneReportsTheWaitDistinctly(_FastLaneCase):
    def test_completed_with_waiting_is_surfaced_and_changes_no_status(self) -> None:
        # covers: INF-700a-5-ii
        # angle: seam
        waiting = self.run_lane(observe=_observed("completed_with_waiting", 2, _WAITING))
        quiet = self.run_lane(observe=_observed("completed", 2, _QUIET))
        report = waiting.result["knowledge_routing"]
        self.assertEqual(report["case"], "completed_with_waiting", report)
        self.assertEqual(report["written"], 2, "a trusted completed run keeps its figures")
        self.assertEqual(report["waiting"]["difference"], 1, report)
        self.assertEqual(quiet.result["knowledge_routing"]["case"], "completed")
        self.assertEqual(waiting.result["status"], quiet.result["status"])


class TestQuickFixReportsTheWaitDistinctly(_QuickFixCase):
    def test_completed_with_waiting_is_surfaced_and_changes_no_status(self) -> None:
        # covers: INF-700a-5-ii
        # angle: seam
        waiting = self.run_fix(observe=_observed("completed_with_waiting", 1, _WAITING))
        quiet = self.run_fix(observe=_observed("completed", 1, _QUIET))
        report = waiting.result["knowledge_routing"]
        self.assertEqual(report["case"], "completed_with_waiting", report)
        self.assertEqual(report["written"], 1, "a trusted completed run keeps its figures")
        self.assertEqual(report["waiting"]["difference"], 1, report)
        self.assertEqual(quiet.result["knowledge_routing"]["case"], "completed")
        self.assertEqual(waiting.result["status"], quiet.result["status"])


class TestBuildEpicCountsWaitingTicketsSeparately(unittest.TestCase):
    def test_a_waiting_ticket_is_trusted_reported_distinctly_and_counted_apart(self) -> None:
        # covers: INF-700a-5-ii
        # angle: seam
        waiting = {**_routing(2, 0, case="completed_with_waiting"), "waiting": _WAITING}
        result = _run_epic({
            "01_a.md": {"status": "ok", "knowledge_routing": waiting},
            "02_b.md": {"status": "ok", "knowledge_routing": _routing(1, 0)},
        }).result
        report = result["knowledge_routing"]
        cases = {t["ticket_path"]: (t["case"], t["written"]) for t in report["tickets"]}
        self.assertEqual(
            cases, {"01_a.md": ("completed_with_waiting", 2), "02_b.md": ("completed", 1)}, report
        )
        self.assertEqual(report["written"], 3, "the waiting ticket's writes are trusted")
        self.assertEqual(report["waiting_tickets"], 1, report)
        self.assertEqual(result["status"], "ok")

    def test_completed_with_waiting_changes_no_status_and_is_not_did_not_run(self) -> None:
        # covers: INF-700a-5-ii
        # angle: failure
        waiting = {**_routing(1, 0, case="completed_with_waiting"), "waiting": _WAITING}
        with_wait = _run_epic({"01_a.md": {"status": "ok", "knowledge_routing": waiting}}).result
        quiet = _run_epic({"01_a.md": {"status": "ok", "knowledge_routing": _routing(1, 0)}}).result
        self.assertEqual(with_wait["status"], quiet["status"])
        self.assertNotEqual(with_wait["knowledge_routing"]["tickets"][0]["case"], "did_not_run")
        self.assertEqual(quiet["knowledge_routing"]["waiting_tickets"], 0)


if __name__ == "__main__":
    unittest.main()
