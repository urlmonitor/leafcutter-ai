"""
Tests for TQ-600a-13-i -- "Choosing to exclude a test from the default run does
not quietly delete it."

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-i.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this).

Background: TQ-600a-13 already landed a REAL deselection (pytest.ini addopts
``-m "not manual"`` plus the auto-marking plugin). Nothing invokes the opt-in
(``-m manual``) on any cadence, which is exactly the state this record forbids.

1. REFUSAL GATE -- a CLI at ``scripts/suite_performance/check_exclusion_compensation.py``:
       python scripts/suite_performance/check_exclusion_compensation.py [--root <project>]
   ``--root`` defaults to the current directory. It reads ``<root>/pytest.ini`` and
   ``<root>/.github/workflows/*.yml``. Exit 0 = accepted, non-zero = refused.
   * No deselection in pytest.ini addopts (no ``-m "not ..."``) -> accepted (vacuous).
   * A deselection present -> accepted ONLY when an INVOKED opt-in exists.
   * A refusal prints (stdout or stderr) text naming the deselected marker (``manual``)
     and the word ``invoked`` (what is missing), never just a count.
2. "INVOKED opt-in" means ALL of: a workflow job with a ``run:`` step whose pytest command
   carries an ``-m <expression>``; the workflow is triggered automatically (``push`` to
   main, or ``schedule``) -- ``workflow_dispatch`` alone is a button, not a cadence; and
   the failure is not swallowed (no ``continue-on-error`` on the job or step, no
   ``|| true`` on the command). A job that is merely DEFINED is not invoked.
3. The correctness lane workflow is ``.github/workflows/post-merge-suite.yml`` (named by
   TQ-600a-13-vi); the timing lane is ``.github/workflows/post-merge-timing.yml`` (named by
   TQ-600a-13-xix, PR #1060). Each carries a ``run:`` step whose pytest command has an
   ``-m`` expression and contains NO ``${{ }}`` expression (so it can be executed verbatim
   offline). The first such step in the workflow is the lane's pytest step.
   RECONCILED WITH TQ-600a-13-ii (the correctness lane): that first step is in the `run` job, which
   exits ZERO whenever it produced a report; a separate `retry` job re-executes failures on a fresh
   runner; the `verdict` job's exit status is the run's conclusion. So for the correctness lane the
   job that must go red on a failing excluded test is `verdict` (see TQ-600a-13-ii's contract:
   jobs `run`/`retry`/`verdict`, artifact `post-merge-verdict`, file `post-merge-verdict.json` with
   `collected` and `failing`). The lane step may be a wrapper such as
   ``python scripts/ci/post_merge_suite.py run -- python -m pytest -m "manual and not timing_ratio" tests/ unit_tests/``
   so the literal pytest ``-m`` stays visible here. The timing lane (post-merge-timing.yml, shipped by
   TQ-600a-13-xix as one pytest step) has the same run / retry / verdict shape since TQ-600a-13-xii.
4. ``.github/workflows/ci.yml`` (a ``pull_request`` workflow) has a step whose ``run:``
   invokes ``check_exclusion_compensation`` with no ``${{ }}`` expression, relative to the
   repository root, with ``--root`` defaulting to cwd -- this is what makes the refusal
   fire before a deselection can merge.

Every assertion about collections is made on node ids a REAL ``pytest --collect-only``
subprocess produced; every workflow ``run:`` step is EXECUTED verbatim in a synthetic
project; workflow fixtures come from ``yaml.safe_dump`` (never hand-typed YAML). Only
triggers and ``continue-on-error`` (GitHub-side semantics that cannot run offline) are
read structurally.

DEFERRED (written once TQ-600a-13-vi / -xii exist; this branch carries them serially):
 * the hold-verdict half of test_spec descriptor 2 (feed the red correctness run to
   scripts/ci/post_merge_hold.py and observe `Post-merge suite status` fail);
 * test_spec descriptor 3 (timing-lane failure leaves the hold unchanged).
======================================================================
"""

import configparser
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

import yaml

from scripts.suite_performance import check_exclusion_compensation as gate

from ._workflow_jobs import FakeGitHub, WorkflowRun, find_job

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts" / "suite_performance" / "check_exclusion_compensation.py"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CORRECTNESS_WORKFLOW = "post-merge-suite.yml"
TIMING_WORKFLOW = "post-merge-timing.yml"

_REGULAR_AND_MANUAL = (
    "import pytest\n\n\ndef test_regular_one():\n    assert True\n\n\n"
    "@pytest.mark.manual\ndef test_slow_one():\n    assert True\n"
)


# --------------------------------------------------------------------------- helpers
def _fail(message, cause=None):
    """Raise a harness failure (distinct from an assertion about the code under test)."""
    raise AssertionError(message) from cause


def _write(path, text):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        _fail(f"could not write fixture {path}: {exc}", exc)


def _run(argv, cwd, extra_env=None, timeout=300):
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env.update(extra_env or {})
    try:
        return subprocess.run(
            argv, cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        _fail(f"could not run {argv!r}: {exc}", exc)


def _collect_ids(args, cwd):
    proc = _run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args], cwd)
    ids = {ln.strip() for ln in proc.stdout.splitlines() if "::" in ln and not ln.startswith(("=", " "))}
    return ids, proc.stdout + proc.stderr


def _run_step(run_text, cwd, extra_env=None):
    """Execute a workflow ``run:`` step verbatim, the way the Actions default shell does."""
    if "${{" in run_text:
        _fail(f"step uses a ${{{{ }}}} expression and cannot be executed offline:\n{run_text}")
    return _run(["bash", "-e", "-c", run_text], cwd, extra_env)


def _load_workflow(path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        _fail(f"cannot read workflow {path}: {exc}", exc)


# The workflow-reading helpers are the GATE's own functions, not copies: an oracle that re-implements
# the gate can drift from it. The refusal tests below still prove the gate behaviourally.
_events = gate.events
_is_automatic = gate.is_automatic
_swallows = gate.swallows
_pytest_args = gate.pytest_args


def _opt_in_steps(doc):
    """(job_name, job, step) for every run step whose pytest command carries ``-m <expr>``."""
    for job_name, job in (doc.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            args = _pytest_args(step.get("run") or "")
            if args is not None and "-m" in args:
                yield job_name, job, step


# ---- synthetic projects for the refusal gate (fixtures from real serializers)
def _write_ini(root, deselect):
    cp = configparser.ConfigParser(interpolation=None)
    cp["pytest"] = {"strict_markers": "true", "markers": "\nmanual: slow opt-in tests"}
    if deselect:
        cp["pytest"]["addopts"] = '-m "not manual"'
    try:
        with (root / "pytest.ini").open("w", encoding="utf-8") as fh:
            cp.write(fh)
    except OSError as exc:
        _fail(f"could not write pytest.ini: {exc}", exc)


def _write_workflow(root, name, on, run, step_extra=None, job_extra=None):
    step = {"run": run, **(step_extra or {})}
    doc = {"name": name, "on": on, "jobs": {"opt-in": {"runs-on": "ubuntu-latest", **(job_extra or {}), "steps": [step]}}}
    _write(root / ".github" / "workflows" / f"{name}.yml", yaml.safe_dump(doc, sort_keys=False))


_CADENCE_ON = {"push": {"branches": ["main"]}, "schedule": [{"cron": "17 */6 * * *"}]}
_OPT_IN_RUN = "python -m pytest -m manual -q"


def _make_project(root, deselect=True):
    _write_ini(root, deselect)
    _write(root / "test_sample.py", _REGULAR_AND_MANUAL)


def _run_gate(root):
    proc = _run([sys.executable, str(GATE), "--root", str(root)], root)
    return proc.returncode, proc.stdout + proc.stderr


class _GateCase(unittest.TestCase):
    def assert_refused_naming_the_gap(self, root):
        self.assertTrue(GATE.is_file(), f"refusal gate not implemented: {GATE.relative_to(REPO_ROOT)}")
        rc, out = _run_gate(root)
        self.assertNotEqual(0, rc, f"deselection with no invoked opt-in must be refused, got exit 0:\n{out}")
        self.assertIn("manual", out, "refusal must name the deselected marker")
        self.assertRegex(out, r"(?i)invoked", "refusal must say an INVOKED opt-in is what is missing")


# --------------------------------------------------------------------------- tests
# The union assertion (test_tq600a_13_i_the_opt_in_collects_every_test_the_default_run_excluded) lives in
# test_tq_600a_13.py::TestTq600a13, which already holds the whole-suite collections it needs.


class TestTq600a13iFailingExcludedTestFailsTheJob(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = FakeGitHub()

    @classmethod
    def tearDownClass(cls):
        cls.api.close()

    def _drive_lane(self, workflow_name, test_source):
        """Execute run -> retry -> verdict of a lane workflow for a passing and a failing test; return both outcomes.

        Each outcome is ``(run job, verdict job, uploaded verdict file or None)``. The three jobs are real
        (the shared workflow-step executor), each in its own fresh directory.
        """
        path = WORKFLOWS / workflow_name
        self.assertTrue(path.is_file(), f"lane workflow not implemented: .github/workflows/{workflow_name}")
        doc = _load_workflow(path)
        self.assertTrue(_is_automatic(doc), f"{workflow_name} is never triggered by push-to-main or schedule")
        steps = list(_opt_in_steps(doc))
        self.assertTrue(steps, f"{workflow_name} has no run step with a pytest -m command")
        for job_name, job in (doc.get("jobs") or {}).items():
            self.assertFalse(_swallows(job.get("continue-on-error")), f"job {job_name}: continue-on-error swallows the failure")
            for step in job.get("steps") or []:
                self.assertFalse(_swallows(step.get("continue-on-error")), f"job {job_name}: step-level continue-on-error")
        for job in ("run", "retry", "verdict"):
            self.assertIsNotNone(find_job(doc, job), f"{workflow_name} has no `{job}` job")
        outcomes = []
        for passing in (True, False):
            with tempfile.TemporaryDirectory() as raw:
                base = Path(raw)
                project = base / "project"
                _write(project / "pytest.ini", (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8"))
                _write(project / "unit_tests" / "test_lane.py", test_source(passing))
                _write(project / "tests" / "test_control.py", "def test_control():\n    assert True\n")
                _write(project / "requirements-dev.txt", "")
                try:
                    (project / "scripts").symlink_to(REPO_ROOT / "scripts", target_is_directory=True)
                except OSError as exc:
                    _fail(f"cannot link scripts/ into the synthetic project: {exc}", exc)
                wf = WorkflowRun(path, project, base / "scratch", None, self.api.url)
                run = wf.execute_job("run")
                retry = wf.execute_job("retry", {"run": run})
                verdict = wf.execute_job("verdict", {"run": run, "retry": retry})
                names = wf.artifacts.names()
                file = wf.artifacts.read_json("post-merge-verdict", "post-merge-verdict.json") if "post-merge-verdict" in names else None
                outcomes.append((run, verdict, file))
        return outcomes

    def test_tq600a_13_i_a_failing_excluded_test_turns_the_invoking_job_red(self):
        # covers: TQ-600a-13-i
        # angle: discrimination
        """AC-13-i must_catch: continue-on-error / swallowed status / never-triggered cadence (correctness lane).

        RECONCILED WITH TQ-600a-13-ii: the correctness lane's first execution does NOT decide the run.
        The `run` job exits zero whenever it produced a report (test failures are data), a separate
        `retry` job re-executes the failures on a fresh runner, and the `verdict` job's exit status is
        the run's conclusion. So the job whose outcome is observed here is `verdict`, executed after
        `run` and `retry` as three separate jobs. A failing `_MANUAL` (auto-marked `manual`) test must
        make `verdict` exit non-zero (and be named in `failing`); a passing one must make it exit zero
        having actually collected the test (control row). No continue-on-error anywhere in the workflow.
        Deferred: the hold-verdict half (-vi).
        """
        path = WORKFLOWS / CORRECTNESS_WORKFLOW
        self.assertTrue(path.is_file(), f"lane workflow not implemented: .github/workflows/{CORRECTNESS_WORKFLOW}")
        doc = _load_workflow(path)
        self.assertTrue(_is_automatic(doc), f"{CORRECTNESS_WORKFLOW} is never triggered by push-to-main or schedule")
        for job_name, job in (doc.get("jobs") or {}).items():
            self.assertFalse(_swallows(job.get("continue-on-error")), f"job {job_name}: continue-on-error swallows the failure")
            for step in job.get("steps") or []:
                self.assertFalse(_swallows(step.get("continue-on-error")), f"job {job_name}: step-level continue-on-error")
        for job in ("run", "retry", "verdict"):
            self.assertIsNotNone(find_job(doc, job), f"{CORRECTNESS_WORKFLOW} has no `{job}` job")

        name = f"test_lane_{uuid.uuid4().hex[:8]}_MANUAL"
        node_id = f"unit_tests/test_lane.py::{name}"
        outcomes = []
        for passing in (True, False):
            with tempfile.TemporaryDirectory() as raw:
                base = Path(raw)
                project = base / "project"
                _write(project / "pytest.ini", (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8"))
                _write(project / "unit_tests" / "test_lane.py", f"def {name}():\n    assert {passing}\n")
                _write(project / "tests" / "test_control.py", "def test_control():\n    assert True\n")
                _write(project / "requirements-dev.txt", "")
                try:
                    (project / "scripts").symlink_to(REPO_ROOT / "scripts", target_is_directory=True)
                except OSError as exc:
                    _fail(f"cannot link scripts/ into the synthetic project: {exc}", exc)
                wf = WorkflowRun(path, project, base / "scratch", None, self.api.url)
                run = wf.execute_job("run")
                retry = wf.execute_job("retry", {"run": run})
                verdict = wf.execute_job("verdict", {"run": run, "retry": retry})
                names = wf.artifacts.names()
                file = wf.artifacts.read_json("post-merge-verdict", "post-merge-verdict.json") if "post-merge-verdict" in names else None
                outcomes.append((run, verdict, file))
        (run_ok, verdict_ok, file_ok), (run_bad, verdict_bad, file_bad) = outcomes
        self.assertEqual("success", run_ok.conclusion, f"control: run job:\n{run_ok.log_text()[-800:]}")
        self.assertEqual("success", verdict_ok.conclusion, f"control: verdict must be green when the excluded test passes:\n{verdict_ok.log_text()[-800:]}")
        self.assertIsNotNone(file_ok, "control: no verdict artifact")
        self.assertGreaterEqual(file_ok["collected"], 1, "control: the lane must RUN the excluded test")
        self.assertEqual("success", run_bad.conclusion, "the run job reports a failing test as data and exits zero (-ii)")
        self.assertEqual("failure", verdict_bad.conclusion, f"a failing excluded test must turn the deciding (verdict) job red:\n{verdict_bad.log_text()[-800:]}")
        self.assertIsNotNone(file_bad, "no verdict artifact on the red run")
        self.assertIn(node_id, file_bad["failing"], "the failing excluded test must be named by its full node id")

    def test_tq600a_13_i_a_failing_excluded_test_turns_the_timing_lane_job_red(self):
        # covers: TQ-600a-13-i
        # angle: discrimination
        """AC-13-i must_catch (timing lane): a failing `timing_ratio` test turns the timing workflow's own run red.

        RECONCILED WITH TQ-600a-13-xii, exactly as the correctness twin above was with -ii: the timing
        workflow has the same run / retry / verdict shape, its `run` job exits zero on a produced report and
        the `verdict` job's exit status is the run's conclusion. So the job observed is `verdict`, executed
        after `run` and `retry`. A failing `timing_ratio` test must make `verdict` exit non-zero (and be named
        in `failing`); a passing one must make it exit zero having actually collected the test (control row).
        The workflow is automatic and carries no continue-on-error anywhere. Before xii the single pytest
        step was executed and its exit status observed.
        """
        name = f"test_ratio_{uuid.uuid4().hex[:8]}"
        node_id = f"unit_tests/test_lane.py::{name}"
        source = lambda ok: f"import pytest\n\n\n@pytest.mark.timing_ratio\ndef {name}():\n    assert {ok}\n"  # noqa: E731
        (run_ok, verdict_ok, file_ok), (run_bad, verdict_bad, file_bad) = self._drive_lane(TIMING_WORKFLOW, source)
        self.assertEqual("success", run_ok.conclusion, f"control: run job:\n{run_ok.log_text()[-800:]}")
        self.assertEqual("success", verdict_ok.conclusion, f"control: verdict must be green when the timing test passes:\n{verdict_ok.log_text()[-800:]}")
        self.assertIsNotNone(file_ok, "control: no verdict artifact")
        self.assertGreaterEqual(file_ok["collected"], 1, "control: the lane must RUN the timing test")
        self.assertEqual("timing", file_ok["lane"])
        self.assertEqual("success", run_bad.conclusion, "the run job reports a failing test as data and exits zero")
        self.assertEqual("failure", verdict_bad.conclusion, f"a failing timing test must turn the deciding (verdict) job red:\n{verdict_bad.log_text()[-800:]}")
        self.assertIsNotNone(file_bad, "no verdict artifact on the red run")
        self.assertIn(node_id, file_bad["failing"], "the failing timing test must be named by its full node id")


class TestTq600a13iRefusal(_GateCase):
    def test_tq600a_13_i_a_deselection_without_an_invoked_opt_in_is_refused(self):
        # covers: TQ-600a-13-i
        # angle: discrimination
        """AC-13-i must_catch: the cheap half lands alone. Deselect + NO workflow at all -> refused.

        Must be implemented: scripts/suite_performance/check_exclusion_compensation.py exits non-zero and
        names `manual` and what is missing (an `invoked` opt-in), not a warning and not a count.
        """
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _make_project(root, deselect=True)
            self.assert_refused_naming_the_gap(root)

    def test_tq600a_13_i_a_defined_but_never_triggered_opt_in_is_refused(self):
        # covers: TQ-600a-13-i
        # angle: discrimination
        """AC-13-i must_catch: the refusal checks DEFINED, not INVOKED.

        The opt-in job exists and runs `pytest -m manual`, but is triggered only by `workflow_dispatch`
        (a button, not a cadence). Must be refused.
        """
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _make_project(root, deselect=True)
            _write_workflow(root, "post-merge-suite", {"workflow_dispatch": None}, _OPT_IN_RUN)
            self.assert_refused_naming_the_gap(root)

    def _assert_swallowing_cadence_refused(self, run_text, step_extra):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _make_project(root, deselect=True)
            _write_workflow(root, "post-merge-suite", _CADENCE_ON, run_text, step_extra)
            self.assert_refused_naming_the_gap(root)

    def test_tq600a_13_i_a_cadence_with_continue_on_error_is_refused(self):
        # covers: TQ-600a-13-i
        # angle: discrimination
        """AC-13-i must_catch: an invoked cadence whose step has `continue-on-error: true` fails nothing; refused."""
        self._assert_swallowing_cadence_refused(_OPT_IN_RUN, {"continue-on-error": True})

    def test_tq600a_13_i_a_cadence_that_swallows_the_exit_status_is_refused(self):
        # covers: TQ-600a-13-i
        # angle: discrimination
        """AC-13-i must_catch: `|| true` on the pytest command swallows the exit status; refused."""
        self._assert_swallowing_cadence_refused(f"{_OPT_IN_RUN} || true", None)


class TestTq600a13iAcceptance(_GateCase):
    def test_tq600a_13_i_a_complete_arrangement_is_accepted(self):
        # covers: TQ-600a-13-i
        # angle: criterion
        """AC-13-i paired control: deselection + registered marker + invoked cadence is accepted and both collections work.

        Also controls vacuity: no deselection at all is accepted (a gate refusing everything fails here).
        """
        self.assertTrue(GATE.is_file(), f"refusal gate not implemented: {GATE.relative_to(REPO_ROOT)}")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _make_project(root, deselect=True)
            _write_workflow(root, "post-merge-suite", _CADENCE_ON, _OPT_IN_RUN)
            rc, out = _run_gate(root)
            self.assertEqual(0, rc, f"a complete arrangement must be accepted:\n{out}")
            default_ids, d_out = _collect_ids([], root)
            optin_ids, o_out = _collect_ids(["-m", "manual"], root)
            self.assertEqual(["test_sample.py::test_regular_one"], sorted(default_ids), d_out[-400:])
            self.assertEqual(["test_sample.py::test_slow_one"], sorted(optin_ids), o_out[-400:])
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _make_project(root, deselect=False)
            rc, out = _run_gate(root)
            self.assertEqual(0, rc, f"nothing excluded: the record is satisfied vacuously:\n{out}")

    def test_tq600a_13_i_the_real_repository_arrangement_is_accepted(self):
        # covers: TQ-600a-13-i
        # angle: reachability
        """AC-13-i: the gate, run as the real CLI against THIS repository, accepts it.

        pytest.ini really deselects `manual` today; accepted only once a real workflow invokes the opt-in.
        """
        self.assertTrue(GATE.is_file(), f"refusal gate not implemented: {GATE.relative_to(REPO_ROOT)}")
        rc, out = _run_gate(REPO_ROOT)
        self.assertEqual(0, rc, f"the repository deselects `manual` with no invoked opt-in:\n{out}")

    def test_tq600a_13_i_ci_runs_the_refusal_gate_and_the_step_refuses(self):
        # covers: TQ-600a-13-i
        # angle: reachability
        """AC-13-i: the deselection cannot land ahead of its compensation because CI runs the gate.

        Must be implemented: a pull_request workflow step in ci.yml invoking check_exclusion_compensation.
        The step is executed verbatim in a project that deselects with no cadence (exit non-zero), and in
        one with an invoked cadence (exit 0), so a step that always passes or always fails is caught.
        """
        ci = WORKFLOWS / "ci.yml"
        doc = _load_workflow(ci)
        self.assertIn("pull_request", _events(doc), "ci.yml does not run on pull requests")
        steps = [
            s["run"]
            for job in (doc.get("jobs") or {}).values()
            for s in job.get("steps") or []
            if "check_exclusion_compensation" in (s.get("run") or "")
        ]
        self.assertTrue(steps, "ci.yml has no step invoking check_exclusion_compensation")
        for label, with_cadence in (("refused", False), ("accepted", True)):
            with tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                _make_project(root, deselect=True)
                if with_cadence:
                    _write_workflow(root, "post-merge-suite", _CADENCE_ON, _OPT_IN_RUN)
                try:
                    (root / "scripts").symlink_to(REPO_ROOT / "scripts", target_is_directory=True)
                except OSError as exc:
                    _fail(f"cannot link scripts/ into the synthetic project: {exc}", exc)
                proc = _run_step(steps[0], root)
                if with_cadence:
                    self.assertEqual(0, proc.returncode, f"{label}: {proc.stdout}{proc.stderr}")
                else:
                    self.assertNotEqual(0, proc.returncode, f"{label}: CI step let a bare deselection through")


if __name__ == "__main__":
    unittest.main()
