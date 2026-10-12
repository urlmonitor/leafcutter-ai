"""Test infrastructure for TQ-600a-13-vi (the `Post-merge suite status` hold). Not a test: underscore-named.

* ``HoldService`` -- the shared recording fake (issues, run lists in all statuses, a run's jobs) plus the
  one read the hold adds: ``GET /actions/workflows/post-merge-suite.yml`` (the workflow's ``state``). It
  serves the timing workflow's runs separately, can fail any read, and classifies every GET it saw so a test
  counts what the hold asked for. Comment-list reads (TQ-600a-13-vii) are filtered out of ``reads()``.
* ``HoldTestCase`` -- the notice test case over a ``HoldService``, with ``evaluate`` calling the REAL hold
  through the REAL REST client and an injected clock.
* ``HoldRun`` / ``run_hold_job`` -- the shared workflow-step executor over the hold workflow, whose
  ``actions/checkout`` emulation honours ``ref:`` (the PR head) and ``sparse-checkout:`` (the default
  branch's ``scripts/ci`` only), plus a ``sitecustomize`` observer that records, INSIDE the job's own Python
  process, every child process, every file open and every import (audit events, never a patched subprocess).
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ._ending_harness import CHECK, EndingService, EndingTestCase, read_text
from ._notice_fakes import REPO, SERVER, import_production, run_record
from ._workflow_conditions import _expand
from ._workflow_jobs import REPO_ROOT, JobResult, WorkflowRun

HOLD_MODULE = "scripts.ci.post_merge_hold"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-hold.yml"
JOB_NAME = "Post-merge hold evaluation"  # was `Post-merge suite status`, which is now the App's check run (TQ-600a-13-vi)
TUNABLES = REPO_ROOT / "scripts" / "ci" / "post_merge_tunables.json"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "tq_600a_13_vi"
NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
SUITE_STATE_PATH = f"/repos/{REPO}/actions/workflows/post-merge-suite.yml"
TIMING_RUNS_PATH = f"/repos/{REPO}/actions/workflows/post-merge-timing.yml/runs"
_COMMENTS = re.compile(rf"{re.escape(f'/repos/{REPO}/issues/')}\d+/comments")
_JOBS_PATH = re.compile(rf"{re.escape(f'/repos/{REPO}/actions/runs/')}\d+/jobs")


def tunables():
    """The committed tunables file, parsed (the hold must read its numbers from here, never from a literal)."""
    return json.loads(read_text(TUNABLES))


def live_notice_body():
    """The real description of notice #1077 on the real repository, verbatim (state block included)."""
    return read_text(FIXTURE_DIR / "live_notice_1077_body.md")


# --------------------------------------------------------------------------- records
def make_run(number, conclusion="success", *, hours_ago=1.0, now=NOW, **kwargs):
    """A run record as the API serves it, with ``run_started_at`` ``hours_ago`` before ``now``."""
    run_id = kwargs.pop("id", None)  # a real run's id (run_record derives one from the run number)
    record = run_record(number, conclusion, **kwargs)
    if run_id:
        record["id"], record["html_url"] = run_id, f"{SERVER}/{REPO}/actions/runs/{run_id}"
    record["run_started_at"] = (now - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return record


def make_job(name, conclusion, steps=()):
    """A job as ``GET /actions/runs/{id}/jobs?filter=latest`` serves it."""
    listed = [{"name": n, "status": "completed", "conclusion": c, "number": i + 1} for i, (n, c) in enumerate(steps)]
    return {"id": 7, "name": name, "status": "completed", "conclusion": conclusion, "steps": listed}


RED_JOBS = [make_job("verdict", "failure", [("Classify the run", "success"), ("Verdict: red", "failure"), ("Verdict: did not complete", "skipped")])]
DNC_JOBS = [make_job("verdict", "failure", [("Classify the run", "success"), ("Verdict: red", "skipped"), ("Verdict: did not complete", "failure")])]


# --------------------------------------------------------------------------- the fake service
class HoldService(EndingService):
    """``EndingService`` plus the workflow-state read, the timing workflow's runs and injectable read failures."""

    def reset(self, **kwargs):
        super().reset(**kwargs)
        self.workflow_state, self.timing_runs, self.failing = "active", [], []

    def handle(self, method, raw_path, body):
        path = urlparse(raw_path).path
        failing = method == "GET" and any(path.startswith(prefix) or path.endswith(prefix) for prefix in self.failing)
        if method == "GET" and (failing or path in (SUITE_STATE_PATH, TIMING_RUNS_PATH)):
            self.requests.append((method, raw_path))
            if failing:
                return 500, {"message": "Server Error"}
            if path == TIMING_RUNS_PATH:
                return 200, {"total_count": len(self.timing_runs), "workflow_runs": self.timing_runs}
            return 200, {"id": 1, "state": self.workflow_state, "path": ".github/workflows/post-merge-suite.yml"}
        return super().handle(method, raw_path, body)

    def reads(self):
        """Every GET the hold made as ``(kind, query)``, comment-list pages excluded (those belong to -vii)."""
        out = []
        for method, raw in self.requests:
            parsed = urlparse(raw)
            if method != "GET" or _COMMENTS.fullmatch(parsed.path):
                continue
            out.append((self._kind(parsed.path), parse_qs(parsed.query)))
        return out

    @staticmethod
    def _kind(path):
        if path.endswith("/actions/workflows/post-merge-suite.yml"):
            return "workflow"
        if "/actions/workflows/" in path and path.endswith("/runs"):
            return "runs"
        if _JOBS_PATH.fullmatch(path):
            return "jobs"
        return "notices" if path == f"/repos/{REPO}/issues" else f"other:{path}"

    def read_kinds(self):
        return sorted(kind for kind, _ in self.reads())

    def paths_seen(self):
        return [urlparse(raw).path for _, raw in self.requests]


class HoldTestCase(EndingTestCase):
    """The notice test case over a ``HoldService``; ``evaluate`` is the hold's verdict entry point."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc.close()
        cls.svc = HoldService()

    def evaluate(self, now=NOW):
        """Call ``scripts.ci.post_merge_hold.evaluate(client, repo, now=...)`` through the real REST client."""
        hold = import_production(HOLD_MODULE)
        found = getattr(hold, "evaluate", None)
        CHECK.assertTrue(callable(found), f"{HOLD_MODULE}.evaluate is not implemented yet")
        client = import_production("scripts.ci._github_rest").GitHubClient(self.svc.url, "fake-token")
        return found(client, REPO, now=now)

    def serve(self, runs, jobs=None):
        """Replace the served run history (and the jobs of the given run ids)."""
        self.svc.runs = list(runs)
        self.svc.jobs = dict(jobs or {})


# --------------------------------------------------------------------------- the executed job
OBSERVER = textwrap.dedent(
    """
    import atexit, json, os, sys
    _LOG, _EVENTS, _STATE = os.environ.get("HOLD_OBSERVER_LOG"), [], {"done": False}
    _PROC = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty")

    def _hook(event, args):
        if _STATE["done"]:
            return
        if event in _PROC:
            _EVENTS.append({"kind": "process", "event": event})
        elif event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            _EVENTS.append({"kind": "open", "path": os.fsdecode(args[0]), "mode": str(args[1])})
        elif event == "import":
            _EVENTS.append({"kind": "import", "module": args[0]})

    def _flush():
        _STATE["done"] = True
        with open(f"{_LOG}.{os.getpid()}", "w", encoding="utf-8") as handle:
            json.dump(_EVENTS, handle)

    if _LOG:
        sys.addaudithook(_hook)
        atexit.register(_flush)  # one file per interpreter process: a child session of the check would show up too
    """
)


class HoldRun(WorkflowRun):
    """The executor with a checkout that says what it was asked for and honours ``ref`` and ``sparse-checkout``."""

    def __init__(self, workflow_path, default_dir, head_dir, scratch, extra_env, api_url):
        super().__init__(workflow_path, default_dir, scratch, extra_env, api_url)
        self.head_dir = Path(head_dir) if head_dir else None
        self.checkouts = []

    def _uses(self, step, ctx, result, workspace):
        if step["uses"].split("@", 1)[0] != "actions/checkout":
            return super()._uses(step, ctx, result, workspace)
        with_ = {k: _expand(v, ctx) for k, v in (step.get("with") or {}).items()}
        ref = str(with_.get("ref") or "").strip()
        self.checkouts.append({"ref": ref, "sparse": with_.get("sparse-checkout"), "persist": with_.get("persist-credentials"), "depth": with_.get("fetch-depth")})
        source = self.head_dir if (ref and self.head_dir) else self.project_dir
        wanted = [p.strip().strip("/") for p in str(with_.get("sparse-checkout") or "").splitlines() if p.strip()] or [""]
        try:
            for rel in wanted:
                if (source / rel).exists():
                    shutil.copytree(source / rel, workspace / rel, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        except (OSError, shutil.Error) as exc:
            return "failure", f"checkout failed: {exc}", {}
        return "success", f"checkout emulated from {'the PR head' if ref else 'the default branch'}: {wanted}", {}


@dataclass
class JobOutcome:
    result: JobResult
    run: HoldRun
    events: list
    head_dir: Path | None
    state_dir: Path

    def opened(self):
        return [e for e in self.events if e["kind"] == "open"]

    def processes(self):
        return [e for e in self.events if e["kind"] == "process"]

    def imported(self):
        return {e["module"].split(".")[0] for e in self.events if e["kind"] == "import"}


def scratch_default_branch(base):
    """The default branch as the sparse checkout will find it: the real ``scripts/ci`` and nothing else."""
    dest = base / "default"
    try:
        shutil.copytree(REPO_ROOT / "scripts" / "ci", dest / "scripts" / "ci", ignore=shutil.ignore_patterns("__pycache__"))
    except OSError as exc:
        message = f"cannot stage the default branch: {exc}"
        raise AssertionError(message) from exc
    return dest


def run_hold_job(svc, base, *, workflow=WORKFLOW, head_files=None, pr_number=42):
    """Execute the `Post-merge hold evaluation` job of ``workflow`` verbatim against ``svc`` with an ``opened`` event.

    ``svc`` must be an ``AppService`` (the job mints the hold App's token); the two App secrets are supplied the way
    ``_app_harness.run_app_job`` supplies them (``secrets.X`` rewritten to an ``env`` lookup).
    ``head_files`` maps path -> text for a synthetic PR head commit (a scratch tree the job must never read).
    """
    from ._app_harness import SECRET_PREFIX, app_secrets, secrets_as_env  # noqa: PLC0415 -- _app_fake imports this module

    base = Path(base)
    default = scratch_default_branch(base)
    head = None
    if head_files:
        head = base / "pr-head"
        for rel, text in head_files.items():
            (head / rel).parent.mkdir(parents=True, exist_ok=True)
            (head / rel).write_text(text, encoding="utf-8")
    observer, state_dir, event = base / "observer", base / "state", base / "event.json"
    for folder in (observer, state_dir):
        folder.mkdir()
    (observer / "sitecustomize.py").write_text(OBSERVER, encoding="utf-8")
    payload = {"action": "opened", "number": pr_number, "pull_request": {"number": pr_number, "body": "A change.", "head": {"sha": "9" * 40}, "base": {"ref": "main"}}}
    event.write_text(json.dumps(payload), encoding="utf-8")
    log = base / "observed.json"
    env = {
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_EVENT_NAME": "pull_request_target",
        "PYTHONPATH": str(observer),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOLD_OBSERVER_LOG": str(log),
        "HOME": str(state_dir),
    }
    env.update({f"{SECRET_PREFIX}{name}": value for name, value in app_secrets().items()})
    run = HoldRun(secrets_as_env(workflow, base / "workflow-under-test.yml"), default, head, base / "scratch", env, svc.url)
    result = run.execute_job(JOB_NAME)
    events = [e for part in sorted(base.glob(f"{log.name}.*")) for e in json.loads(part.read_text(encoding="utf-8"))]
    return JobOutcome(result, run, events, head, state_dir)


def fresh_base():
    """A scratch directory for one job execution; the caller cleans it up."""
    return tempfile.TemporaryDirectory()
