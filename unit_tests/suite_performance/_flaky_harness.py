"""Shared harness for the TQ-600a-13-xiii tests (pass-on-retry history, escalation and the flaky notice). Not a test.

* ``FlakyService`` -- the hold's recording fake (issues, run lists of both lanes) plus the two reads the verdict job
  adds: ``GET /actions/runs/{id}/artifacts`` (one ``post-merge-verdict`` artifact per run that has a blob) and
  ``GET /actions/artifacts/{id}/zip`` (the artifact's zip bytes, served directly: the redirect a real service
  answers with is the REST client's concern, not this fake's). Both are recorded with every other request.
* ``Earlier`` -- one earlier run of the window: its run record and what its verdict artifact is (ok | corrupt | badjson |
  missing).
* ``build`` -- a verdict file from the REAL producer (``post_merge_suite.build_verdict_file``) over real-shaped lane reports.
* ``FlakyCase`` -- ``seed`` the run history, ``run_verdict`` (the REAL ``post_merge_suite.main(["verdict", ...])``) and
  ``apply_notice`` (the REAL ``post_merge_notice.main(["apply", ...])``) over the fake, in-process.
"""

from __future__ import annotations

import inspect
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

from ._ending_harness import HEAD_SHA, VERDICT_ARTIFACT
from ._hold_harness import HoldService, HoldTestCase
from ._notice_fakes import REPO, SERVER, Applied, _Handler, captured_logs, import_production, run_record

SUITE = "scripts.ci.post_merge_suite"
FLAKY_LABEL = "post-merge-flaky"
RED_LABEL = "post-merge-red"
CONTROL_ID = "tests/test_lane.py::test_fine"
_PREFIX = f"/repos/{REPO}/actions"
_LISTED = re.compile(rf"{re.escape(_PREFIX)}/runs/(\d+)/artifacts")
_ZIPPED = re.compile(rf"{re.escape(_PREFIX)}/artifacts/(\d+)/zip")


def lane_id(name):
    """A correctness-lane node id."""
    return f"tests/test_shared_layout.py::test_{name}"


def run_id_of(number):
    """The id ``run_record`` gives run number ``number``."""
    return 100 + number


# --------------------------------------------------------------------------- the fake service
class Raw:
    """A response body that is bytes, not JSON."""

    def __init__(self, data):
        self.data = data


class _BinaryHandler(_Handler):
    def _dispatch(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = None
        code, payload = self.server.service.handle(method, self.path, body)
        data = payload.data if isinstance(payload, Raw) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/zip" if isinstance(payload, Raw) else "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class FlakyService(HoldService):
    """``HoldService`` that also serves earlier runs' verdict artifacts (``blobs``: run id -> zip bytes)."""

    def __init__(self):
        super().__init__()
        self._server.RequestHandlerClass = _BinaryHandler

    def reset(self, **kwargs):
        super().reset(**kwargs)
        self.blobs = {}

    def handle(self, method, raw_path, body):
        path = urlparse(raw_path).path
        listed, zipped = _LISTED.fullmatch(path), _ZIPPED.fullmatch(path)
        if method != "GET" or not (listed or zipped):
            return super().handle(method, raw_path, body)
        self.requests.append((method, raw_path))
        if listed:
            run_id = int(listed.group(1))
            found = [{"id": run_id * 10, "name": VERDICT_ARTIFACT, "expired": False}] if run_id in self.blobs else []
            return 200, {"total_count": len(found), "artifacts": found}
        data = self.blobs.get(int(zipped.group(1)) // 10)
        return (404, {"message": "Not Found"}) if data is None else (200, Raw(data))

    def paths(self):
        """The path of every GET the job made."""
        return [urlparse(raw).path for method, raw in self.requests if method == "GET"]

    def artifact_reads(self, number):
        """The artifact list / download requests that named run number ``number``."""
        run_id = run_id_of(number)
        return [p for p in self.paths() if p == f"{_PREFIX}/runs/{run_id}/artifacts" or p == f"{_PREFIX}/artifacts/{run_id * 10}/zip"]


# --------------------------------------------------------------------------- verdicts from the real producer
def _require(function, parameter):
    if parameter not in inspect.signature(function).parameters:
        message = f"{function.__name__} does not accept `{parameter}` yet: TQ-600a-13-xiii is not implemented"
        raise AssertionError(message)


def _env(run_id, head_sha, event="push"):
    return {"GITHUB_SHA": head_sha, "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": event, "GITHUB_RUN_ID": str(run_id), "GITHUB_REPOSITORY": REPO, "GITHUB_SERVER_URL": SERVER}


def reports(retried):
    """(first, retry) lane reports as ``_lane_report_plugin`` writes them: ``retried`` ids fail first and pass on retry."""
    results = {CONTROL_ID: "passed", **dict.fromkeys(retried, "failed")}
    first = {"runner": "runner-run", "exitstatus": 1 if retried else 0, "expected": len(results), "ran": len(results), "collection_errors": [], "results": results}
    retry = None
    if retried:
        retry = {"runner": "runner-retry", "exitstatus": 0, "expected": len(retried), "ran": len(retried), "collection_errors": [], "results": dict.fromkeys(retried, "passed")}
    return first, retry


def build(retried, *, run_id, head_sha=HEAD_SHA, lane="correctness", history=None, tunables=None):
    """A verdict file from ``build_verdict_file`` for a run in which ``retried`` ids failed and then passed."""
    suite = import_production(SUITE)
    first, retry = reports(retried)
    extra = {}
    for name, value in (("history", history), ("tunables", tunables)):
        if value is not None:
            _require(suite.build_verdict_file, name)
            extra[name] = value
    return suite.build_verdict_file(
        first, retry, _env(run_id, head_sha), run_result="success", retry_result="success" if retry else "skipped", first_state="ok", lane=lane, **extra
    )


def verdict_zip(verdict):
    """The zip a ``post-merge-verdict`` artifact download serves, written with the real JSON serializer."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("post-merge-verdict.json", json.dumps(verdict, indent=2) + "\n")
    return buffer.getvalue()


@dataclass
class Earlier:
    """One earlier run of the window; ``ids`` are the tests that passed on retry in it."""

    number: int
    ids: tuple = ()
    kind: str = "ok"  # ok | corrupt | badjson | missing
    conclusion: str = "success"
    status: str = "completed"

    def blob(self):
        if self.kind == "ok":
            return verdict_zip(build(self.ids, run_id=run_id_of(self.number)))
        if self.kind == "corrupt":
            return b"this is not a zip archive"
        if self.kind == "badjson":
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("post-merge-verdict.json", "{ not json")
            return buffer.getvalue()
        return None


# --------------------------------------------------------------------------- the test case
class FlakyCase(HoldTestCase):
    """The hold's test case over a ``FlakyService``; in-process verdict and notice entry points."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc.close()
        cls.svc = FlakyService()

    def seed(self, current_number, earlier):
        """Serve the run history (the current run still in progress) and the earlier runs' verdict artifacts."""
        runs = [run_record(current_number, status="in_progress")]
        for item in earlier:
            runs.append(run_record(item.number, item.conclusion, status=item.status))
            blob = item.blob()
            if blob is not None:
                self.svc.blobs[run_id_of(item.number)] = blob
        self.svc.runs, self.svc.timing_runs = runs, list(runs)

    def settle(self, number, conclusion):
        """The current run has ended: its record is completed with ``conclusion``."""
        self.svc.runs = [run_record(number, conclusion) if r["run_number"] == number else r for r in self.svc.runs]

    def run_verdict(self, retried, number, *, lane="correctness", environ=None):
        """``post_merge_suite.main(["verdict", ...])`` for the current run; return the verdict file it wrote."""
        suite = import_production(SUITE)
        base = Path(tempfile.mkdtemp(dir=self.tmp))
        first, retry = reports(retried)
        for rel, report in ((suite.FIRST_REPORT, first), (suite.RETRY_REPORT, retry)):
            if report is not None:
                (base / "artifacts" / rel).parent.mkdir(parents=True, exist_ok=True)
                (base / "artifacts" / rel).write_text(json.dumps(report, indent=2), encoding="utf-8")
        out = base / "post-merge-verdict.json"
        argv = ["verdict", "--artifacts", str(base / "artifacts"), "--output", str(out), "--lane", lane]
        argv += ["--api-url", self.svc.url, "--repo", REPO, "--run-id", str(run_id_of(number))]
        env = {**_env(run_id_of(number), HEAD_SHA), "GITHUB_TOKEN": "fake-token", "RUN_RESULT": "success", "RETRY_RESULT": "success" if retry else "skipped", **(environ or {})}
        with mock.patch.dict(os.environ, env), captured_logs():
            try:
                code = suite.main(argv)
            except SystemExit as exc:
                message = f"the verdict command does not accept the history options yet (exit {exc.code}): TQ-600a-13-xiii is not implemented"
                raise AssertionError(message) from exc
        self.assertEqual(0, code, "the verdict step exits 0 whenever it wrote a verdict")
        return json.loads(out.read_text(encoding="utf-8"))

    def apply_notice(self, verdict, number, conclusion, *, previous=None, token="fake-token"):
        """``post_merge_notice.main(["apply", ...])`` for run ``number`` (``previous`` is the earlier run's verdict)."""
        self.svc.runs = [run_record(number, conclusion, head_sha=verdict["head_sha"])]
        verdict_path = self.tmp / "post-merge-verdict.json"
        verdict_path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
        argv = ["apply", "--api-url", self.svc.url, "--repo", REPO, "--repo-dir", str(self.tmp), "--run-id", str(run_id_of(number)), "--verdict-file", str(verdict_path)]
        if previous is not None:
            previous_path = self.tmp / "previous-verdict.json"
            previous_path.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")
            argv += ["--previous-verdict-file", str(previous_path)]
        with captured_logs() as lines, mock.patch.dict(os.environ, {"GITHUB_TOKEN": token}):
            code = self.notice.main(argv)
        return Applied(code, "\n".join(lines))

    def flaky_create(self):
        """The one create body labelled flaky; an assertion failure (not an IndexError) when the job created none."""
        created = self.created(FLAKY_LABEL)
        self.assertEqual(1, len(created), f"one {FLAKY_LABEL} notice is created; the server saw {self.svc.writes()}")
        return created[0]

    def created(self, label):
        """The create bodies the server saw that carried ``label``."""
        return [body for _number, body in self.svc.writes_of("create") if label in (body.get("labels") or [])]
