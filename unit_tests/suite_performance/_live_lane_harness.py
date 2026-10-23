"""Shared harness for the TQ-600a-13-xxi / -xxii / -xxiii / -xxv tests (the live-database lane). Not a test: underscore-named.

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this). Every name below is what the tests read.

CLI (``python scripts/ci/post_merge_suite.py``, run from the project root, as the workflow runs it)
  ``run --lane live --report R --failures F -- <pytest command>``    first execution of the live lane
  ``retry --lane live --failures F --report R -- <pytest command>``  re-executes exactly the listed ids
  The live lane owns its selection: it appends a marker override (``-m ""``-equivalent: nothing deselected) to the pytest
  command, so ``manual`` and ``timing_ratio`` tests of the live folder run, on the first execution and on the retry.
  Environment: ``LIVE_DB_ADDRESS`` (``host:port``) is the address of the lane's database, ``LIVE_DB_STARTUP_LIMIT`` (seconds) the
  most the lane waits for it. Before any test the lane checks the address is REACHABLE by a real connection that stays
  up (a passed health probe alone is not trusted); the result is written to the report as
  ``"reachability": {"reachable": <bool>, "detail": <str>}``. An unreachable database executes NO test, writes the report
  (``results`` empty) and exits 0.
  The report (``_lane_report_plugin``) gains ``"skip_reasons": {<node id>: <reason text>}`` for every skipped test.
  ``verdict`` additionally reads, under ``--artifacts``, ``live-first-run-report/live-first-run-report.json`` and
  ``live-retry-report/live-retry-report.json`` and the environment variables ``LIVE_RUN_RESULT`` / ``LIVE_RETRY_RESULT``
  (the live jobs' ``needs.*.result``). When ``LIVE_RUN_RESULT`` is absent the live lane did not take part.

VERDICT FILE: ``schema_version`` 3; every correctness-lane field unchanged; a new ``live_database`` object with
  ``verdict, stage, collected, collected_ids, passed, first_run_failures, failing, passed_on_retry, pass_on_retry_window,
  skipped, unreachable_skips, run_runner, retry_runner``. ``collected_ids`` / ``collected`` are the tests that EXECUTED to a
  pass or a failure (never a skipped one); ``skipped`` is a list of ``{"id", "reason"}`` for skips of any reason EXCEPT a
  no-database one, which lives only in ``unreachable_skips`` (a list of full node ids). The recognised no-database reason is a
  skip reason that STARTS WITH ``live database unreachable`` (``UNREACHABLE``). The top-level ``verdict`` / ``stage`` are the
  combined ones: did_not_complete (either lane) outranks red outranks green; top-level ``failing`` stays the correctness
  lane's own. Stages: ``live_database_startup`` (the lane could not reach its database, or its jobs never produced a
  report because of that, or the retry machine's database never became healthy) and ``live_database_unreachable`` (a
  test skipped for an unreachable database). A live lane in which nothing executed to a pass or a failure is never green.

WORKFLOW ``post-merge-suite.yml`` gains jobs ``live_run`` (output ``failures``, steps upload artifacts
  ``live-first-run-report`` and ``live-first-run-failures``) and ``live_retry`` (downloads ONLY ``live-first-run-failures``,
  uploads ``live-retry-report``); ``verdict`` needs ``[run, retry, live_run, live_retry]``. ``LIVE_DB_ADDRESS`` and
  ``LIVE_DB_STARTUP_LIMIT`` appear as ``env:`` keys of the live jobs (or their steps) so a test can substitute a stand-in
  address, the way it substitutes the hosting service's answers.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

from ._ending_harness import CHECK, EndingTestCase, make_project
from ._workflow_jobs import REPO_ROOT, FakeGitHub, JobResult, WorkflowRun

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-suite.yml"
SCRIPT = REPO_ROOT / "scripts" / "ci" / "post_merge_suite.py"
UNREACHABLE = "live database unreachable: connection refused"
OTHER_REASON = "needs a GPU runner"
LOOKALIKE_REASON = "unreachable code path; the database is mocked in this test"
LIVE_DIR = "tests/knowledge_live"
STARTUP_STAGE, UNREACHABLE_STAGE = "live_database_startup", "live_database_unreachable"
LIVE_COMMAND = ["python", "-m", "pytest", f"{LIVE_DIR}/", "-p", "no:cacheprovider"]
OLD_KEYS = (
    "collection_errors lane verdict stage collected skipped collected_ids first_run_failures failing passed_on_retry "
    "repeated_pass_on_retry pass_on_retry_window window_runs_read run_runner retry_runner head_sha ref event run_id run_url"
).split()
LIVE_KEYS = (
    "verdict stage collected collected_ids first_run_failures failing passed_on_retry skipped unreachable_skips run_runner retry_runner"
).split()
CORR_FIRST = ("first-run-report", "first-run-report.json")
CORR_RETRY = ("retry-report", "retry-report.json")
LIVE_FIRST = ("live-first-run-report", "live-first-run-report.json")
LIVE_RETRY = ("live-retry-report", "live-retry-report.json")


def nid(name: str, folder: str = LIVE_DIR) -> str:
    """The full node id of ``test_<name>`` in the live folder's ``test_<name>.py``."""
    return f"{folder}/test_{name}.py::test_{name}"


# --------------------------------------------------------------------------- a stand-in database
class Listener:
    """A local TCP stand-in for the lane's database. ``mode``: ``accept`` (every connection is held open) or
    ``probe_only`` (the first connection is accepted, then the listener closes with a reset: every later one is
    refused or reset)."""

    def __init__(self, mode: str = "accept") -> None:
        self.mode, self.connections, self._held = mode, 0, []
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.port = self._sock.getsockname()[1]
        self.address = f"127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self) -> None:
        while True:
            try:
                conn, _addr = self._sock.accept()
            except OSError:
                return
            self.connections += 1
            if self.mode == "probe_only":
                self._held.append(conn)
                self._sock.close()  # queued and later connections are refused or reset
                return
            self._held.append(conn)

    def __enter__(self) -> Listener:
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        for conn in self._held:
            conn.close()
        try:
            self._sock.close()
        except OSError:
            return


def closed_address() -> str:
    """``host:port`` of a local port nothing listens on."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return f"127.0.0.1:{sock.getsockname()[1]}"


# --------------------------------------------------------------------------- synthetic live tests
def live_test(name: str, body: str = "assert True", marks: tuple = (), fail_first: bool = False) -> str:
    """Source of ``test_<name>.py``: it writes a witness line to ``$LIVE_STATE_DIR/ran.log`` when it really runs.

    ``fail_first`` makes the test fail on its first execution and pass on any later one (fail-then-pass).
    """
    marks_text = "".join(f"@pytest.mark.{m}\n" for m in marks)
    check = f"    assert (Path(state) / 'ran.log').read_text().split().count({name!r}) >= 2\n" if fail_first else ""
    return (
        "import os\nfrom pathlib import Path\n\nimport pytest\n\n\n"
        f"{marks_text}def test_{name}():\n    state = os.environ.get('LIVE_STATE_DIR')\n    if state:\n"
        f"        with (Path(state) / 'ran.log').open('a', encoding='utf-8') as handle:\n            handle.write({name!r} + '\\n')\n"
        f"{check}    {body}\n"
    )


def ran(state: Path) -> list[str]:
    """The sorted witness lines: exactly which synthetic tests executed, and how many times."""
    log = Path(state) / "ran.log"
    return sorted(log.read_text(encoding="utf-8").split()) if log.is_file() else []


def project_with(root: Path, live: dict, other: dict | None = None) -> Path:
    """A synthetic project whose live folder holds ``live`` (name -> source); ``other`` are extra files (path -> source)."""
    tests = {f"{LIVE_DIR}/test_{name}.py": source for name, source in live.items()}
    root.mkdir(parents=True, exist_ok=True)  # make_project writes pytest.ini into an existing directory
    make_project(root, {**tests, **(other or {})})
    return root


# --------------------------------------------------------------------------- driving the CLI
def cli_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "GITHUB_", "RUNNER_", "LIVE_"))}
    env.update({"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "AC_ENFORCE_STRICT": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    env.update(extra or {})
    return env


def run_cli(args: list, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    """``python scripts/ci/post_merge_suite.py <args>`` as a child process, as the workflow runs it."""
    try:
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(cwd), env=cli_env(env), capture_output=True, text=True, timeout=240, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        message = f"cannot run the suite CLI: {exc}"
        raise AssertionError(message) from exc


def read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        message = f"cannot read {path}: {exc}"
        raise AssertionError(message) from exc


def live_run(project: Path, out: Path, address: str, *, limit: str = "2", extra_env: dict | None = None, command: list | None = None):
    """First execution of the live lane; returns (completed process, report dict or None, failures file text)."""
    report, failures = out / "live-first-run-report.json", out / "live-first-run-failures.txt"
    out.mkdir(parents=True, exist_ok=True)
    env = {"LIVE_DB_ADDRESS": address, "LIVE_DB_STARTUP_LIMIT": limit, "RUNNER_NAME": "live-run-machine", **(extra_env or {})}
    proc = run_cli(["run", "--lane", "live", "--report", str(report), "--failures", str(failures), "--", *(command or LIVE_COMMAND)], project, env)
    return proc, (read_json(report) if report.is_file() else None), (failures.read_text(encoding="utf-8") if failures.is_file() else None)


def live_retry(project: Path, out: Path, address: str, failures: Path, *, extra_env: dict | None = None):
    report = out / "live-retry-report.json"
    env = {"LIVE_DB_ADDRESS": address, "LIVE_DB_STARTUP_LIMIT": "2", "RUNNER_NAME": "live-retry-machine", **(extra_env or {})}
    proc = run_cli(["retry", "--lane", "live", "--failures", str(failures), "--report", str(report), "--", *LIVE_COMMAND], project, env)
    return proc, (read_json(report) if report.is_file() else None)


def report(results: dict, *, skips: dict | None = None, reachable: bool | None = None, runner: str = "runner", exitstatus: int | None = None) -> dict:
    """A per-test lane report in the shape ``_lane_report_plugin`` writes (``json.dumps`` is the real serializer)."""
    failed = any(s in ("failed", "error") for s in results.values())
    payload = {
        "runner": runner,
        "exitstatus": (1 if failed else 0) if exitstatus is None else exitstatus,
        "expected": len(results),
        "ran": len(results),
        "collection_errors": [],
        "results": dict(sorted(results.items())),
        "skip_reasons": dict(skips or {}),
    }
    if reachable is not None:
        payload["reachability"] = {"reachable": reachable, "detail": "" if reachable else "no connection"}
    return payload


def live_report(results: dict, skips: dict | None = None, runner: str = "live-run-machine") -> dict:
    return report(results, skips=skips, reachable=True, runner=runner)


class Verdict(NamedTuple):
    proc: subprocess.CompletedProcess
    file: dict | None
    path: Path


def verdict_cli(base: Path, *, first=None, retry=None, live_first=None, live_retry=None, results: dict | None = None, lane: str = "correctness", env: dict | None = None) -> Verdict:
    """Seed the reports as artifacts and run ``verdict`` as a child process; read the written file back.

    ``results`` overrides the dependency results (RUN_RESULT, RETRY_RESULT, LIVE_RUN_RESULT, LIVE_RETRY_RESULT); the default
    is every job that produced a report ``success`` and the others ``skipped``.
    """
    seeded = {CORR_FIRST: first, CORR_RETRY: retry, LIVE_FIRST: live_first, LIVE_RETRY: live_retry}
    try:
        for (name, rel), data in seeded.items():
            if data is not None:
                target = base / "artifacts" / name / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        (base / "artifacts").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        message = f"cannot seed the artifacts: {exc}"
        raise AssertionError(message) from exc
    given = {
        "RUN_RESULT": "success" if first is not None else "skipped",
        "RETRY_RESULT": "success" if retry is not None else "skipped",
        "LIVE_RUN_RESULT": "success" if live_first is not None else "skipped",
        "LIVE_RETRY_RESULT": "success" if live_retry is not None else "skipped",
        **(results or {}),
    }
    out = base / "post-merge-verdict.json"
    proc = run_cli(["verdict", "--artifacts", str(base / "artifacts"), "--output", str(out), "--lane", lane], base, {**given, **(env or {})})
    return Verdict(proc, read_json(out) if out.is_file() else None, out)


def need_file(result: Verdict) -> dict:
    """The verdict file, or an assertion failure that says why there is none."""
    if result.file is None:
        message = f"`verdict` wrote no file (exit {result.proc.returncode}):\n{result.proc.stderr[-1200:]}"
        raise AssertionError(message)
    return result.file


def need_live(result: Verdict) -> dict:
    """The verdict file's ``live_database`` object, or an assertion failure naming its absence."""
    live = need_file(result).get("live_database")
    CHECK.assertIsInstance(live, dict, f"the verdict file has no live_database object: keys {sorted(result.file)}")
    return live


def exit_status_cli(verdict_path: Path) -> int:
    return run_cli(["exit-status", "--verdict-file", str(verdict_path)], verdict_path.parent).returncode


# --------------------------------------------------------------------------- driving the workflow
def point_at(wf: WorkflowRun, address: str, limit: str = "2") -> None:
    """Substitute the stand-in database address (and a short start-up limit) wherever the workflow declares them."""
    replaced = 0
    holders = [wf.doc]
    for job in (wf.doc.get("jobs") or {}).values():
        holders += [job, *(job.get("steps") or [])]
    for holder in holders:
        env = holder.get("env")
        if isinstance(env, dict) and "LIVE_DB_ADDRESS" in env:
            env["LIVE_DB_ADDRESS"] = address
            replaced += 1
        if isinstance(env, dict) and "LIVE_DB_STARTUP_LIMIT" in env:
            env["LIVE_DB_STARTUP_LIMIT"] = limit
    if not replaced:
        message = "the workflow declares no LIVE_DB_ADDRESS env key, so a stand-in database cannot be substituted"
        raise AssertionError(message)


class LiveDrive(NamedTuple):
    run: JobResult
    retry: JobResult
    live_run: JobResult
    live_retry: JobResult
    verdict: JobResult
    file: dict | None
    wf: WorkflowRun
    state: Path


def has_job(wf: WorkflowRun, job_id: str) -> None:
    """Fail (as an assertion, not a harness error) when the workflow lacks the job."""
    if job_id not in (wf.doc.get("jobs") or {}):
        message = f"post-merge-suite.yml has no job {job_id!r}"
        raise AssertionError(message)


@contextmanager
def workflow(api: FakeGitHub, live: dict, other: dict | None, address: str, *, run_number: int = 5):
    """A ``WorkflowRun`` of the suite workflow over a synthetic project; yields ``(wf, state dir)``."""
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        project_with(base / "project", live, other)
        (base / "state").mkdir()
        env = {"GITHUB_RUN_ID": str(100 + run_number), "GITHUB_SHA": "1" * 40, "LIVE_STATE_DIR": str(base / "state")}
        wf = WorkflowRun(WORKFLOW, base / "project", base / "scratch", env, api.url)
        point_at(wf, address)
        yield wf, base / "state"


def drive_all(api: FakeGitHub, live: dict, other: dict | None, address: str, *, run_number: int = 5) -> LiveDrive:
    """Execute run -> retry -> live_run -> live_retry -> verdict verbatim over real child pytest sessions."""
    with workflow(api, live, other, address, run_number=run_number) as (wf, state):
        for job in ("live_run", "live_retry"):
            has_job(wf, job)
        run = wf.execute_job("run")
        retry = wf.execute_job("retry", {"run": run})
        live_first = wf.execute_job("live_run")
        live_second = wf.execute_job("live_retry", {"live_run": live_first})
        needs = {"run": run, "retry": retry, "live_run": live_first, "live_retry": live_second}
        verdict = wf.execute_job("verdict", needs)
        file = wf.artifacts.read_json("post-merge-verdict", "post-merge-verdict.json") if "post-merge-verdict" in wf.artifacts.names() else None
        copied = Path(tempfile.mkdtemp(prefix="state-copy-"))  # outside ``base``: that directory is removed when the with block exits
        (copied / "ran.log").write_text("\n".join(ran(state)) + "\n" if ran(state) else "", encoding="utf-8")
        return LiveDrive(run, retry, live_first, live_second, verdict, file, wf, copied)


def drive_verdict_job(api: FakeGitHub, artifacts: dict, *, run="success", retry="skipped", live_run_result="success", live_retry_result="skipped", run_number=5):
    """Execute only the ``verdict`` job with the given dependency results; ``artifacts`` maps (name, file) -> dict (JSON-serialised here).

    Returns an object with ``run``, ``retry``, ``verdict`` and ``file`` (the uploaded verdict artifact, parsed or None), so
    ``_ending_harness.expect_did_not_complete`` reads it. The live jobs' results are the hosting service's answer, supplied.
    """
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        project_with(base / "project", {})
        wf = WorkflowRun(WORKFLOW, base / "project", base / "scratch", {"GITHUB_RUN_ID": str(100 + run_number), "GITHUB_SHA": "1" * 40}, api.url)
        try:
            for (name, rel), data in artifacts.items():
                source = base / "seed" / name / rel
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(json.dumps(data), encoding="utf-8")
                wf.artifacts.upload(name, [(rel, source)])
        except OSError as exc:
            message = f"cannot seed artifact {name!r}: {exc}"
            raise AssertionError(message) from exc
        needs = {
            "run": JobResult("run", run),
            "retry": JobResult("retry", retry),
            "live_run": JobResult("live_run", live_run_result),
            "live_retry": JobResult("live_retry", live_retry_result),
        }
        if "live_run" not in (wf.doc.get("jobs") or {}):
            message = "post-merge-suite.yml has no job 'live_run'"
            raise AssertionError(message)
        verdict = wf.execute_job("verdict", needs)
        file = wf.artifacts.read_json("post-merge-verdict", "post-merge-verdict.json") if "post-merge-verdict" in wf.artifacts.names() else None
        return type("Drive", (), {"run": needs["run"], "retry": needs["retry"], "verdict": verdict, "file": file})()


def seeded(first=None, retry=None, live_first=None, live_retry=None) -> dict:
    """Map the given reports to the artifact keys the verdict job downloads."""
    pairs = {CORR_FIRST: first, CORR_RETRY: retry, LIVE_FIRST: live_first, LIVE_RETRY: live_retry}
    return {key: data for key, data in pairs.items() if data is not None}


class LiveNoticeCase(EndingTestCase):
    """The notice test case (fake issue service) plus a fake REST API for the verdict job's history reads."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = FakeGitHub()

    @classmethod
    def tearDownClass(cls):
        cls.api.close()
        super().tearDownClass()


__all__ = ["CHECK"]
