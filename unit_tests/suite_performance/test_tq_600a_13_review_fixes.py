"""
Regression tests for the independent review of TQ-600a-13-i / -ii (H-1, M-1..M-5).

Each test failed on the code as first delivered:

* H-1  a verdict must not be GREEN when the lane did not really run: all tests skipped, a pytest.exit(),
       an interrupt, an internal error, or a truncated session. Real child pytest sessions are used
       for exit / interrupt / all-skipped; the report plugin must record the session's exit status.
* M-1  the exclusion gate must not pass vacuously: a tags-only or paths-filtered push is not "every
       merge to main"; a job or step ``if:`` that is not trivially true is refused; a wrapped lane step
       (``post_merge_suite.py run``, exits 0 by design) needs a downstream job that fails on a red verdict.
* M-2  a small local marker-expression evaluator (no private pytest import), checked against real pytest.
* M-4  a missing lane report is logged at WARNING.
* M-5  fail-then-pass and failing ids reach the step summary, so a green run is not silent about them.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.ci import post_merge_suite as suite
from scripts.suite_performance import check_exclusion_compensation as gate

from ._workflow_jobs import REPO_ROOT
from .test_tq_600a_13_i import _CADENCE_ON, _make_project, _run_gate, _write

_INI = "[pytest]\nstrict_markers = true\nmarkers =\n    manual: m\n    timing_ratio: t\n"


def _child_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "GITHUB_"))}
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


def _real_lane_verdict(test_source):
    """Run the lane wrapper over a real child pytest session; return (verdict file dict, wrapper rc)."""
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        _write(root / "pytest.ini", _INI)
        _write(root / "tests" / "test_lane.py", test_source)
        (root / "scripts").symlink_to(REPO_ROOT / "scripts", target_is_directory=True)
        report = root / "report.json"
        argv = [sys.executable, "scripts/ci/post_merge_suite.py", "run", "--report", str(report)]
        argv += ["--failures", str(root / "f.txt"), "--", "python", "-m", "pytest", "-p", "no:cacheprovider"]
        proc = subprocess.run(argv, cwd=root, env=_child_env(), capture_output=True, text=True, timeout=120, check=False)
        data = suite.read_report(report)
        if data is None:
            detail = f"no report produced:\n{proc.stdout}{proc.stderr}"
            raise AssertionError(detail)
        return suite.build_verdict_file(data, None, {}), proc.returncode


def _report(results, exitstatus=0, expected=None):
    return {"runner": "r", "exitstatus": exitstatus, "expected": len(results) if expected is None else expected, "results": results}


class TestH1VerdictNeverGreenWhenTheLaneDidNotRun(unittest.TestCase):
    def test_all_skipped_is_did_not_complete(self):
        # covers: TQ-600a-13-ii
        verdict = suite.build_verdict_file(_report({"t::a": "skipped", "t::b": "skipped"}), None, {})
        self.assertEqual("did_not_complete", verdict["verdict"])
        self.assertEqual("nothing_passed", verdict["stage"])
        self.assertEqual(2, verdict["skipped"])

    def test_a_majority_of_skips_is_did_not_complete_but_a_minority_is_green(self):
        # covers: TQ-600a-13-ii
        mostly = {"t::a": "passed", "t::b": "skipped", "t::c": "skipped"}
        verdict = suite.build_verdict_file(_report(mostly), None, {})
        self.assertEqual(("did_not_complete", "mostly_skipped"), (verdict["verdict"], verdict["stage"]))
        some = {"t::a": "passed", "t::b": "passed", "t::c": "skipped"}
        verdict = suite.build_verdict_file(_report(some), None, {})
        self.assertEqual(("green", None, 1), (verdict["verdict"], verdict["stage"], verdict["skipped"]))

    def test_an_aborted_session_or_a_truncated_one_or_an_inconsistent_exit_is_did_not_complete(self):
        # covers: TQ-600a-13-ii
        passed = {"t::a": "passed"}
        for status in (2, 3, 4):
            with self.subTest(exitstatus=status):
                verdict = suite.build_verdict_file(_report(passed, exitstatus=status), None, {})
                self.assertEqual(("did_not_complete", "pytest_aborted"), (verdict["verdict"], verdict["stage"]))
        truncated = suite.build_verdict_file(_report(passed, expected=3), None, {})
        self.assertEqual(("did_not_complete", "truncated"), (truncated["verdict"], truncated["stage"]))
        odd = suite.build_verdict_file(_report(passed, exitstatus=1), None, {})
        self.assertEqual(("did_not_complete", "exit_status_without_failures"), (odd["verdict"], odd["stage"]))
        failed = suite.build_verdict_file(_report({"t::a": "passed", "t::b": "failed"}, exitstatus=1), None, {})
        self.assertEqual(("red", None), (failed["verdict"], failed["stage"]))

    def test_real_sessions_pytest_exit_interrupt_and_all_skipped_never_read_green(self):
        # covers: TQ-600a-13-ii
        sources = {
            "exit": "import pytest\n\n\ndef test_one():\n    pass\n\n\ndef test_two():\n    pytest.exit('boom')\n\n\ndef test_three():\n    pass\n",
            "interrupt": "def test_one():\n    pass\n\n\ndef test_two():\n    raise KeyboardInterrupt\n\n\ndef test_three():\n    pass\n",
            "all_skipped": "import pytest\n\n\n@pytest.mark.skip('no prerequisite')\ndef test_one():\n    pass\n\n\n@pytest.mark.skip('no prerequisite')\ndef test_two():\n    pass\n",
        }
        for name, source in sources.items():
            with self.subTest(case=name):
                verdict, rc = _real_lane_verdict(source)
                self.assertEqual(0, rc, "the run step reports data and exits zero")
                self.assertEqual("did_not_complete", verdict["verdict"], verdict)
        control, _rc = _real_lane_verdict("def test_one():\n    pass\n\n\ndef test_two():\n    pass\n")
        self.assertEqual(("green", None), (control["verdict"], control["stage"]))


def _write_doc(root, name, doc):
    _write(root / ".github" / "workflows" / f"{name}.yml", yaml.safe_dump(doc, sort_keys=False))


def _opt_in_doc(on, run, job_extra=None, step_extra=None, extra_jobs=None):
    jobs = {"lane": {"runs-on": "ubuntu-latest", **(job_extra or {}), "steps": [{"run": run, **(step_extra or {})}]}}
    jobs.update(extra_jobs or {})
    return {"name": "x", "on": on, "jobs": jobs}


_PLAIN = "python -m pytest -m manual -q"
_WRAPPED = "python scripts/ci/post_merge_suite.py run --report r.json --failures f.txt -- python -m pytest -m manual"


class TestM1TheGateDoesNotPassVacuously(unittest.TestCase):
    def _gate(self, doc):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _make_project(root, deselect=True)
            _write_doc(root, "lane", doc)
            return _run_gate(root)

    def assert_refused(self, doc):
        rc, out = self._gate(doc)
        self.assertNotEqual(0, rc, out)
        self.assertIn("manual", out)

    def test_a_push_that_is_not_every_merge_to_main_is_refused(self):
        # covers: TQ-600a-13-i
        self.assert_refused(_opt_in_doc({"push": {"tags": ["v*"]}}, _PLAIN))
        self.assert_refused(_opt_in_doc({"push": {"paths": ["docs/**"]}}, _PLAIN))
        self.assert_refused(_opt_in_doc({"push": {"branches": ["main"], "paths": ["src/**"]}}, _PLAIN))
        self.assert_refused(_opt_in_doc({"push": {"branches": ["release"]}}, _PLAIN))
        self.assert_refused(_opt_in_doc({"push": {"branches-ignore": ["main"]}}, _PLAIN))
        for accepted in ({"push": {"branches": ["main"]}}, {"push": None}, {"push": {"branches": ["**"]}}):
            with self.subTest(on=accepted):
                rc, out = self._gate(_opt_in_doc(accepted, _PLAIN))
                self.assertEqual(0, rc, out)

    def test_a_conditional_job_or_step_is_refused_unless_trivially_true(self):
        # covers: TQ-600a-13-i
        for condition in ("false", "github.event_name == 'workflow_dispatch'", "${{ github.event_name == 'workflow_dispatch' }}"):
            with self.subTest(condition=condition):
                self.assert_refused(_opt_in_doc(_CADENCE_ON, _PLAIN, job_extra={"if": condition}))
                self.assert_refused(_opt_in_doc(_CADENCE_ON, _PLAIN, step_extra={"if": condition}))
        for condition in ("always()", "success()", "${{ always() }}"):
            with self.subTest(condition=condition):
                rc, out = self._gate(_opt_in_doc(_CADENCE_ON, _PLAIN, step_extra={"if": condition}))
                self.assertEqual(0, rc, out)

    def test_a_wrapped_lane_step_needs_a_downstream_job_that_fails_on_red(self):
        # covers: TQ-600a-13-i
        def verdict_job(step_extra=None, needs="lane"):
            step = {"run": "python scripts/ci/post_merge_suite.py exit-status --verdict-file v.json", **(step_extra or {})}
            return {"verdict": {"needs": needs, "if": "always()", "runs-on": "ubuntu-latest", "steps": [step]}}

        self.assert_refused(_opt_in_doc(_CADENCE_ON, _WRAPPED))
        self.assert_refused(_opt_in_doc(_CADENCE_ON, _WRAPPED, extra_jobs=verdict_job(needs="other")))
        self.assert_refused(_opt_in_doc(_CADENCE_ON, _WRAPPED, extra_jobs=verdict_job({"continue-on-error": True})))
        rc, out = self._gate(_opt_in_doc(_CADENCE_ON, _WRAPPED, extra_jobs=verdict_job()))
        self.assertEqual(0, rc, out)
        rc, out = self._gate(_opt_in_doc(_CADENCE_ON, _WRAPPED, extra_jobs=verdict_job(needs=["lane"])))
        self.assertEqual(0, rc, out)


class TestM2MarkerExpressionEvaluator(unittest.TestCase):
    EXPRESSIONS = (
        "manual",
        "manual and not timing_ratio",
        "not manual and not timing_ratio",
        "manual or timing_ratio",
        "not (manual or timing_ratio)",
        "(manual and timing_ratio) or not manual",
    )
    TESTS = {
        "test_plain": (),
        "test_manual": ("manual",),
        "test_timing": ("timing_ratio",),
        "test_both": ("manual", "timing_ratio"),
    }

    def test_it_agrees_with_real_pytest(self):
        # covers: TQ-600a-13-i
        lines = ["import pytest\n"]
        for name, marks in self.TESTS.items():
            lines += [f"@pytest.mark.{m}" for m in marks] + [f"def {name}():\n    pass\n"]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _write(root / "pytest.ini", _INI)
            _write(root / "test_m.py", "\n".join(lines))
            for expression in self.EXPRESSIONS:
                with self.subTest(expression=expression):
                    argv = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-m", expression]
                    proc = subprocess.run(argv, cwd=root, env=_child_env(), capture_output=True, text=True, timeout=60, check=False)
                    real = {ln.split("::")[1] for ln in proc.stdout.splitlines() if "::" in ln}
                    mine = {n for n, marks in self.TESTS.items() if gate.evaluate_marker_expression(expression, set(marks))}
                    self.assertEqual(real, mine)

    def test_anything_else_is_refused_loudly(self):
        # covers: TQ-600a-13-i
        for bad in ("", "manual and", "manual && x", "manual timing_ratio", "(manual", "manual)", "k=v", "manual or and", "-m"):
            with self.subTest(expression=bad), self.assertRaises(gate.MarkerExpressionError):
                gate.evaluate_marker_expression(bad, {"manual"})


class TestM4M5ReportsAndSummary(unittest.TestCase):
    def test_a_missing_report_is_logged_at_warning(self):
        # covers: TQ-600a-13-ii
        with tempfile.TemporaryDirectory() as raw, self.assertLogs("post_merge_suite", level="WARNING"):
            self.assertIsNone(suite.read_report(Path(raw) / "absent.json"))

    def _verdict_cli(self, summary_path):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            first = _report({"t::a": "passed", "t::b": "failed", "t::c": "failed"}, exitstatus=1)
            retry = _report({"t::b": "passed", "t::c": "failed"}, exitstatus=1)
            for rel, data in (("first-run-report/first-run-report.json", first), ("retry-report/retry-report.json", retry)):
                _write(base / "artifacts" / rel, json.dumps(data))
            env = {**_child_env(), "GITHUB_STEP_SUMMARY": str(summary_path(base)), "GITHUB_OUTPUT": str(base / "out.txt")}
            argv = [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "post_merge_suite.py"), "verdict"]
            argv += ["--artifacts", str(base / "artifacts"), "--output", str(base / "v.json")]
            proc = subprocess.run(argv, cwd=base, env=env, capture_output=True, text=True, timeout=60, check=False)
            return proc.returncode, summary_path(base)

    def test_passed_on_retry_and_failing_ids_reach_the_step_summary(self):
        # covers: TQ-600a-13-ii
        with tempfile.TemporaryDirectory() as raw:
            summary = Path(raw) / "summary.md"
            rc, _path = self._verdict_cli(lambda _base: summary)
            self.assertEqual(0, rc)
            text = summary.read_text(encoding="utf-8")
            self.assertIn("t::b", text)
            self.assertIn("t::c", text)
            self.assertNotIn("t::a", text)
            self.assertEqual(2, len([ln for ln in text.splitlines() if ln.strip()]))

    def test_an_unwritable_summary_never_changes_the_verdict_step(self):
        # covers: TQ-600a-13-ii
        rc, _path = self._verdict_cli(lambda base: base)  # a directory: not writable as a file
        self.assertEqual(0, rc)


class TestGateRealRepository(unittest.TestCase):
    def test_the_real_gate_still_accepts_this_repository(self):
        # covers: TQ-600a-13-i
        rc, out = _run_gate(REPO_ROOT)
        self.assertEqual(0, rc, out)


if __name__ == "__main__":
    unittest.main()
