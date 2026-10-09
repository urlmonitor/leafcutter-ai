"""Shared harness for the TQ-600a-13-xii tests (the timing lane's run / retry / verdict and its notice). Not a test.

* ``drive_timing`` -- the REAL ``run`` -> ``retry`` -> ``verdict`` jobs of ``post-merge-timing.yml`` executed verbatim over
  real child pytest sessions by the shared workflow-step executor, in a synthetic project the test writes.
* ``timing_test`` / ``plain_test`` / ``manual_test`` -- sources of synthetic test files (the marker spellings are the
  repository's: ``timing_ratio`` and ``manual``).
* ``timing_verdict`` -- a timing verdict file built by the REAL producer (``build_verdict_file(..., lane="timing")``).
* ``TimingRepo`` -- a scratch git repository whose history marks a test file twice inside one commit range.
* ``TimingNoticeCase`` -- the hold test case (fake issue service, run history, jobs) plus ``apply_timing``, which runs the
  notice job's ``apply --lane timing`` entry point against a staged verdict file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from ._ending_harness import HEAD_SHA, VERDICT_ARTIFACT, VERDICT_FILE, Drive, _env, make_project
from ._hold_harness import HoldTestCase
from ._notice_fakes import REPO, SERVER, Applied, _git, captured_logs, import_production
from ._workflow_jobs import REPO_ROOT, WorkflowRun

TIMING_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-timing.yml"
FOLLOWUP_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-followup.yml"
TIMING_LABEL = "post-merge-timing"
RED_LABEL = "post-merge-red"
CONTROL_TEST = "def test_control():\n    assert True\n"


def timing_test(name, body="assert True"):
    """Source of one test in the timing lane (explicit ``timing_ratio`` marker, not ``manual``)."""
    return f"import pytest\n\n\n@pytest.mark.timing_ratio\ndef test_{name}():\n    {body}\n"


def manual_test(name, body="assert True"):
    """Source of one test in the correctness lane (``manual`` only)."""
    return f"import pytest\n\n\n@pytest.mark.manual\ndef test_{name}():\n    {body}\n"


def plain_test(name, body="assert True"):
    """Source of one test of the default run (no marker at all)."""
    return f"def test_{name}():\n    {body}\n"


def drive_timing(api_url, tests, *, run_number=5, extra_env=None):
    """Execute run -> retry -> verdict of the timing workflow (real steps, real child pytest sessions)."""
    env = {**_env(run_number), **(extra_env or {})}
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        (base / "project").mkdir()
        make_project(base / "project", {"tests/test_control.py": CONTROL_TEST, **tests})
        wf = WorkflowRun(TIMING_WORKFLOW, base / "project", base / "scratch", env, api_url)
        run = wf.execute_job("run")
        retry = wf.execute_job("retry", {"run": run})
        verdict = wf.execute_job("verdict", {"run": run, "retry": retry})
        names = wf.artifacts.names()
        written = wf.artifacts.read_json(VERDICT_ARTIFACT, VERDICT_FILE) if VERDICT_ARTIFACT in names else None
        return Drive(run, retry, verdict, written)


def timing_verdict(results, *, run_id, head_sha=HEAD_SHA):
    """A timing-lane verdict file from the real producer; ``results`` maps node id -> passed | failed."""
    suite = import_production("scripts.ci.post_merge_suite")
    env = {"GITHUB_SHA": head_sha, "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "push", "GITHUB_RUN_ID": str(run_id), "GITHUB_REPOSITORY": REPO, "GITHUB_SERVER_URL": SERVER}
    failed = "failed" in results.values()
    first = {"results": dict(results), "exitstatus": 1 if failed else 0, "ran": len(results), "expected": len(results), "runner": "runner-run"}
    return suite.build_verdict_file(first, None, env, lane="timing")


class TimingRepo:
    """Commits: C0, P (adds the old ratio test), M1 (adds test_moved), D (bystander), M2 (edits test_moved), H (empty head)."""

    MOVED = "unit_tests/test_moved.py"

    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        _git(self.path, "init", "-q", "-b", "main")
        self.c0 = self._commit("C0 initial", {"README.md": "hello\n"})
        self.p = self._commit("P previous timing run head", {"unit_tests/test_old_ratio.py": "def test_old():\n    pass\n"})
        self.m1 = self._commit("M1 add moved ratio test", {self.MOVED: "def test_moved():\n    pass\n"})
        self.d = self._commit("D bystander change", {"unit_tests/test_bystander.py": "def test_b():\n    pass\n"})
        self.m2 = self._commit("M2 tune moved ratio test", {self.MOVED: "def test_moved():\n    assert 1\n"})
        self.h = self._commit("H unrelated head", {})

    def _commit(self, subject, files):
        for rel, text in files.items():
            target = self.path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        _git(self.path, "add", "-A")
        _git(self.path, "commit", "-q", "--allow-empty", "-m", subject)
        return _git(self.path, "rev-parse", "HEAD")

    def commit_shas(self):
        """Every scratch commit, as full shas (a test searches text for their 7-character forms)."""
        return {"C0": self.c0, "P": self.p, "M1": self.m1, "D": self.d, "M2": self.m2, "H": self.h}


class TimingNoticeCase(HoldTestCase):
    """The hold test case (which also serves run lists, jobs and the timing workflow's runs) plus a timing apply."""

    needs_repo = False
    git: TimingRepo

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.git = TimingRepo(cls.tmp / "timing-repo")

    def stage(self, name, verdict):
        """Write a verdict file the way the notice job finds it; ``None`` means the file is absent."""
        path = self.tmp / name
        path.unlink(missing_ok=True)
        if verdict is not None:
            path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
        return path

    def apply_timing(self, verdict, run_id, *, previous=None, previous_path=None, repo_dir=None):
        """Run ``post_merge_notice.main(["apply", "--lane", "timing", ...])``; ``previous`` is the earlier run's verdict."""
        path = self.stage("post-merge-verdict.json", verdict)
        argv = ["apply", "--lane", "timing", "--api-url", self.svc.url, "--repo", REPO, "--repo-dir", str(repo_dir or self.git.path)]
        argv += ["--run-id", str(run_id), "--verdict-file", str(path)]
        if previous is not None or previous_path is not None:
            prior = previous_path or self.stage("previous-verdict.json", previous)
            argv += ["--previous-verdict-file", str(prior)]
        with captured_logs() as lines, mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}):
            code = self.notice.main(argv)
        return Applied(code, "\n".join(lines))

    def listings(self):
        """The ``labels`` filter of every issue-list request the job made."""
        out = []
        for method, raw in self.svc.requests:
            parsed = urlparse(raw)
            if method == "GET" and parsed.path == f"/repos/{REPO}/issues":
                out.append(parse_qs(parsed.query).get("labels", [""])[-1])
        return out
