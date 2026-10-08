"""
Tests for TQ-600a-13-xix -- "A timing-ratio test in the default run stops making the
required pytest check flaky, by moving to the timing lane once that lane runs."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xix.yaml

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this).

1. pytest.ini registers a ``timing_ratio`` marker in its ``markers =`` key and
   the default selection becomes ``-m "not manual and not timing_ratio"``.
2. The two TQ-600a-11 wall-clock ratio tests carry ``@pytest.mark.timing_ratio``.
3. ``.github/workflows/post-merge-timing.yml`` (name ``Post-merge timing suite``) has
   one job whose pytest ``run:`` step collects ``-m timing_ratio`` and concludes red
   on a failing test AND on an empty selection (pytest exit 5).

Test 1 is made on node ids two REAL ``pytest --collect-only`` subprocesses produced,
reading the real pytest.ini -- never on a grep of the configuration. Test 2 executes
the workflow's pytest step verbatim with bash in a synthetic project.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RATIO_FILE = "unit_tests/ac_store/test_tq_600a_11.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-timing.yml"
RATIO_TESTS = (
    "TestTq600a11ParserSpeed::test_tq600a_11_store_sweep_is_at_least_five_times_faster_than_the_pure_python_parser",
    "TestTq600a11AgentCardWalk::test_tq600a_11_the_agent_card_store_walk_beats_a_fifth_of_its_same_sitting_pure_python_baseline",
)


def _collect(extra_args):
    """Run a real scoped ``pytest --collect-only -q``; return (returncode, node ids, output text)."""
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONPATH"] = str(REPO_ROOT)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *extra_args, RATIO_FILE],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        message = f"collect-only subprocess could not run: {exc}"
        raise AssertionError(message) from exc
    ids = [ln.strip() for ln in proc.stdout.splitlines() if "::" in ln and not ln.startswith(("=", " "))]
    return proc.returncode, ids, proc.stdout + proc.stderr


def _has(ids, tail):
    return any(i.endswith(tail) for i in ids)


def _load_workflow():
    try:
        text = WORKFLOW.read_text(encoding="utf-8")
    except OSError as exc:
        message = f"{WORKFLOW} is missing or unreadable: {exc}"
        raise AssertionError(message) from exc
    return yaml.safe_load(text)


def _pytest_step_script(workflow):
    jobs = workflow.get("jobs") or {}
    assert len(jobs) == 1, f"expected exactly one job, found {sorted(jobs)}"
    (job,) = jobs.values()
    scripts = [s["run"] for s in job.get("steps", []) if isinstance(s.get("run"), str) and "pytest" in s["run"]]
    assert len(scripts) == 1, f"expected exactly one pytest run step, found {len(scripts)}"
    return scripts[0]


def _marker_line():
    """The repository's own ``timing_ratio`` marker registration line, as written in pytest.ini."""
    for line in (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("timing_ratio:"):
            return line.strip()
    message = "pytest.ini registers no `timing_ratio` marker line to copy"
    raise AssertionError(message)


_MARKED = "import pytest\n\n\n@pytest.mark.timing_ratio\ndef test_ratio():\n    assert {outcome}\n"
_UNMARKED = (
    "import os\n\n\ndef test_plain():\n"
    "    open(os.environ['SENTINEL'], 'w').write('ran')\n"
)


class TestTq600a13XixTimingLane(unittest.TestCase):
    def test_tq600a_13_xix_ratio_tests_leave_the_default_run_only_into_the_timing_lane(self):
        # covers: TQ-600a-13-xix
        # angle: real_artifact
        """Each named ratio test is in the timing collection only; sibling tests stay in the default one."""
        _, default_ids, default_out = _collect([])
        lane_rc, lane_ids, lane_out = _collect(["-m", "timing_ratio"])

        self.assertGreater(len(default_ids), 0, f"default collection is empty:\n{default_out}")
        self.assertTrue(
            any("TestTq600a11CParserSeam" in i for i in default_ids),
            f"non-ratio tests of the file must stay in the default run: {default_ids}",
        )
        self.assertEqual(lane_rc, 0, f"`-m timing_ratio` collection failed:\n{lane_out}")
        for name in RATIO_TESTS:
            self.assertFalse(_has(default_ids, name), f"{name} still in the DEFAULT run")
            self.assertTrue(_has(lane_ids, name), f"{name} is not collected by the timing lane:\n{lane_out}")
        self.assertEqual(len(lane_ids), len(RATIO_TESTS), f"timing lane collected more than the ratio tests: {lane_ids}")


class TestTq600a13XixTimingWorkflow(unittest.TestCase):
    def _run_step(self, script, tests_body, unit_body):
        """Execute the workflow's pytest step verbatim in a synthetic project; return (rc, sentinel_ran, out)."""
        marker = _marker_line()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            (root / "tests").mkdir(parents=True)
            (root / "unit_tests").mkdir()
            (root / "pytest.ini").write_text(
                f"[pytest]\nstrict_markers = true\nmarkers =\n    {marker}\n", encoding="utf-8"
            )
            if tests_body is not None:
                (root / "tests" / "test_marked.py").write_text(tests_body, encoding="utf-8")
            (root / "unit_tests" / "test_unmarked.py").write_text(unit_body, encoding="utf-8")
            shim = Path(tmp) / "bin"
            shim.mkdir()
            (shim / "python").symlink_to(sys.executable)
            (shim / "python3").symlink_to(sys.executable)
            sentinel = Path(tmp) / "sentinel"
            env = dict(os.environ)
            env.pop("PYTEST_ADDOPTS", None)
            env.pop("PYTEST_CURRENT_TEST", None)
            env["PATH"] = f"{shim}{os.pathsep}{env.get('PATH', '')}"
            env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
            env["AC_ENFORCE_STRICT"] = "1"
            env["SENTINEL"] = str(sentinel)
            try:
                proc = subprocess.run(
                    ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
                    cwd=str(root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                message = f"workflow step could not run: {exc}"
                raise AssertionError(message) from exc
            return proc.returncode, sentinel.exists(), proc.stdout + proc.stderr

    def test_tq600a_13_xix_the_timing_workflow_goes_red_on_a_failing_ratio_test(self):
        # covers: TQ-600a-13-xix
        # angle: seam
        """The pytest step is red on a failing marked test and on an empty lane, green on a passing one."""
        workflow = _load_workflow()
        script = _pytest_step_script(workflow)

        with self.subTest(case="marked test fails"):
            rc, _, out = self._run_step(script, _MARKED.format(outcome="False"), _UNMARKED)
            self.assertNotEqual(rc, 0, f"a failing timing_ratio test left the step green:\n{out}")
            self.assertIn("1 failed", out)

        with self.subTest(case="marked test passes"):
            rc, ran, out = self._run_step(script, _MARKED.format(outcome="True"), _UNMARKED)
            self.assertEqual(rc, 0, f"a passing timing_ratio test made the step red:\n{out}")
            self.assertIn("1 passed", out)
            self.assertFalse(ran, "the unmarked test ran: the step used the default selection")

        with self.subTest(case="no marked tests"):
            rc, ran, out = self._run_step(script, None, _UNMARKED)
            self.assertNotEqual(rc, 0, f"an empty timing lane concluded green:\n{out}")
            self.assertFalse(ran, "the unmarked test ran in the timing lane")

    def test_tq600a_13_xix_the_workflow_triggers_and_permissions(self):
        # covers: TQ-600a-13-xix
        # angle: criterion
        """Structural by necessity: a schedule cannot be executed offline."""
        workflow = _load_workflow()
        self.assertEqual(workflow.get("name"), "Post-merge timing suite")
        triggers = workflow.get(True, workflow.get("on"))  # PyYAML parses the key `on` as True
        self.assertIsInstance(triggers, dict)
        self.assertIn("main", (triggers.get("push") or {}).get("branches", []))
        self.assertIn("workflow_dispatch", triggers)
        crons = [entry["cron"] for entry in triggers.get("schedule", [])]
        self.assertTrue(crons, "no schedule heartbeat")
        hours = set()
        for cron in crons:
            field = cron.split()[1]
            if field == "*":
                hours.update(range(24))
            elif field.startswith("*/"):
                hours.update(range(0, 24, int(field[2:])))
            else:
                hours.update(int(h) for h in field.split(","))
        ordered = sorted(hours)
        gaps = [(b - a) for a, b in zip(ordered, ordered[1:])] + [ordered[0] + 24 - ordered[-1]]
        self.assertLessEqual(max(gaps), 12, f"heartbeat is less often than every 12 hours: {crons}")
        self.assertEqual(workflow.get("permissions"), {})
        for job in workflow["jobs"].values():
            self.assertNotIn(job.get("continue-on-error"), (True, "true"))
            for step in job.get("steps", []):
                self.assertNotIn(step.get("continue-on-error"), (True, "true"))


if __name__ == "__main__":
    unittest.main()
