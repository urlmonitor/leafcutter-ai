"""
Review follow-ups for TQ-600a-13-v: three gaps a review found after the main tests went green.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-v.yaml

1. A run cancelled AFTER `run` and `retry` finished clean leaves a GREEN verdict file (the verdict job runs under
   `always()`) on a run whose conclusion is `cancelled`. The notice must apply it as did_not_complete /
   cancelled_or_timed_out -- not error, never green -- while every other disagreement stays a loud failure.
2. `_run_history.RED_STEP` must be a step name of the workflow's verdict job, or `classify_run` is a silent no-op.
3. The verdict step's dependency results arrive through env: a missing, empty or unrecognised RUN_RESULT is
   `unknown`, never green; the same for RETRY_RESULT when the first run had failures.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ._ending_harness import CHECK, FIRST_REPORT, HEAD_SHA, WORKFLOW, Cases, EndingTestCase, drive_lane, first_run_report_text
from ._notice_fakes import LABEL, import_production, old_description, run_record, state_block
from ._workflow_jobs import FakeGitHub, load_workflow

PASSING = {"tests/test_a.py": "import pytest\n\n\n@pytest.mark.manual\ndef test_a():\n    assert True\n"}
ONE_FAILING = {"tests/test_f.py": "import pytest\n\n\n@pytest.mark.manual\ndef test_ok():\n    assert True\n\n\n@pytest.mark.manual\ndef test_f():\n    assert False\n"}


class TestGreenFileOnACancelledRun(EndingTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = FakeGitHub()
        cls.green = drive_lane(cls.api, PASSING, run_number=2).file

    @classmethod
    def tearDownClass(cls):
        cls.api.close()
        super().tearDownClass()

    def test_tq600a_13_v_review_a_green_file_on_a_cancelled_run_is_did_not_complete(self):
        # covers: TQ-600a-13-v
        # angle: discrimination
        """A green verdict file whose run concluded cancelled / timed_out is applied as did_not_complete at stage
        cancelled_or_timed_out (raised, or updated when a notice is open, never closed, no error exit)."""
        CHECK.assertEqual("green", self.green["verdict"])
        cases = Cases()
        for conclusion in ("cancelled", "timed_out"):
            for open_notice in (False, True):
                with cases.case(f"{conclusion}, notice open: {open_notice}"):
                    self.svc.reset()
                    self.svc.runs = [run_record(2, conclusion, head_sha=HEAD_SHA)]
                    if open_notice:
                        self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
                    applied = self.apply(self.green, 102)
                    CHECK.assertEqual(0, applied.code, applied.log)
                    kinds = [kind for kind, _number in self.svc.writes()]
                    CHECK.assertNotIn("close", kinds, "a cancelled run never closes a notice")
                    body = self.svc.writes_of("edit" if open_notice else "create")[0][1]["body"]
                    block = state_block(body)
                    CHECK.assertEqual(("did_not_complete", "cancelled_or_timed_out"), (block["verdict"], block["stage"]))
        cases.check()

    def test_tq600a_13_v_review_every_other_disagreement_stays_loud(self):
        # covers: TQ-600a-13-v
        # angle: discrimination
        """A green file on a run that concluded failure (or any non-success, non-cancelled conclusion) is still an
        error exit that writes nothing: only a cancellation explains a green file on a non-green run."""
        cases = Cases()
        for conclusion in ("failure", "neutral", "startup_failure"):
            with cases.case(conclusion):
                self.svc.reset()
                self.svc.runs = [run_record(2, conclusion, head_sha=HEAD_SHA)]
                self.svc.add_issue(4, labels=[LABEL], body=old_description(90))
                applied = self.apply(self.green, 102)
                CHECK.assertNotEqual(0, applied.code)
                CHECK.assertEqual([], self.svc.write_attempts)
        cases.check()


class TestRedStepIsPinnedToTheWorkflow(unittest.TestCase):
    def test_tq600a_13_v_review_the_classifier_red_step_is_a_verdict_job_step(self):
        # covers: TQ-600a-13-v
        # angle: reachability
        """`classify_run` looks for `RED_STEP`; if the workflow renames its step the classifier never says red."""
        history = import_production("scripts.ci._run_history")
        steps = [step.get("name") for step in load_workflow(WORKFLOW)["jobs"]["verdict"]["steps"]]
        self.assertIn(history.RED_STEP, steps)


class TestMissingDependencyResultsAreUnknown(unittest.TestCase):
    @staticmethod
    def _verdict(first_text, env):
        suite = import_production("scripts.ci.post_merge_suite")
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            target = base / "artifacts" / FIRST_REPORT[0] / FIRST_REPORT[1]
            target.parent.mkdir(parents=True)
            target.write_text(first_text, encoding="utf-8")
            out = base / "verdict.json"
            clean = {k: v for k, v in os.environ.items() if k not in ("RUN_RESULT", "RETRY_RESULT")}
            with mock.patch.dict(os.environ, {**clean, **env}, clear=True):
                code = suite.main(["verdict", "--artifacts", str(base / "artifacts"), "--output", str(out)])
            return code, json.loads(out.read_text(encoding="utf-8"))

    def test_tq600a_13_v_review_a_missing_or_unrecognised_run_result_is_never_green(self):
        # covers: TQ-600a-13-v
        # angle: discrimination
        """A readable, failure-free report is green only with RUN_RESULT=success; unset, empty, or a value the
        runner never produces is unknown."""
        api = FakeGitHub()
        try:
            text = first_run_report_text(api, PASSING)
        finally:
            api.close()
        cases = Cases()
        with cases.case("control: RUN_RESULT=success is green"):
            _code, verdict = self._verdict(text, {"RUN_RESULT": "success", "RETRY_RESULT": "skipped"})
            CHECK.assertEqual("green", verdict["verdict"])
        for label, env in (("unset", {}), ("empty", {"RUN_RESULT": ""}), ("unrecognised", {"RUN_RESULT": "succeeded"})):
            with cases.case(f"RUN_RESULT {label}"):
                _code, verdict = self._verdict(text, env)
                CHECK.assertEqual(("did_not_complete", "unknown"), (verdict["verdict"], verdict["stage"]))
        cases.check()

    def test_tq600a_13_v_review_a_missing_or_unrecognised_retry_result_with_failures_is_never_red_or_green(self):
        # covers: TQ-600a-13-v
        # angle: discrimination
        """With first-run failures, the retry result must be known: unset, empty or unrecognised is unknown."""
        api = FakeGitHub()
        try:
            text = first_run_report_text(api, ONE_FAILING)
        finally:
            api.close()
        cases = Cases()
        for label, extra in (("unset", {}), ("empty", {"RETRY_RESULT": ""}), ("unrecognised", {"RETRY_RESULT": "ok"})):
            with cases.case(f"RETRY_RESULT {label}"):
                _code, verdict = self._verdict(text, {"RUN_RESULT": "success", **extra})
                CHECK.assertEqual(("did_not_complete", "unknown"), (verdict["verdict"], verdict["stage"]))
        cases.check()


if __name__ == "__main__":
    unittest.main()
