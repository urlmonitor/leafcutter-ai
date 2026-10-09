"""
Tests for TQ-600a-13-v, run half -- "A post-merge run that did not run to completion is reported as not
run, never as green". The run-history, conclusion and wording half is in test_tq_600a_13_v_history.py.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-v.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

VERDICT FILE (`post-merge-verdict.json`, schema_version 2, same key set as a red/green file, plus one key)
  verdict "did_not_complete" with `stage` exactly one of
    setup | collection | empty_selection | retry_failed | cancelled_or_timed_out | startup_failure |
    result_unreadable | unknown          (the stages post_merge_suite already has -- pytest_aborted,
    truncated, exit_status_without_failures, nothing_passed, mostly_skipped -- stay as they are;
    `nothing_collected` and `run_report_missing` are replaced by empty_selection / the rows below)
  `collection_errors`  sorted list of node ids that failed to COLLECT (empty list when none). A collection
    error is never in `failing` and never counted as a failing test.

WHAT THE VERDICT JOB OBSERVES (decided from the `needs.run.result` / `needs.retry.result` it is given,
which reach the module through `env:` of the classify step, plus the artifacts it downloaded)
  first-run report readable, `collection_errors` non-empty     -> collection (wins over pytest_aborted)
  first-run report readable, `results` empty (any exit status)  -> empty_selection (never green)
  run result `cancelled`                                        -> cancelled_or_timed_out
  run result `failure`, no first-run report                     -> setup
  run result `success`, first-run report absent                 -> result_unreadable
  first-run report present but not JSON / truncated             -> result_unreadable
  retry result `failure` (first-run failures present)           -> retry_failed
  Green needs: readable report, no collection error, >= 1 test collected, every failure passed on retry.
  Any other input is did_not_complete too (`unknown`), never green.

VERDICT JOB UNDER CANCELLATION. The job and EVERY step it needs (checkout, download, classify, upload, the two
`Verdict:` steps) carry a status-agnostic `if:` (`always()`), so a whole-run cancellation still leaves a
`post-merge-verdict` artifact with stage cancelled_or_timed_out, and the job fails at `Verdict: did not complete`.
(The executor models cancellation with `execute_job(..., cancelled=True)`: steps implying success() are skipped.)
`run` and `retry` keep exiting 0 whenever they produced a readable report.
======================================================================
"""

from __future__ import annotations

import unittest

from ._ending_harness import (
    CHECK,
    FIRST_REPORT,
    HEAD_SHA,
    Cases,
    EndingTestCase,
    drive_lane,
    drive_verdict,
    expect_did_not_complete,
    first_run_report_text,
    live_red_verdict,
)
from ._notice_fakes import LABEL, import_production, old_description, run_record, state_block, visible_text
from ._workflow_jobs import FakeGitHub

OK_AND_BAD = "import pytest\n\n\n@pytest.mark.manual\ndef test_ok():\n    assert True\n\n\n@pytest.mark.manual\ndef test_bad():\n    assert False\n"
BROKEN_MODULE = "import pytest\nimport tq600a13v_no_such_module\n\n\n@pytest.mark.manual\ndef test_never_collected():\n    pass\n"


class _EndingBase(EndingTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = FakeGitHub()

    @classmethod
    def tearDownClass(cls):
        cls.api.close()
        super().tearDownClass()

    def assert_notice_says_not_run(self, drive, stage, *, open_notice):
        """Apply the produced verdict file to the notice: raised or updated, never closed, worded as not-run."""
        self.svc.reset()
        self.svc.runs = [run_record(5, "failure" if stage != "cancelled_or_timed_out" else "cancelled", head_sha=HEAD_SHA)]
        if open_notice:
            self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
        applied = self.apply(drive.file, 105)
        CHECK.assertEqual(0, applied.code, applied.log)
        if open_notice:
            CHECK.assertEqual([("comment", 4), ("edit", 4)], self.svc.writes(), "an open notice is updated, never closed")
            body = self.svc.writes_of("edit")[0][1]["body"]
        else:
            CHECK.assertEqual([("create", None)], self.svc.writes())
            body = self.svc.writes_of("create")[0][1]["body"]
        block = state_block(body)
        CHECK.assertEqual(("did_not_complete", stage), (block["verdict"], block["stage"]))
        prose = visible_text(body)
        CHECK.assertIn("did not complete", prose)
        CHECK.assertNotIn("is red", prose, "a run that never ran must not read like a test failure")
        if stage == "cancelled_or_timed_out":  # the runner cannot tell the two apart, so the prose says both
            CHECK.assertIn("cancelled or timed out", prose)
        else:
            CHECK.assertIn(stage, body)
        if not drive.file["failing"]:
            CHECK.assertNotIn("failing tests", body.lower(), "no failing-tests heading over an empty list")


class TestTq600a13vEndings(_EndingBase):
    def test_tq600a_13_v_every_incomplete_ending_is_not_green(self):
        # covers: TQ-600a-13-v
        # angle: criterion
        """AC-v: setup failure, failed retry job, truncated artifact, corrupt artifact, absent artifact, run job
        timed out: did_not_complete with the right stage, the verdict job fails at its named step, and the
        notice is raised or updated -- never closed -- saying the run did not complete and at which stage.

        Must be implemented: stage derivation from the dependency results in scripts/ci/post_merge_suite.py
        and the workflow's classify step passing them in.
        """
        real = first_run_report_text(self.api, {"tests/test_lane.py": OK_AND_BAD})
        cases = Cases()
        rows = [
            ("setup failure: no artifact at all", "failure", "skipped", {}, "setup"),
            ("retry job failed", "success", "failure", {FIRST_REPORT: real.encode()}, "retry_failed"),
            ("truncated first-run report", "success", "skipped", {FIRST_REPORT: real[: len(real) // 2].encode()}, "result_unreadable"),
            ("corrupt first-run report", "success", "skipped", {FIRST_REPORT: b"\x00\xff not json at all"}, "result_unreadable"),
            ("report absent although the run job succeeded", "success", "skipped", {}, "result_unreadable"),
            ("run job timed out", "cancelled", "skipped", {}, "cancelled_or_timed_out"),
        ]
        for index, (label, run_result, retry_result, artifacts, stage) in enumerate(rows):
            with cases.case(label):
                drive = drive_verdict(self.api, run_result, retry_result, artifacts=artifacts)
                if stage == "retry_failed":
                    self._expect_retry_failed(drive)
                else:
                    expect_did_not_complete(drive, stage)
                self.assert_notice_says_not_run(drive, stage, open_notice=index % 2 == 1)
                if index == 0:
                    # The live fixture predates -v; -v adds exactly one key, `collection_errors`, always present.
                    expected_keys = sorted({*live_red_verdict(), "collection_errors"})
                    CHECK.assertEqual(expected_keys, sorted(drive.file), "the file is the live verdict shape plus exactly `collection_errors`")
                    CHECK.assertEqual([], drive.file["collection_errors"], "no collection error on this path: an empty list, never an absent key")
        cases.check()

    @staticmethod
    def _expect_retry_failed(drive):
        """A failed retry never reads red or green: the first-run failures were not confirmed."""
        if drive.file is None:
            raise AssertionError("no verdict artifact uploaded:\n" + drive.verdict.log_text()[-800:])
        CHECK.assertEqual(("did_not_complete", "retry_failed"), (drive.file["verdict"], drive.file["stage"]))
        CHECK.assertEqual(("failure", "Verdict: did not complete"), (drive.verdict.conclusion, drive.verdict.failed_step))

    def test_tq600a_13_v_a_cancelled_run_still_leaves_a_did_not_complete_verdict(self):
        # covers: TQ-600a-13-v
        # angle: discrimination
        """AC-v must_catch: the verdict job is conditioned to skip on cancellation, so a cancellation leaves no
        record. The executor models the cancelled run: only status-agnostic jobs and steps still run.

        Wrong version caught: `if: ${{ !cancelled() }}` on the job, or a classify/upload step without `always()`.
        """
        drive = drive_verdict(self.api, "cancelled", "skipped", cancelled=True)
        self.assertNotEqual("skipped", drive.verdict.conclusion, "the verdict job must run on a cancelled run")
        expect_did_not_complete(drive, "cancelled_or_timed_out")
        self.assert_notice_says_not_run(drive, "cancelled_or_timed_out", open_notice=False)


class TestTq600a13vEmptyAndCollection(_EndingBase):
    def test_tq600a_13_v_an_empty_population_is_never_green(self):
        # covers: TQ-600a-13-v
        # angle: discrimination
        """AC-v THE DESCRIPTOR THAT CANNOT BE DROPPED: a selection that matches nothing (a renamed marker, a
        moved directory) is not green because no test failed. Real child session (exit 5), then the verdict job.

        Wrong versions caught: green on `failing == []`; `nothing_collected` instead of the named stage; the
        verdict step skipped on an empty report; green on whatever exit status an empty report carries.
        """
        cases = Cases()
        with cases.case("real run job, a lane with no test marked into it"):
            drive = drive_lane(self.api, {"tests/test_plain.py": "def test_not_in_the_lane():\n    assert True\n"})
            CHECK.assertEqual("success", drive.run.conclusion, drive.run.log_text()[-800:])
            CHECK.assertEqual("skipped", drive.retry.conclusion, "nothing failed, so nothing is re-executed")
            expect_did_not_complete(drive, "empty_selection")
            CHECK.assertEqual(0, drive.file["collected"])
        suite = import_production("scripts.ci.post_merge_suite")
        for exit_status in (0, 1, 5):
            with cases.case(f"empty report, pytest exit status {exit_status}"):
                report = {"runner": "r", "exitstatus": exit_status, "expected": 0, "ran": 0, "results": {}}
                verdict = suite.build_verdict_file(report, None, {})
                CHECK.assertEqual(("did_not_complete", "empty_selection"), (verdict["verdict"], verdict["stage"]))
                CHECK.assertNotEqual(0, suite.exit_status(verdict))
        cases.check()

    def test_tq600a_13_v_a_collection_error_is_not_a_test_failure_and_not_green(self):
        # covers: TQ-600a-13-v
        # angle: real_artifact
        """AC-v: one lane module raises at import, one lane test passes; the real child session (with
        `--continue-on-collection-errors`, as the repo's pytest.ini has) still runs the passing test.

        Wrong versions caught: green because the passing test passed; the collection error reported as a failing
        test by node id (red); a collection error that vanishes from the verdict.
        """
        drive = drive_lane(self.api, {"tests/test_ok.py": "import pytest\n\n\n@pytest.mark.manual\ndef test_ok():\n    assert True\n", "tests/test_broken.py": BROKEN_MODULE})
        self.assertEqual("success", drive.run.conclusion, drive.run.log_text()[-800:])
        expect_did_not_complete(drive, "collection")
        self.assertEqual(["tests/test_broken.py"], drive.file["collection_errors"])
        self.assertNotIn("tests/test_broken.py", drive.file["failing"])
        self.assertIn("tests/test_ok.py::test_ok", drive.file["collected_ids"], "the passing test did run: the run is not green for another reason")

    def test_tq600a_13_v_a_collection_error_is_collection_even_when_pytest_aborts(self):
        # covers: TQ-600a-13-v
        # angle: discrimination
        """AC-v: without `--continue-on-collection-errors` pytest ends the session (exit 2) on a collection
        error. The ending is still named `collection`, not `pytest_aborted`: the cause is what a reader needs.

        The retry job is handed a skipped result here: its outcome is not what this test is about.
        """
        tests = {"tests/test_broken.py": BROKEN_MODULE}
        drive = drive_lane(self.api, tests, continue_on_errors=False, skip_retry=True)
        self.assertEqual("success", drive.run.conclusion, drive.run.log_text()[-800:])
        expect_did_not_complete(drive, "collection")


class TestTq600a13vCompleteRunIsGreen(_EndingBase):
    def test_tq600a_13_v_a_complete_passing_run_is_green(self):
        # covers: TQ-600a-13-v
        # angle: criterion
        """AC-v paired control: the whole lane collected, executed, every test passing is green -- verdict job
        succeeds, neither `Verdict:` step runs, and the green run closes the open notice.

        Expected to pass already (the green path was built by -ii); it keeps the not-green rows honest.
        """
        lane = {"tests/test_a.py": "import pytest\n\n\n@pytest.mark.manual\ndef test_a():\n    assert True\n", "tests/test_b.py": "import pytest\n\n\n@pytest.mark.manual\ndef test_b():\n    assert True\n"}
        drive = drive_lane(self.api, lane, run_number=2)
        self.assertEqual(("success", "skipped"), (drive.run.conclusion, drive.retry.conclusion))
        self.assertEqual("success", drive.verdict.conclusion, drive.verdict.log_text()[-800:])
        self.assertEqual(("skipped", "skipped"), (drive.verdict.steps.get("Verdict: red"), drive.verdict.steps.get("Verdict: did not complete")))
        self.assertEqual(("green", None, []), (drive.file["verdict"], drive.file["stage"], drive.file["failing"]))
        self.assertEqual(["tests/test_a.py::test_a", "tests/test_b.py::test_b"], drive.file["collected_ids"])
        self.svc.runs = [run_record(2, "success", head_sha=HEAD_SHA)]
        self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
        self.assertEqual(0, self.apply(drive.file, 102).code)
        self.assertEqual([("close", 4), ("comment", 4)], self.svc.writes())


if __name__ == "__main__":
    unittest.main()
