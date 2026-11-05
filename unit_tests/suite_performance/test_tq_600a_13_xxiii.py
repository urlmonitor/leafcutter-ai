"""
Tests for TQ-600a-13-xxiii -- "In the live-database lane a skipped test is never a passed test, and a skip for an
unreachable database means the lane is broken".

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xxiii.yaml
The ASSUMED PRODUCTION CONTRACT (report ``skip_reasons``, the verdict file's ``live_database`` object, stages, the recognised
no-database reason) is in ``_live_lane_harness.py``. The in-process ``classify_live_results`` the AC names is reached here
through the verdict builder's real entry point (the ``verdict`` CLI), so the tests bind the behaviour, not a private name.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ._ending_harness import Cases
from ._live_lane_harness import (
    LIVE_DIR,
    LOOKALIKE_REASON,
    OTHER_REASON,
    STARTUP_STAGE,
    UNREACHABLE,
    UNREACHABLE_STAGE,
    cli_env,
    exit_status_cli,
    live_report,
    live_test,
    need_file,
    need_live,
    nid,
    project_with,
    read_json,
    report,
    verdict_cli,
)

P1, P2, F1, U1, U2, O1, O2 = (nid(n) for n in ("p1", "p2", "f1", "u1", "u2", "o1", "o2"))
C1, C2, S1 = "unit_tests/test_c.py::test_c1", "unit_tests/test_c.py::test_c2", "unit_tests/test_c.py::test_s1"
GREEN_CORR = report({C1: "passed"})


def _live_ids(live: dict, key: str) -> list:
    """The ids of a live_database list that holds ids or ``{"id", "reason"}`` objects."""
    return [item["id"] if isinstance(item, dict) else item for item in live[key]]


class TestTq600a13XxiiiSkips(unittest.TestCase):
    def _live(self, live_first, live_retry=None, *, corr=GREEN_CORR):
        with tempfile.TemporaryDirectory() as raw:
            result = verdict_cli(Path(raw), first=corr, live_first=live_first, live_retry=live_retry)
            return need_file(result), need_live(result)

    def test_tq_600a_13_xxiii_no_skip_is_counted_as_passed_in_any_live_lane_count(self):
        # covers: TQ-600a-13-xxiii
        # angle: discrimination
        """A report of passed, failed, unreachable-skipped and other-skipped tests: no skipped id is in passed, failing or the executed count.

        Wrong versions caught: a verdict built only from failures counts every skip as a pass; collected-and-executed is
        `len(results)`, so skipped tests inflate it. Control row: the two passing tests and the failure are all present.
        """
        first = live_report({P1: "passed", P2: "passed", F1: "failed", U1: "skipped", O1: "skipped"}, {U1: UNREACHABLE, O1: OTHER_REASON})
        _file, live = self._live(first, live_report({F1: "failed"}, runner="live-retry-machine"))
        self.assertEqual([P1, P2], live["passed"])
        self.assertEqual([F1], live["failing"])
        self.assertEqual(sorted([F1, P1, P2]), live["collected_ids"])
        self.assertEqual(3, live["collected"], "collected-and-executed must not count the two skipped tests")
        for key in ("passed", "failing", "collected_ids", "passed_on_retry"):
            self.assertFalse({U1, O1} & set(live[key]), f"a skipped id is in {key}")
        self.assertEqual([U1], _live_ids(live, "unreachable_skips"))
        self.assertEqual([O1], _live_ids(live, "skipped"))

    def test_tq_600a_13_xxiii_an_unreachable_database_skip_makes_the_lane_did_not_complete_and_names_the_test(self):
        # covers: TQ-600a-13-xxiii
        # angle: criterion
        """Two tests skip with the recognised no-database reason beside a pass: did_not_complete at live_database_unreachable, both ids named.

        Wrong versions caught: the recognised reason is matched by a loose substring (the look-alike skip, whose reason mentions
        `unreachable` and `database`, would be named); the unreachable skip is read as an other-reason skip and the run stays green;
        the stage reuses the start-up stage.
        """
        first = live_report({P1: "passed", U1: "skipped", U2: "skipped", O1: "skipped"}, {U1: UNREACHABLE, U2: UNREACHABLE, O1: LOOKALIKE_REASON})
        file, live = self._live(first)
        self.assertEqual(("did_not_complete", UNREACHABLE_STAGE), (live["verdict"], live["stage"]))
        self.assertEqual(("did_not_complete", UNREACHABLE_STAGE), (file["verdict"], file["stage"]))
        self.assertNotEqual(STARTUP_STAGE, live["stage"])
        self.assertEqual([U1, U2], _live_ids(live, "unreachable_skips"))
        self.assertEqual([{"id": O1, "reason": LOOKALIKE_REASON}], live["skipped"], "the look-alike reason is an ordinary skip")

    def test_tq_600a_13_xxiii_an_other_reason_skip_is_named_with_its_reason_and_kept_apart(self):
        # covers: TQ-600a-13-xxiii
        # angle: boundary
        """One test skipped for a stated non-database reason beside passing tests: listed with its reason, absent from passed and failing, run stays green.

        Wrong versions caught: the skip is merged into the passed list; it is dropped and invisible; its reason text is lost.
        """
        first = live_report({P1: "passed", P2: "passed", O1: "skipped"}, {O1: OTHER_REASON})
        file, live = self._live(first)
        self.assertEqual([{"id": O1, "reason": OTHER_REASON}], live["skipped"])
        self.assertEqual([P1, P2], live["passed"])
        self.assertEqual([], live["failing"])
        self.assertEqual("green", live["verdict"], "an other-reason skip alone neither fails nor aborts the lane")
        self.assertEqual("green", file["verdict"])
        self.assertEqual([], _live_ids(live, "unreachable_skips"))

    def test_tq_600a_13_xxiii_a_lane_that_executed_nothing_to_a_pass_or_failure_is_never_green(self):
        # covers: TQ-600a-13-xxiii
        # angle: boundary
        """A live report whose every test skipped for a stated other reason, and one whose folder collected nothing: neither is green; the empty one is did_not_complete.

        Wrong versions caught: an all-skipped lane has no failures so a failure-driven verdict reports green; an empty live folder reads green.
        """
        cases = Cases()
        rows = {
            "every test skipped": live_report({O1: "skipped", O2: "skipped"}, {O1: OTHER_REASON, O2: OTHER_REASON}),
            "folder collected nothing": report({}, reachable=True, exitstatus=5),
        }
        for label, first in rows.items():
            with cases.case(label):
                file, live = self._live(first)
                self.assertNotEqual("green", live["verdict"])
                self.assertNotEqual("green", file["verdict"])
                self.assertTrue(live["stage"], "a lane that executed nothing names its stage")
                if label == "folder collected nothing":
                    self.assertEqual("did_not_complete", live["verdict"])
        cases.check()

    def test_tq_600a_13_xxiii_a_retry_skip_for_an_unreachable_database_is_not_passed_on_retry(self):
        # covers: TQ-600a-13-xxiii
        # angle: discrimination
        """A first-run failure whose retry only skipped: never passed-on-retry, never failed twice; unreachable makes did_not_complete, another reason is reported as skipped.

        Wrong versions caught: a retry that only skipped has no failure left, so the test is called passed on retry; a retry skip is
        counted as failed twice and the run is red.
        """
        first = live_report({F1: "failed", P1: "passed"})
        cases = Cases()
        with cases.case("unreachable retry skip"):
            file, live = self._live(first, live_report({F1: "skipped"}, {F1: UNREACHABLE}, "live-retry-machine"))
            self.assertEqual(("did_not_complete", UNREACHABLE_STAGE), (file["verdict"], file["stage"]))
            self.assertNotIn(F1, live["passed_on_retry"])
            self.assertNotIn(F1, live["failing"])
            self.assertEqual([F1], _live_ids(live, "unreachable_skips"))
        with cases.case("other-reason retry skip"):
            file, live = self._live(first, live_report({F1: "skipped"}, {F1: OTHER_REASON}, "live-retry-machine"))
            self.assertNotIn(F1, live["passed_on_retry"])
            self.assertIn(F1, live["failing"], "a first-run failure whose retry only skipped was never confirmed passing: it stays failing")
            self.assertEqual("red", file["verdict"], "a skipped retry is never a pass, so the failure keeps the run red")
            self.assertIn(F1, _live_ids(live, "skipped"))
        cases.check()

    def test_tq_600a_13_xxiii_a_first_run_failure_whose_retry_skipped_for_an_ordinary_reason_keeps_the_lane_red(self):
        # covers: TQ-600a-13-xxiii
        # angle: discrimination
        """A live test that failed in the first run and skipped (ordinary reason) on the retry, beside a passing one and a retry pass: the lane and the run are red.

        Wrong version caught: the retry skip drops the id out of both `failing` and `passed_on_retry`, so the lane reads green
        although the test never passed. Control row: the id the retry really passed is passed-on-retry and not failing.
        """
        first = live_report({F1: "failed", P1: "failed", P2: "passed"})
        retry = live_report({F1: "skipped", P1: "passed"}, {F1: OTHER_REASON}, "live-retry-machine")
        file, live = self._live(first, retry)
        self.assertEqual([F1], live["failing"])
        self.assertEqual([P1], live["passed_on_retry"])
        self.assertEqual(("red", None), (live["verdict"], live["stage"]))
        self.assertEqual("red", file["verdict"])

    def test_tq_600a_13_xxiii_the_same_skips_in_the_correctness_lane_and_shards_change_nothing(self):
        # covers: TQ-600a-13-xxiii
        # angle: discrimination
        """Correctness-lane tests that skip with the no-database reason leave the correctness verdict as it was before this change, beside a green live lane.

        The recorded baseline (the pre-change classification of this report: two passes and one skip is a complete, green lane,
        one skipped, three collected, no stage). Wrong version caught: the unreachable-skip rule is applied to every report, so the
        correctness lane turns did_not_complete where these tests legitimately skip.
        """
        corr = report({C1: "passed", C2: "passed", S1: "skipped"}, skips={S1: UNREACHABLE})
        file, live = self._live(live_report({P1: "passed"}), corr=corr)
        self.assertEqual("green", live["verdict"], "the live lane beside it is complete and green")
        baseline = {"verdict": "green", "stage": None, "failing": [], "passed_on_retry": [], "collected": 3, "skipped": 1, "collected_ids": sorted([C1, C2, S1])}
        self.assertEqual(baseline, {key: file[key] for key in baseline})

    def test_tq_600a_13_xxiii_the_lane_report_written_by_a_real_session_carries_each_skip_reason(self):
        # covers: TQ-600a-13-xxiii
        # angle: real_artifact
        """A real child pytest session with the lane-report plugin over pass / fail / unreachable-skip / other-skip: the file on disk holds each reason, and its classification gives the four lists.

        Wrong version caught: the report keeps only a status string, so the reason of every skip is dropped and none can be told apart.
        """
        live = {
            "p1": live_test("p1"),
            "f1": live_test("f1", "assert False"),
            "u1": live_test("u1", f"pytest.skip({UNREACHABLE!r})"),
            "o1": live_test("o1", f"pytest.skip({OTHER_REASON!r})"),
        }
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            project = project_with(base / "project", live)
            path = base / "lane-report.json"
            argv = [sys.executable, "-m", "pytest", "-p", "scripts.ci._lane_report_plugin", "--lane-report", str(path), f"{LIVE_DIR}/", "-p", "no:cacheprovider"]
            try:
                subprocess.run(argv, cwd=str(project), env=cli_env(), capture_output=True, text=True, timeout=120, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                message = f"cannot run the real session: {exc}"
                raise AssertionError(message) from exc
            real = read_json(path)
            self.assertEqual({nid("u1"): UNREACHABLE, nid("o1"): OTHER_REASON}, real.get("skip_reasons"))
            real["reachability"] = {"reachable": True, "detail": ""}
            result = verdict_cli(base / "verdict", first=GREEN_CORR, live_first=real, live_retry=live_report({nid("f1"): "failed"}, runner="live-retry-machine"))
            live = need_live(result)
        self.assertEqual([nid("p1")], live["passed"])
        self.assertEqual([nid("f1")], live["failing"])
        self.assertEqual([nid("u1")], _live_ids(live, "unreachable_skips"))
        self.assertEqual([{"id": nid("o1"), "reason": OTHER_REASON}], live["skipped"])

    def test_tq_600a_13_xxiii_the_verdict_cli_reads_a_skip_report_and_exits_non_zero(self):
        # covers: TQ-600a-13-xxiii
        # angle: reachability
        """`verdict` then `exit-status` as child processes over a live report holding an unreachable-database skip: did_not_complete at live_database_unreachable, ids named, exit non-zero."""
        first = live_report({P1: "passed", U1: "skipped"}, {U1: UNREACHABLE})
        with tempfile.TemporaryDirectory() as raw:
            result = verdict_cli(Path(raw), first=GREEN_CORR, live_first=first)
            file, live = need_file(result), need_live(result)
            status = exit_status_cli(result.path)
        self.assertEqual(("did_not_complete", UNREACHABLE_STAGE), (file["verdict"], file["stage"]))
        self.assertEqual([U1], _live_ids(live, "unreachable_skips"))
        self.assertNotEqual(0, status, "exit-status must fail a did_not_complete verdict")
