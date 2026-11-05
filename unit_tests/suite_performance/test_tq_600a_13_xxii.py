"""
Tests for TQ-600a-13-xxii -- "A live-database lane whose database never becomes reachable is reported as not run,
at its own start-up stage, never as green and never as failing tests".

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xxii.yaml
The ASSUMED PRODUCTION CONTRACT (CLI, report, verdict file, stages, workflow jobs) is in ``_live_lane_harness.py``.
The notice side: a start-up ending is ``did_not_complete`` with stage ``live_database_startup``; the description's plain-words
cause (``_notice_render.STAGE_CAUSES``) says the live-database tests never ran, and no failing-tests heading appears.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ._ending_harness import CHECK, HEAD_SHA, EndingService, expect_did_not_complete
from ._live_lane_harness import (
    STARTUP_STAGE,
    Listener,
    LiveNoticeCase,
    closed_address,
    drive_verdict_job,
    live_report,
    live_run,
    live_test,
    need_file,
    need_live,
    nid,
    project_with,
    ran,
    report,
    seeded,
    verdict_cli,
)
from ._notice_fakes import LABEL, REPO, SERVER, old_description, run_record, state_block, visible_text

CORR_OK, CORR_FAIL = "unit_tests/test_corr.py::test_ok", "unit_tests/test_corr.py::test_bad"
FAIL = nid("publication")
RUN_ENV = {"GITHUB_RUN_ID": "105", "GITHUB_SHA": HEAD_SHA, "GITHUB_REPOSITORY": REPO, "GITHUB_SERVER_URL": SERVER}


def _startup_ending(base: Path, address: str, listener_mode: str | None = None):
    """Run the live lane's first execution against ``address`` and return (completed process, report, witness lines)."""
    state = base / "state"
    state.mkdir()
    project = project_with(base / "project", {"publication": live_test("publication", "assert True")})
    proc, rep, _failures = live_run(project, base / "out", address, extra_env={"LIVE_STATE_DIR": str(state)})
    return proc, rep, ran(state)


class TestTq600a13XxiiStartup(LiveNoticeCase):
    svc: EndingService  # set in EndingTestCase.setUpClass

    def _assert_startup_verdict(self, base: Path, rep: dict, corr: dict | None = None):
        result = verdict_cli(base / "verdict", first=corr or report({CORR_OK: "passed"}), live_first=rep, env=RUN_ENV)
        file, live = need_file(result), need_live(result)
        CHECK.assertEqual(("did_not_complete", STARTUP_STAGE), (file["verdict"], file["stage"]))
        CHECK.assertEqual(("did_not_complete", STARTUP_STAGE, []), (live["verdict"], live["stage"], live["failing"]))
        return file

    def _notice_body(self, file: dict, *, open_notice: bool) -> str:
        self.svc.reset()
        self.svc.runs = [run_record(5, "failure", head_sha=HEAD_SHA)]
        if open_notice:
            self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
        applied = self.apply(file, 105)
        CHECK.assertEqual(0, applied.code, applied.log)
        if open_notice:
            CHECK.assertEqual([("comment", 4), ("edit", 4)], self.svc.writes(), "an open notice is updated, never closed")
            return self.svc.writes_of("edit")[0][1]["body"]
        CHECK.assertEqual([("create", None)], self.svc.writes(), "an ending with no open notice raises one")
        return self.svc.writes_of("create")[0][1]["body"]

    def test_tq_600a_13_xxii_a_database_that_never_answers_ends_the_run_as_live_database_startup(self):
        # covers: TQ-600a-13-xxii
        # angle: criterion
        """A port nothing listens on, with a short limit: the check fails, no live test runs, the verdict is did_not_complete at the start-up stage.

        Wrong versions caught: an instance that never answers reads as nothing failed (green); the ending reuses the `setup` stage;
        the lane executes its tests anyway and reports connection errors (the witness log is not empty).
        """
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            proc, rep, witnessed = _startup_ending(base, closed_address())
            self.assertEqual(0, proc.returncode, proc.stderr[-1500:])
            self.assertIsNotNone(rep, "an unreachable database must still leave a report")
            self.assertIs(False, rep.get("reachability", {}).get("reachable"))
            self.assertEqual({}, rep["results"])
            self.assertEqual([], witnessed, "no live test may be executed against an unreachable database")
            file = self._assert_startup_verdict(base, rep)
        self.assertNotIn(file["stage"], ("setup", "collection", "retry_failed", "empty_selection"))

    def test_tq_600a_13_xxii_a_database_that_answers_its_probe_then_refuses_the_first_connection_is_startup(self):
        # covers: TQ-600a-13-xxii
        # angle: failure
        """A listener accepts the probe's connection and resets every later one: the pre-test connection check fails, the verdict is start-up, not connection-error failures.

        Wrong version caught: a passed health probe is trusted and the first test's connection errors are read as genuine regressions.
        """
        with tempfile.TemporaryDirectory() as raw, Listener("probe_only") as db:
            base = Path(raw)
            proc, rep, witnessed = _startup_ending(base, db.address)
            self.assertEqual(0, proc.returncode, proc.stderr[-1500:])
            self.assertIsNotNone(rep)
            self.assertGreaterEqual(db.connections, 1, "the lane never probed the address")
            self.assertIs(False, rep.get("reachability", {}).get("reachable"), "a database that resets later connections is not reachable")
            self.assertEqual([], witnessed)
            self._assert_startup_verdict(base, rep)

    def test_tq_600a_13_xxii_no_node_ids_and_no_failing_tests_heading_for_a_startup_ending(self):
        # covers: TQ-600a-13-xxii
        # angle: discrimination
        """A real live report full of connection-error failures plus a failed reachability result: live failing is empty and the notice says the tests never ran.

        Wrong versions caught: the connection-error tests stay in the failing list and the notice shows a failing-tests heading over
        them; the new stage has no plain-words cause so the notice shows only the bare stage code.
        """
        live = {"publication": live_test("publication", "raise ConnectionError('connection refused')")}
        with tempfile.TemporaryDirectory() as raw, Listener() as db:
            base = Path(raw)
            project = project_with(base / "project", live)
            _proc, rep, _failures = live_run(project, base / "out", db.address)
            self.assertEqual({FAIL: "failed"}, rep["results"], "the real session must hold the connection-error failure")
            rep["reachability"] = {"reachable": False, "detail": "connection refused"}
            file = self._assert_startup_verdict(base, rep)
            body = self._notice_body(file, open_notice=False)
        prose = visible_text(body)
        self.assertEqual([], file["failing"])
        self.assertIn("never ran", prose.lower())
        self.assertIn("live", prose.lower())
        self.assertNotIn("failing tests", body.lower(), "no failing-tests heading over an empty list")
        self.assertNotIn(FAIL, body, "the connection-error test must not be named")

    def test_tq_600a_13_xxii_a_retry_machine_whose_database_never_became_healthy_is_not_passed_on_retry(self):
        # covers: TQ-600a-13-xxii
        # angle: discrimination
        """The verdict job given live first-run failures, a failed live retry job and no live retry report: did_not_complete at start-up, failures not passed-on-retry.

        The failed live retry job result is the hosting service's answer for a failed service health check, supplied (it cannot be
        produced in the unit layer). Wrong versions caught: a retry that executed nothing is read as zero remaining failures, so as
        passed on retry; the run is green because the first execution's failures are discarded.
        """
        drive = _drive(self.api, seeded(first=report({CORR_OK: "passed"}), live_first=live_report({FAIL: "failed", nid("ok"): "passed"})), live_retry_result="failure")
        expect_did_not_complete(drive, STARTUP_STAGE)
        live = drive.file["live_database"]
        self.assertEqual([], live["passed_on_retry"])
        self.assertEqual([FAIL], live["first_run_failures"])
        self.assertEqual(STARTUP_STAGE, live["stage"])

    def test_tq_600a_13_xxii_the_startup_ending_raises_or_updates_the_notice_and_closes_nothing(self):
        # covers: TQ-600a-13-xxii
        # angle: seam
        """The verdict file the real producer wrote, applied through the notice planner: one notice created, or the open one commented and edited, never closed.

        Wrong versions caught: the unrecognised stage falls into the close branch (an open notice closed); it falls into a no-op branch
        (no notice raised).
        """
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            file = self._assert_startup_verdict(base, report({}, reachable=False, exitstatus=0))
        for open_notice in (False, True):
            body = self._notice_body(file, open_notice=open_notice)
            block = state_block(body)
            self.assertEqual(("did_not_complete", STARTUP_STAGE), (block["verdict"], block["stage"]))
            self.assertIn("did not complete", visible_text(body))
            self.assertNotIn("is red", visible_text(body))
            self.assertNotIn("close", [kind for kind, _number in self.svc.writes()])

    def test_tq_600a_13_xxii_a_green_correctness_lane_does_not_turn_a_startup_ending_green(self):
        # covers: TQ-600a-13-xxii
        # angle: discrimination
        """The combined verdict of a green correctness lane and a start-up ending is did_not_complete at start-up, and a red correctness lane does not outrank it.

        Wrong versions caught: the green lane wins the combination (green run); a did-not-complete live lane ranked below a red
        correctness lane (the stage is lost, the verdict reads red).
        """
        not_run = report({}, reachable=False, exitstatus=0)
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            green = self._assert_startup_verdict(base / "green", not_run)
            red = self._assert_startup_verdict(base / "red", not_run, corr=report({CORR_FAIL: "failed"}))
        self.assertEqual(STARTUP_STAGE, green["stage"])
        self.assertEqual(STARTUP_STAGE, red["stage"], "a red correctness lane must not hide the live start-up ending")

    def test_tq_600a_13_xxii_the_workflow_verdict_job_fails_at_the_did_not_complete_step_for_startup(self):
        # covers: TQ-600a-13-xxii
        # angle: reachability
        """The verdict job (steps verbatim: `verdict` then `exit-status`) given the live run job's failed result and no live report: failure at `Verdict: did not complete`, stage in the artifact."""
        drive = _drive(self.api, seeded(first=report({CORR_OK: "passed"})), live_run_result="failure")
        expect_did_not_complete(drive, STARTUP_STAGE)
        self.assertEqual(STARTUP_STAGE, need_live_of(drive)["stage"])


_drive = drive_verdict_job


def need_live_of(drive) -> dict:
    live = (drive.file or {}).get("live_database")
    CHECK.assertIsInstance(live, dict, "the uploaded verdict has no live_database object")
    assert isinstance(live, dict)  # narrows for the type checker; the assertion above already failed otherwise
    return live
