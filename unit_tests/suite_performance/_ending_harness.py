"""Shared harness for the TQ-600a-13-v tests (a run that did not run to completion). Not a test: underscore-named.

* ``make_project`` / ``drive_lane`` -- a synthetic project whose lane is whatever the test writes, and the
  REAL ``run`` -> ``retry`` -> ``verdict`` jobs of ``post-merge-suite.yml`` executed verbatim over real child
  pytest sessions by the shared workflow-step executor.
* ``drive_verdict`` -- only the ``verdict`` job, with the dependency results the hosting service would give it
  and whichever artifacts the test seeds. Setup failure, a failed retry, a cancellation and a timeout are events
  of the hosting service and cannot be produced in the unit layer; this is the honest form (the job's real
  steps run, the service's answer is supplied).
* ``EndingTestCase`` -- the notice test case with a fake service that also serves a run's jobs, serves the run
  list in INSERTION order (the API's own order is unverified), and honours ``status`` and
  ``exclude_pull_requests`` the way the real run-list endpoint does.
* ``Cases`` -- collects every labelled failure so one red test reports all its rows, never only the first.
"""

from __future__ import annotations

import configparser
import json
import re
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple
from urllib.parse import parse_qs, urlparse

from ._notice_fakes import REPO, FakeIssueService, NoticeTestCase
from ._workflow_conditions import HarnessError
from ._workflow_jobs import REPO_ROOT, JobResult, WorkflowRun

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-suite.yml"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "tq_600a_13_v"
VERDICT_ARTIFACT, VERDICT_FILE = "post-merge-verdict", "post-merge-verdict.json"
FIRST_REPORT = ("first-run-report", "first-run-report.json")
RETRY_REPORT = ("retry-report", "retry-report.json")
HEAD_SHA = "1" * 40
CHECK = unittest.TestCase()
_JOBS = re.compile(rf"{re.escape(f'/repos/{REPO}/actions/runs/')}(\d+)/jobs")


def read_text(path):
    """Read a text file; an unreadable one is a broken test, never a silent pass."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        message = f"cannot read {path}: {exc}"
        raise AssertionError(message) from exc


def live_red_verdict():
    """The real verdict file of a red `Post-merge suite` run on main (verbatim, as the real producer wrote it)."""
    return json.loads(read_text(FIXTURE_DIR / "live_red_verdict.json"))


# --------------------------------------------------------------------------- collecting rows
class Cases:
    """Labelled blocks whose failures are all reported together (not subTest: the parent must read as failed)."""

    def __init__(self):
        self.failures = []

    @contextmanager
    def case(self, label):
        try:
            yield
        except HarnessError:
            raise
        except AssertionError as exc:
            self.failures.append(f"[{label}] {exc}")

    def check(self):
        if self.failures:
            raise AssertionError(f"{len(self.failures)} row(s) failed:\n" + "\n".join(self.failures))


# --------------------------------------------------------------------------- the synthetic project
def make_project(root, tests, continue_on_errors=True):
    """Write a project whose ini is built by the real serializer; ``tests`` maps relative path -> source."""
    addopts = '-m "not manual and not timing_ratio"'
    ini = configparser.ConfigParser(interpolation=None)
    ini["pytest"] = {
        "strict_markers": "true",
        "addopts": f"--continue-on-collection-errors {addopts}" if continue_on_errors else addopts,
        "markers": "\nmanual: opt-in lane\ntiming_ratio: timing lane",
    }
    files = {"unit_tests/test_default_only.py": "def test_default_run_only():\n    assert True\n", "requirements-dev.txt": "", **tests}
    try:
        with (root / "pytest.ini").open("w", encoding="utf-8") as handle:
            ini.write(handle)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (root / "scripts").symlink_to(REPO_ROOT / "scripts", target_is_directory=True)
    except OSError as exc:
        message = f"cannot build the synthetic project: {exc}"
        raise AssertionError(message) from exc


def lane_test(name, body="assert True", marked=True):
    """Source of one lane test file; ``marked`` puts it in the correctness lane."""
    mark = "@pytest.mark.manual\n" if marked else ""
    return f"import pytest\n\n\n{mark}def test_{name}():\n    {body}\n"


# --------------------------------------------------------------------------- driving the jobs
class Drive(NamedTuple):
    run: JobResult
    retry: JobResult
    verdict: JobResult
    file: dict | None  # the uploaded `post-merge-verdict` artifact, parsed; None when no verdict job uploaded one


def _env(run_number):
    return {"GITHUB_RUN_ID": str(100 + run_number), "GITHUB_SHA": HEAD_SHA}


def _verdict_file(wf):
    if VERDICT_ARTIFACT not in wf.artifacts.names():
        return None
    return wf.artifacts.read_json(VERDICT_ARTIFACT, VERDICT_FILE)


def drive_lane(api, tests, *, continue_on_errors=True, run_number=5, skip_retry=False):
    """Execute run -> retry -> verdict (real steps, real child pytest sessions). ``skip_retry`` hands the verdict
    job a skipped retry instead of executing that job (used where its outcome is not what the test is about)."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        (base / "project").mkdir()
        make_project(base / "project", tests, continue_on_errors)
        wf = WorkflowRun(WORKFLOW, base / "project", base / "scratch", _env(run_number), api.url)
        run = wf.execute_job("run")
        retry = JobResult("retry", "skipped") if skip_retry else wf.execute_job("retry", {"run": run})
        verdict = wf.execute_job("verdict", {"run": run, "retry": retry})
        return Drive(run, retry, verdict, _verdict_file(wf))


def first_run_report_text(api, tests):
    """The first-run report a real `run` job uploaded (written by the real plugin over a real child session)."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        (base / "project").mkdir()
        make_project(base / "project", tests)
        wf = WorkflowRun(WORKFLOW, base / "project", base / "scratch", _env(5), api.url)
        run = wf.execute_job("run")
        CHECK.assertEqual("success", run.conclusion, run.log_text()[-1500:])
        return wf.artifacts.read_text(*FIRST_REPORT)


def drive_verdict(api, run_result, retry_result="skipped", *, artifacts=None, cancelled=False, run_number=5):
    """Execute only the verdict job with the given dependency results; ``artifacts`` maps (name, file) -> bytes."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        (base / "project").mkdir()
        make_project(base / "project", {})
        wf = WorkflowRun(WORKFLOW, base / "project", base / "scratch", _env(run_number), api.url)
        try:
            for (name, rel), data in (artifacts or {}).items():
                source = base / "seed" / name / rel
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(data)
                wf.artifacts.upload(name, [(rel, source)])
        except OSError as exc:
            message = f"cannot seed artifact {name!r}: {exc}"
            raise AssertionError(message) from exc
        needs = {"run": JobResult("run", run_result), "retry": JobResult("retry", retry_result)}
        verdict = wf.execute_job("verdict", needs, cancelled=cancelled)
        return Drive(needs["run"], needs["retry"], verdict, _verdict_file(wf))


def expect_did_not_complete(drive, stage):
    """The ending is recorded as not-run: file, stage, no failing tests, and the job fails at its named step."""
    if drive.file is None:
        message = f"no `{VERDICT_ARTIFACT}` artifact uploaded (verdict job {drive.verdict.conclusion}):\n{drive.verdict.log_text()[-800:]}"
        raise AssertionError(message)
    CHECK.assertEqual(("did_not_complete", stage, []), (drive.file["verdict"], drive.file["stage"], drive.file["failing"]))
    CHECK.assertEqual(("failure", "Verdict: did not complete"), (drive.verdict.conclusion, drive.verdict.failed_step))
    CHECK.assertEqual("skipped", drive.verdict.steps.get("Verdict: red"))


# --------------------------------------------------------------------------- the notice side
class EndingService(FakeIssueService):
    """The fake issue service, plus ``jobs`` per run id, run list in insertion order, ``status`` / PR filters."""

    def reset(self, **kwargs):
        super().reset(**kwargs)
        self.jobs = {}  # run id -> list of job dicts, served by GET /actions/runs/{id}/jobs

    def handle(self, method, raw_path, body):
        match = _JOBS.fullmatch(urlparse(raw_path).path)
        if method == "GET" and match:
            self.requests.append((method, raw_path))
            jobs = self.jobs.get(int(match.group(1)))
            return (404, {"message": "Not Found"}) if jobs is None else (200, {"total_count": len(jobs), "jobs": jobs})
        return super().handle(method, raw_path, body)

    def _runs(self, query):
        runs = [r for r in self.runs if r.get("head_branch") == query.get("branch", r.get("head_branch"))]
        if "status" in query:
            runs = [r for r in runs if query["status"] in (r.get("status"), r.get("conclusion"))]
        if query.get("exclude_pull_requests") == "true":
            runs = [r for r in runs if r.get("event") != "pull_request"]
        runs = runs[: min(int(query.get("per_page", 30)), 100)]
        return {"total_count": len(runs), "workflow_runs": runs}

    def run_history_queries(self):
        """The query of every request that read the suite's run history."""
        paths = [urlparse(p) for m, p in self.requests if m == "GET"]
        return [parse_qs(u.query) for u in paths if "/actions/workflows/" in u.path and u.path.endswith("/runs")]


class EndingTestCase(NoticeTestCase):
    """NoticeTestCase whose service is an ``EndingService``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc.close()
        cls.svc = EndingService()
