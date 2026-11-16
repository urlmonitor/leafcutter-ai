"""
MODULE: unit_tests/ac_store/test_tq_100b_1_iv_xfail_convention.py
GOAL: Prove TQ-100b-1-iv: a failure the AC enforcement plugin masks is reported in
    pytest's own expected-failure form (outcome "skipped" + wasxfail), so the
    terminal, JUnit XML, pytest-xdist, --maxfail and every reader of a test run in
    this package classify it as an expected failure.
BUSINESS CONTEXT: The plugin used to set ``report.outcome = "xfailed"``, a value
    pytest does not define. ``passed``, ``failed`` and ``skipped`` were then all
    False, so pytest printed the failure letter F for a masked test, JUnit wrote it
    as a plain passing testcase (and a tests total one short), and the post-merge
    lane report read it as passed.
ARCHITECTURE: Every assertion is made on real pytest sessions run as subprocesses
    in a temp project (its own pytest.ini, a synthetic AC store, the plugin loaded
    with ``-p``). A small probe plugin written into the temp project records, for
    each call report, the outcome, wasxfail, the status pytest's own
    ``pytest_report_teststatus`` hook gives it (the source of the progress letter
    and verbose word) and the post-merge fix proof's ``_distinct_status`` label.
    AC_ENFORCE_STRICT is removed from the child environment for masked runs (CI
    sets it in the parent) and set for the strict run. The fast lane's
    red-baseline classification is read in a child interpreter so its sys.path
    set-up never leaks into this process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.ac_store.pytest_outcome_reader import parse_pytest_outcomes

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RED_BASELINE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
_TODO_AC = "ZZ-TODO-1"
_DONE_AC = "ZZ-DONE-1"
_MASKED = "test_probe.py::test_a_masked"
_NATIVE = "test_native.py::test_native_xfail"

# f-string placeholders keep a literal coverage tag out of this file's own source.
_PROBE_TESTS = f'''
def test_a_masked():
    # covers: {_TODO_AC}
    assert False, "not-done AC failure: masked by default"


def test_b_pass():
    assert True


def test_c_done_fail():
    # covers: {_DONE_AC}
    assert False, "done AC failure: never masked"


def test_d_pass():
    assert True
'''

_NATIVE_TESTS = '''
import pytest


@pytest.mark.xfail(reason="native xfail")
def test_native_xfail():
    assert False
'''

_RECORDER_PLUGIN = '''
import json
import os

from scripts.ci.post_merge_fix_proof import _distinct_status

_SEEN = {}


def pytest_runtest_logreport(report):
    if report.when != "call":
        return
    config = _CONFIG[0]
    status = config.hook.pytest_report_teststatus(report=report, config=config)
    _SEEN[report.nodeid] = {
        "outcome": report.outcome,
        "wasxfail": getattr(report, "wasxfail", None),
        "teststatus": list(status),
        "fix_proof": _distinct_status(report),
    }


_CONFIG = []


def pytest_configure(config):
    _CONFIG.append(config)


def pytest_sessionfinish(session, exitstatus):
    if hasattr(session.config, "workerinput"):
        return
    with open(os.environ["TQ100B1IV_RECORD"], "w", encoding="utf-8") as handle:
        json.dump(_SEEN, handle)
'''


class _Project:
    """A temp pytest project with the probe tests, a synthetic store and the recorder plugin."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        files = {
            "pytest.ini": "[pytest]\n",
            "test_probe.py": _PROBE_TESTS,
            "test_native.py": _NATIVE_TESTS,
            "tq100b1iv_recorder.py": _RECORDER_PLUGIN,
            "store/todo.yaml": f'id: "{_TODO_AC}"\nwork_status: todo\ncomponent: x\n',
            "store/done.yaml": f'id: "{_DONE_AC}"\nwork_status: done\ncomponent: x\n',
        }
        for rel, body in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

    def close(self) -> None:
        """Remove the temp project."""
        self._tmp.cleanup()

    def run(self, *args: str, strict: bool = False, name: str = "run") -> tuple[subprocess.CompletedProcess[str], dict]:
        """Run one real pytest session; return the process and the recorder's per-test record."""
        record = self.root / f"{name}.record.json"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "AC_ENFORCE_STRICT"))}
        env["PYTHONPATH"] = os.pathsep.join([str(_REPO_ROOT), str(self.root)])
        env["LEAFCUTTER_AC_STORE_ROOT"] = str(self.root / "store")
        env["TQ100B1IV_RECORD"] = str(record)
        if strict:
            env["AC_ENFORCE_STRICT"] = "1"
        cmd = [
            sys.executable, "-m", "pytest", "-c", str(self.root / "pytest.ini"), "--rootdir", str(self.root),
            "-p", "scripts.ac_store.pytest_ac_enforcement", "-p", "tq100b1iv_recorder",
            "-p", "no:cacheprovider", "--color=no", "--tb=no", *args,
        ]
        proc = subprocess.run(cmd, cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=180)
        recorded = json.loads(record.read_text(encoding="utf-8")) if record.is_file() else {}
        return proc, recorded

    def junit_case(self, xml_name: str, test_name: str) -> tuple[ET.Element, ET.Element]:
        """Return (testsuite, testcase) for *test_name* in the JUnit file *xml_name*."""
        suite = ET.parse(self.root / xml_name).getroot().find("testsuite")
        assert suite is not None, f"no testsuite in {xml_name}"
        for case in suite.iter("testcase"):
            if case.get("name") == test_name:
                return suite, case
        message = f"no testcase {test_name} in {xml_name}"
        raise AssertionError(message)


def _red_baseline_bucket(token: str) -> str:
    """The fast lane's red-baseline bucket for *token*, read in a child interpreter (no sys.path leak here)."""
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from _fl_red_baseline_support import _classify_outcome_bucket; print(_classify_outcome_bucket(sys.argv[2]))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(_RED_BASELINE_DIR), token],
        cwd=_REPO_ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    if proc.returncode != 0:
        message = f"red-baseline reader failed: {proc.stderr}"
        raise AssertionError(message)
    return proc.stdout.strip()


class _ProjectCase(unittest.TestCase):
    """Shares one temp project per test class."""

    project: _Project

    @classmethod
    def setUpClass(cls) -> None:
        cls.project = _Project()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.project.close()

    def assert_masked_as_xfail(self, recorded: dict, out: str) -> None:
        """The masked test's report is pytest's xfail shape and pytest itself labels it XFAIL."""
        self.assertIn(_MASKED, recorded, f"masked test never reported\n{out}")
        entry = recorded[_MASKED]
        self.assertEqual("skipped", entry["outcome"], f"outcome is not pytest's convention\n{out}")
        self.assertIn(_TODO_AC, entry["wasxfail"] or "", f"wasxfail does not carry the masking reason\n{out}")
        self.assertEqual(["xfailed", "x", "XFAIL"], entry["teststatus"], f"pytest does not label it XFAIL\n{out}")


class TestTerminalAndJunit(_ProjectCase):
    """The terminal and JUnit XML read the masked failure as an expected failure."""

    def test_tq_100b_1_iv_masked_failure_reads_as_xfail_in_terminal_and_junit(self) -> None:
        # covers: TQ-100b-1-iv
        proc, recorded = self.project.run("-rA", "-v", "test_probe.py", "--junitxml", "serial.xml", name="serial")
        out = proc.stdout + proc.stderr
        self.assert_masked_as_xfail(recorded, out)
        self.assertRegex(out, r"::test_a_masked XFAIL\b", f"verbose word is not XFAIL\n{out}")
        self.assertNotIn("XFAILED", out, f"a non-pytest verbose word is printed\n{out}")
        self.assertIn("1 failed, 2 passed, 1 xfailed", out, f"summary counts are wrong\n{out}")
        self.assertIn("AC-ENFORCEMENT [MASKED FAILURE]", out, f"masking is no longer loud\n{out}")
        suite, case = self.project.junit_case("serial.xml", "test_a_masked")
        skipped = case.find("skipped")
        self.assertIsNotNone(skipped, f"JUnit records the masked failure as a pass\n{out}")
        assert skipped is not None
        self.assertEqual("pytest.xfail", skipped.get("type"))
        self.assertIn(_TODO_AC, skipped.get("message", ""))
        self.assertEqual(len(list(suite.iter("testcase"))), int(suite.get("tests", "-1")))
        self.assertEqual("1", suite.get("skipped"))
        self.assertEqual("1", suite.get("failures"))

        quiet, quiet_recorded = self.project.run("-q", "test_probe.py", "-k", "not done_fail", name="quiet")
        quiet_out = quiet.stdout + quiet.stderr
        self.assertEqual(0, quiet.returncode, f"masked failure changed the exit status\n{quiet_out}")
        self.assertRegex(quiet_out, r"(?m)^x\.\.\s+\[100%\]$", f"progress letter is not x\n{quiet_out}")
        self.assert_masked_as_xfail(quiet_recorded, quiet_out)


class TestXdistAndMaxfail(_ProjectCase):
    """xdist and --maxfail treat the masked failure as an expected failure."""

    def test_tq_100b_1_iv_masked_failure_reads_as_xfail_under_xdist_and_maxfail(self) -> None:
        # covers: TQ-100b-1-iv
        proc, recorded = self.project.run("-rA", "-v", "-n", "2", "test_probe.py", "--junitxml", "xdist.xml", name="xdist")
        out = proc.stdout + proc.stderr
        self.assert_masked_as_xfail(recorded, out)
        self.assertRegex(out, r"\bXFAIL\b[^\n]*::test_a_masked", f"xdist verbose word is not XFAIL\n{out}")
        self.assertIn("1 failed, 2 passed, 1 xfailed", out, f"xdist summary counts are wrong\n{out}")
        suite, case = self.project.junit_case("xdist.xml", "test_a_masked")
        skipped = case.find("skipped")
        self.assertIsNotNone(skipped, f"xdist JUnit records the masked failure as a pass\n{out}")
        assert skipped is not None
        self.assertEqual("pytest.xfail", skipped.get("type"))
        self.assertEqual(len(list(suite.iter("testcase"))), int(suite.get("tests", "-1")))

        stop, stop_recorded = self.project.run("-p", "no:xdist", "--maxfail=1", "test_probe.py", name="maxfail")
        stop_out = stop.stdout + stop.stderr
        self.assert_masked_as_xfail(stop_recorded, stop_out)
        self.assertIn("test_probe.py::test_b_pass", stop_recorded, f"--maxfail counted the masked failure\n{stop_out}")
        self.assertIn("test_probe.py::test_c_done_fail", stop_recorded, f"run stopped before the real failure\n{stop_out}")
        self.assertNotIn("test_probe.py::test_d_pass", stop_recorded, f"--maxfail=1 did not stop at the real failure\n{stop_out}")


class TestReadersKeepTheirVerdicts(_ProjectCase):
    """Each reader of a test run in this package gives the verdict it gave before."""

    def test_tq_100b_1_iv_every_reader_gives_its_previous_verdict(self) -> None:
        # covers: TQ-100b-1-iv
        proc, recorded = self.project.run("-v", "test_probe.py", name="readers")
        out = proc.stdout + proc.stderr
        outcomes = parse_pytest_outcomes(proc.stdout, proc.returncode)
        self.assertEqual("XFAIL", outcomes.get(_MASKED), f"shared -v reader misreads the masked test\n{out}")
        self.assertEqual("FAILED", outcomes.get("test_probe.py::test_c_done_fail"))
        self.assertEqual("red", _red_baseline_bucket(outcomes[_MASKED]), "red-baseline gate stopped counting it red")
        self.assertEqual("xfailed", recorded[_MASKED]["fix_proof"], f"fix proof mislabels the masked test\n{out}")
        self.assertEqual("failed", recorded["test_probe.py::test_c_done_fail"]["fix_proof"])

        strict, strict_recorded = self.project.run("-v", "test_probe.py", "--junitxml", "strict.xml", strict=True, name="strict")
        strict_out = strict.stdout + strict.stderr
        self.assertEqual("FAILED", parse_pytest_outcomes(strict.stdout, strict.returncode).get(_MASKED), strict_out)
        self.assertEqual("failed", strict_recorded[_MASKED]["outcome"], strict_out)
        self.assertIsNotNone(self.project.junit_case("strict.xml", "test_a_masked")[1].find("failure"), strict_out)
        self.assertIn("2 failed, 2 passed", strict_out)


class TestLaneReport(_ProjectCase):
    """The post-merge lane report records the masked failure as it records pytest's own xfail."""

    def test_tq_100b_1_iv_lane_report_records_masked_failure_as_skipped_like_native_xfail(self) -> None:
        # covers: TQ-100b-1-iv
        lane = self.project.root / "lane.json"
        proc, _ = self.project.run(
            "-q", "-p", "scripts.ci._lane_report_plugin", "--lane-report", str(lane),
            "test_probe.py", "test_native.py", name="lane",
        )
        out = proc.stdout + proc.stderr
        results = json.loads(lane.read_text(encoding="utf-8"))["results"]
        self.assertEqual("skipped", results.get(_NATIVE), f"native xfail baseline changed\n{out}")
        self.assertEqual(results.get(_NATIVE), results.get(_MASKED), f"lane report misreads the masked failure\n{out}")
        self.assertEqual("failed", results.get("test_probe.py::test_c_done_fail"))


if __name__ == "__main__":
    unittest.main()
