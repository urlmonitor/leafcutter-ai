"""
Tests for TQ-600a-13-xii -- "Only correctness tests hold pull requests; timing-ratio tests run in their own lane
that reports and never holds" (lane half: selection, run / retry / verdict, never-holds).

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xii.yaml
The notice half (lifecycle, lane entrants, follow-up workflow) is in test_tq_600a_13_xii_notice.py.

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this).

1. ``.github/workflows/post-merge-timing.yml`` keeps its name, triggers and concurrency group and becomes THREE jobs
   with ids ``run``, ``retry``, ``verdict``: the same shape as ``post-merge-suite.yml`` (a ``run`` job whose step has
   id ``lane`` and exits zero whenever a report exists, a ``retry`` job skipped on zero first-run failures, a
   ``verdict`` job whose steps ``Classify the run`` / ``Verdict: red`` / ``Verdict: did not complete`` are
   ``if: always()``), every pytest command selecting ``-m timing_ratio`` (and nothing else).
2. ``post_merge_suite.py verdict --lane timing`` writes the verdict file with ``"lane": "timing"``; the in-process
   producer is ``build_verdict_file(..., lane="timing")`` (default lane stays ``"correctness"``).
3. An empty timing lane is ``did_not_complete`` at stage ``empty_selection``: the verdict job's
   ``Verdict: did not complete`` step fails, so the lane's own run is red.
4. A timing fail-then-pass is green with the id in ``passed_on_retry``; it opens no notice of any kind.
5. The hold (``post_merge_hold.evaluate``) never reads the timing workflow or the ``post-merge-timing`` label.
"""

from __future__ import annotations

import configparser
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ._ending_harness import CHECK
from ._hold_harness import RED_JOBS, make_run
from ._notice_fakes import old_description
from ._timing_harness import (
    RED_LABEL,
    TIMING_LABEL,
    TIMING_WORKFLOW,
    TimingNoticeCase,
    drive_timing,
    manual_test,
    plain_test,
    timing_test,
)
from ._workflow_jobs import REPO_ROOT, load_workflow

SUITE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-suite.yml"
RATIO_FILE = "unit_tests/test_ratio.py"
FAILING_ID = f"{RATIO_FILE}::test_ratio_slow"
PASSING_ID = f"{RATIO_FILE}::test_ratio_fast"
RATIO_SOURCE = (
    "import pytest\n\n\n@pytest.mark.timing_ratio\ndef test_ratio_slow():\n    assert False\n\n\n"
    "@pytest.mark.timing_ratio\ndef test_ratio_fast():\n    assert True\n"
)
POPULATION = """\
import unittest

import pytest


def test_plain():
    assert True


@pytest.mark.manual
def test_correctness_manual():
    assert True


@pytest.mark.timing_ratio
def test_timing_without_manual():
    assert True


@pytest.mark.manual
@pytest.mark.timing_ratio
def test_timing_and_manual():
    assert True


def test_ratio_but_unmarked():
    assert True


class TestUnit(unittest.TestCase):
    @pytest.mark.timing_ratio
    def test_unittest_timing(self):
        assert True

    def test_unittest_plain(self):
        assert True
"""


def _expression_after_m(tokens):
    """The ``-m`` selection expressions of a tokenised command (``python -m pytest``'s own ``-m`` is skipped)."""
    return {tokens[i + 1] for i, tok in enumerate(tokens[:-1]) if tok == "-m" and tokens[i + 1] != "pytest"}


def workflow_selections(path):
    """Every pytest ``-m`` expression the workflow's run steps carry, parsed from the real file."""
    found = set()
    for job in (load_workflow(path).get("jobs") or {}).values():
        for step in job.get("steps") or []:
            text = step.get("run")
            if isinstance(text, str) and "pytest" in text:
                found |= _expression_after_m(shlex.split(text))
    return found


def default_selection():
    """The default run's ``-m`` expression, parsed from the real pytest.ini ``addopts``."""
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(REPO_ROOT / "pytest.ini", encoding="utf-8")
    found = _expression_after_m(shlex.split(ini["pytest"]["addopts"]))
    CHECK.assertEqual(1, len(found), f"pytest.ini addopts must carry exactly one -m: {found}")
    return found.pop()


def _collect(project, selection):
    """A real ``pytest --collect-only -q`` in the synthetic project; return the node ids it printed."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    argv = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
    if selection is not None:
        argv += ["-m", selection]
    try:
        proc = subprocess.run(argv, cwd=str(project), env=env, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        message = f"collect-only subprocess could not run: {exc}"
        raise AssertionError(message) from exc
    CHECK.assertEqual(0, proc.returncode, f"collection failed:\n{proc.stdout}{proc.stderr}")
    return {ln.strip() for ln in proc.stdout.splitlines() if "::" in ln and not ln.startswith(("=", " "))}


class TestTq600a13XiiPartition(unittest.TestCase):
    def test_tq600a_13_xii_every_test_is_in_exactly_one_collection(self):
        # covers: TQ-600a-13-xii
        # angle: real_artifact
        """Default, correctness and timing selections (read from the real ini and workflows) partition the population.

        Wrong versions caught: a test marked both `manual` and `timing_ratio` collected by both lanes (a correctness
        selection of plain `manual`); a `timing_ratio` test without `manual` in the default run and the timing lane
        (addopts not excluding the marker); a test in no collection. The population carries an unmarked ratio test
        (default run, by the marker rule) and a unittest.TestCase method carrying the marker.
        """
        correctness = workflow_selections(SUITE_WORKFLOW)
        timing = workflow_selections(TIMING_WORKFLOW)
        self.assertEqual(1, len(correctness), f"the correctness workflow's pytest commands must agree on one -m: {correctness}")
        self.assertEqual(1, len(timing), f"the timing workflow's pytest commands must agree on one -m: {timing}")
        ini = configparser.ConfigParser(interpolation=None)
        ini["pytest"] = {"strict_markers": "true", "addopts": f'-m "{default_selection()}"', "markers": "\nmanual: opt-in lane\ntiming_ratio: timing lane"}
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            with (project / "pytest.ini").open("w", encoding="utf-8") as handle:
                ini.write(handle)
            (project / "unit_tests").mkdir()
            (project / "unit_tests" / "test_population.py").write_text(POPULATION, encoding="utf-8")
            sets = {
                "default": _collect(project, None),
                "correctness": _collect(project, correctness.pop()),
                "timing": _collect(project, timing.pop()),
                "unfiltered": _collect(project, "manual or not manual"),
            }
        prefix = "unit_tests/test_population.py::"
        expected = {
            "default": {"test_plain", "test_ratio_but_unmarked", "TestUnit::test_unittest_plain"},
            "correctness": {"test_correctness_manual"},
            "timing": {"test_timing_without_manual", "test_timing_and_manual", "TestUnit::test_unittest_timing"},
        }
        for lane, names in expected.items():
            self.assertEqual({prefix + n for n in names}, sets[lane], f"the {lane} collection")
        lanes = [sets["default"], sets["correctness"], sets["timing"]]
        self.assertEqual(set(), (lanes[0] & lanes[1]) | (lanes[0] & lanes[2]) | (lanes[1] & lanes[2]), "a test is collected by two lanes")
        self.assertEqual(sets["unfiltered"], lanes[0] | lanes[1] | lanes[2], "a test is collected by no lane")
        self.assertEqual(7, len(sets["unfiltered"]))


class TestTq600a13XiiNeverHolds(TimingNoticeCase):
    def test_tq600a_13_xii_a_timing_failure_never_holds(self):
        # covers: TQ-600a-13-xii
        # angle: discrimination
        """A red timing run turns its own run red and is named on the timing notice; the hold passes; red correctness holds.

        Real timing workflow (run -> retry -> verdict) over a synthetic project with a failing and a passing
        `timing_ratio` test, a failing `manual` test and a failing unmarked test; its verdict file is piped into the
        notice job with a correctness notice already open. Wrong versions caught: the timing lane being a job of the
        correctness workflow (the hold's run goes red with it); the hold reading the newest run of any post-merge
        workflow; the failure reported nowhere; the timing failure written to the `post-merge-red` notice.
        """
        tests = {
            RATIO_FILE: RATIO_SOURCE,
            "unit_tests/test_manual_fails.py": manual_test("correctness_fails", "assert False"),
            "unit_tests/test_default_fails.py": plain_test("default_fails", "assert False"),
        }
        drive = drive_timing(self.svc.url, tests, run_number=5)
        self.assertEqual("success", drive.run.conclusion, drive.run.log_text()[-800:])
        self.assertEqual(("failure", "Verdict: red"), (drive.verdict.conclusion, drive.verdict.failed_step), drive.verdict.log_text()[-800:])
        self.assertIsNotNone(drive.file, "no verdict artifact on the red timing run")
        self.assertEqual(("timing", "red"), (drive.file["lane"], drive.file["verdict"]))
        self.assertEqual([FAILING_ID], drive.file["failing"])
        self.assertEqual(sorted([FAILING_ID, PASSING_ID]), drive.file["collected_ids"], "exactly the two timing_ratio tests are collected")

        timing_run = make_run(5, "failure")
        self.svc.timing_runs = [timing_run]
        self.svc.add_issue(50, title="correctness notice", body=old_description(900), labels=[RED_LABEL])
        applied = self.apply_timing(drive.file, timing_run["id"])
        self.assertEqual(0, applied.code, applied.log)
        self.assertEqual([("create", None)], self.svc.writes(), "a red timing run writes exactly one new notice and touches no other issue")
        (_, created), = self.svc.writes_of("create")
        self.assertEqual([TIMING_LABEL], created["labels"])
        self.assertIn(f"`{FAILING_ID}`", created["body"], "the failing timing test is named by node id")
        self.assertEqual({TIMING_LABEL}, set(self.listings()), "the notice job read no label but its own")

        self.svc.requests.clear()
        suite_green = make_run(7, "success", hours_ago=1)
        self.serve([suite_green])
        self.svc.timing_runs = [make_run(9, "failure")]
        held = self.evaluate()
        self.assertEqual("pass", held["state"], held["reason"])
        self.assertFalse([p for p in self.svc.paths_seen() if "timing" in p], self.svc.paths_seen())

        red = make_run(8, "failure")
        self.serve([suite_green, red], {red["id"]: RED_JOBS})
        self.assertEqual("red", self.evaluate()["state"], "control: a red correctness run holds")


class TestTq600a13XiiLaneEndings(TimingNoticeCase):
    def test_tq600a_13_xii_an_empty_timing_lane_concludes_red(self):
        # covers: TQ-600a-13-xii
        # angle: failure
        """No `timing_ratio` test at all: the verdict job fails at `Verdict: did not complete`, stage empty_selection."""
        drive = drive_timing(self.svc.url, {"unit_tests/test_only_default.py": plain_test("only_default")})
        self.assertEqual("success", drive.run.conclusion, drive.run.log_text()[-800:])
        self.assertEqual(("failure", "Verdict: did not complete"), (drive.verdict.conclusion, drive.verdict.failed_step), drive.verdict.log_text()[-800:])
        self.assertIsNotNone(drive.file)
        self.assertEqual(("timing", "did_not_complete", "empty_selection", []), (drive.file["lane"], drive.file["verdict"], drive.file["stage"], drive.file["failing"]))

    def test_tq600a_13_xii_a_timing_pass_on_retry_is_recorded_and_never_escalated(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        """A timing test that fails then passes on the fresh-machine retry: green, recorded, no notice, no flaky escalation.

        An open `post-merge-timing` notice is closed by that green run; nothing else is written anywhere.
        """
        sentinel = self.tmp / "flaky-sentinel"
        sentinel.unlink(missing_ok=True)
        body = f"import pathlib\n    p = pathlib.Path({str(sentinel)!r})\n    ok = p.exists()\n    p.write_text('x')\n    assert ok"
        tests = {RATIO_FILE: timing_test("ratio_slow", body)}
        drive = drive_timing(self.svc.url, tests, run_number=6)
        self.assertEqual(("success", "success"), (drive.retry.conclusion, drive.verdict.conclusion), drive.verdict.log_text()[-800:])
        self.assertIsNotNone(drive.file)
        self.assertEqual(("timing", "green", [FAILING_ID], []), (drive.file["lane"], drive.file["verdict"], drive.file["passed_on_retry"], drive.file["failing"]))

        timing_run = make_run(6, "success")
        self.svc.timing_runs = [timing_run]
        self.svc.add_issue(60, title="timing notice", body=old_description(906), labels=[TIMING_LABEL])
        applied = self.apply_timing(drive.file, timing_run["id"])
        self.assertEqual(0, applied.code, applied.log)
        self.assertEqual([("close", 60), ("comment", 60)], self.svc.writes(), "the green run closes the timing notice and writes nothing else")
        self.assertEqual([], self.svc.writes_of("create"), "a pass-on-retry opens no notice of its own")


if __name__ == "__main__":
    unittest.main()
