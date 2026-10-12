"""Test infrastructure for TQ-600a-13-iii (the post-merge-red notice). Not a test: underscore-named.

* ``FakeIssueService`` -- a STATEFUL recording fake of the issue and workflow-run REST endpoints on
  127.0.0.1. It honours the label / state / sort / direction / per_page / page query the way the
  hosting service does (default page of 30, here lowered on request), includes pull requests in the
  issue listing (as the real service does), can silently DROP labels on create, and can refuse every write.
  It records every request and every write ATTEMPT, so a test asserts what the server saw.
* ``ScratchRepo`` -- a real git repository with a merge commit and a side-branch commit.
* ``make_verdict`` -- builds the verdict file with the REAL producer (``post_merge_suite.build_verdict_file``).
* ``NoticeTestCase`` -- shared setUpClass/setUp: one server per class, state reset per test.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple
from unittest import mock
from urllib.parse import parse_qs, urlparse

REPO = "example/leafcutter-ai"
LABEL = "post-merge-red"
SERVER = "https://github.com"
STATE_RE = re.compile(r"<!-- post-merge-suite-state v2 (\{.*?\}) -->")
_ISSUES = re.compile(rf"{re.escape(f'/repos/{REPO}/issues')}(?:/(\d+)(/comments)?)?")
_RUNS = re.compile(rf"{re.escape(f'/repos/{REPO}/actions/workflows/')}[^/]+/runs")
_LABELS = re.compile(rf"{re.escape(f'/repos/{REPO}/issues/')}(\d+)/labels")
_ARTIFACTS = re.compile(rf"{re.escape(f'/repos/{REPO}/actions/runs/')}(\d+)/artifacts")


def import_production(module):
    """Import a production module; absence is the specified-but-unbuilt state, reported as such."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        message = f"{module} is not implemented yet: {exc}"
        raise AssertionError(message) from exc


# --------------------------------------------------------------------------- the fake service
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return None

    def _dispatch(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = {"_unparseable": raw.decode("utf-8", "replace")}
        code, payload = self.server.service.handle(method, self.path, body)
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802 -- http.server naming
        self._dispatch("GET")

    def do_POST(self):  # noqa: N802
        self._dispatch("POST")

    def do_PATCH(self):  # noqa: N802
        self._dispatch("PATCH")

    def do_PUT(self):  # noqa: N802
        self._dispatch("PUT")

    def do_DELETE(self):  # noqa: N802
        self._dispatch("DELETE")


class FakeIssueService:
    """Serves a stated set of issues and workflow runs; records requests and write attempts."""

    def __init__(self):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.service = self
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()
        self.reset()

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def reset(self, *, default_per_page=30, drop_labels=False, labels_override=None, refuse_writes=False, add_label_sticks=False):
        """``add_label_sticks``: POST /issues/N/labels really adds the label (create may still drop it)."""
        self.issues, self.comments, self.runs = {}, [], []
        self.artifacts = {}  # run id -> artifact names served by GET /actions/runs/{id}/artifacts
        self.add_label_sticks = add_label_sticks
        self.requests, self.write_attempts = [], []
        self.default_per_page, self.drop_labels = default_per_page, drop_labels
        self.labels_override, self.refuse_writes = labels_override, refuse_writes

    def add_issue(self, number, *, title="an issue", body="", labels=(), state="open", pull_request=False):
        self.issues[number] = {"number": number, "title": title, "body": body, "state": state, "state_reason": None, "labels": list(labels), "pull_request": pull_request}

    def _render(self, issue):
        out = {k: v for k, v in issue.items() if k != "pull_request"}
        out["labels"] = [{"name": name} for name in issue["labels"]]
        out["html_url"] = f"{SERVER}/{REPO}/issues/{issue['number']}"
        if issue["pull_request"]:
            out["pull_request"] = {"url": f"{SERVER}/{REPO}/pull/{issue['number']}"}
        return out

    def handle(self, method, raw_path, body):
        parsed = urlparse(raw_path)
        query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
        self.requests.append((method, raw_path))
        if method != "GET":
            self.write_attempts.append({"method": method, "path": parsed.path, "body": body})
            if self.refuse_writes:
                return 403, {"message": "Resource not accessible by integration"}
        labels_match, artifacts_match = _LABELS.fullmatch(parsed.path), _ARTIFACTS.fullmatch(parsed.path)
        if method == "POST" and labels_match:
            return self._add_labels(int(labels_match.group(1)), body or {})
        if method == "GET" and artifacts_match:
            names = self.artifacts.get(int(artifacts_match.group(1)), [])
            return 200, {"total_count": len(names), "artifacts": [{"name": n, "expired": False} for n in names]}
        match = _ISSUES.fullmatch(parsed.path)
        if method == "GET" and match and not match.group(1):
            return 200, self._list(query)
        if method == "GET" and _RUNS.fullmatch(parsed.path):
            return 200, self._runs(query)
        if match and method == "POST" and not match.group(1):
            return self._create(body or {})
        if match and match.group(1) and int(match.group(1)) not in self.issues:
            return 404, {"message": "Not Found"}
        if match and method == "POST" and match.group(2):
            self.comments.append({"number": int(match.group(1)), "body": (body or {}).get("body", "")})
            return 201, {"id": len(self.comments), "body": (body or {}).get("body", "")}
        if match and method == "PATCH" and match.group(1) and not match.group(2):
            issue = self.issues[int(match.group(1))]
            issue.update({k: v for k, v in (body or {}).items() if k in ("title", "body", "state", "state_reason")})
            return 200, self._render(issue)
        return 404, {"message": "Not Found"}

    def _list(self, query):
        wanted = [name for name in query.get("labels", "").split(",") if name]
        state = query.get("state", "open")
        items = [i for i in self.issues.values() if state in ("all", i["state"]) and all(n in i["labels"] for n in wanted)]
        items.sort(key=lambda i: i["number"], reverse=query.get("direction", "desc") == "desc")
        per_page = min(int(query.get("per_page", self.default_per_page)), 100)
        page = int(query.get("page", 1))
        return [self._render(i) for i in items[(page - 1) * per_page : page * per_page]]

    def _runs(self, query):
        """The run list as the service serves it: ``branch`` filters, newest first, ``per_page`` truncates."""
        runs = [r for r in self.runs if "branch" not in query or r.get("head_branch") == query["branch"]]
        runs.sort(key=lambda r: r.get("run_number", 0), reverse=True)
        runs = runs[: min(int(query.get("per_page", 30)), 100)]
        return {"total_count": len(runs), "workflow_runs": runs}

    def _add_labels(self, number, body):
        if number not in self.issues:
            return 404, {"message": "Not Found"}
        issue = self.issues[number]
        if self.add_label_sticks:
            issue["labels"] += [n for n in body.get("labels", []) if n not in issue["labels"]]
        return 200, [{"name": name} for name in issue["labels"]]

    def _create(self, body):
        labels = list(body.get("labels") or [])
        if self.drop_labels:
            labels = list(self.labels_override or [])
        number = max(self.issues, default=0) + 1
        self.add_issue(number, title=body.get("title", ""), body=body.get("body", ""), labels=labels)
        return 201, self._render(self.issues[number])

    # ---- what the server saw
    def writes(self):
        """The write attempts as sorted (kind, issue number or None) pairs."""
        return sorted(((kind, number) for kind, number, _ in classify_writes(self.write_attempts)), key=str)

    def writes_of(self, kind):
        return [(number, body) for k, number, body in classify_writes(self.write_attempts) if k == kind]


def classify_writes(attempts):
    """Name each recorded write attempt: create | edit | close | comment | label | other."""
    out = []
    for attempt in attempts:
        label_match = _LABELS.fullmatch(attempt["path"])
        if label_match and attempt["method"] == "POST":
            out.append(("label", int(label_match.group(1)), attempt["body"] or {}))
            continue
        match = _ISSUES.fullmatch(attempt["path"])
        number = int(match.group(1)) if match and match.group(1) else None
        body, method = attempt["body"] or {}, attempt["method"]
        if not match:
            kind = "other"
        elif method == "POST" and match.group(2):
            kind = "comment"
        elif method == "POST" and number is None:
            kind = "create"
        elif method == "PATCH" and number is not None and body.get("state") == "closed":
            kind = "close"
        elif method == "PATCH" and number is not None:
            kind = "edit"
        else:
            kind = "other"
        out.append((kind, number, body))
    return out


# --------------------------------------------------------------------------- run records, verdicts, parsing
def run_record(number, conclusion="success", head_sha="0" * 40, status="completed", event="push", branch="main"):
    """A workflow-run record as the REST API serves it; id is 100 + run_number."""
    run_id = 100 + number
    return {
        "id": run_id,
        "run_number": number,
        "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "event": event,
        "head_branch": branch,
        "head_sha": head_sha,
        "html_url": f"{SERVER}/{REPO}/actions/runs/{run_id}",
    }


def make_verdict(kind, *, run_id, head_sha, failing=(), ref="refs/heads/main", event="push"):
    """Build a verdict file with the REAL producer (``build_verdict_file``): green | red | did_not_complete."""
    suite = import_production("scripts.ci.post_merge_suite")
    env = {"GITHUB_SHA": head_sha, "GITHUB_REF": ref, "GITHUB_EVENT_NAME": event, "GITHUB_RUN_ID": str(run_id), "GITHUB_REPOSITORY": REPO, "GITHUB_SERVER_URL": SERVER}
    results = {"tests/test_lane.py::test_fine": "passed", "tests/test_lane.py::test_also_fine": "passed"}
    if kind == "did_not_complete":
        return suite.build_verdict_file(None, None, env)
    results.update(dict.fromkeys(failing, "failed"))
    first = {"results": results, "exitstatus": 1 if failing else 0, "ran": len(results), "expected": len(results), "runner": "runner-run"}
    return suite.build_verdict_file(first, None, env)


def state_block(text):
    """The state block of a description or comment as a dict, or None when it carries none."""
    match = STATE_RE.search(text or "")
    return json.loads(match.group(1)) if match else None


def visible_text(text):
    """What a reader sees as prose: the state block and inline code spans removed."""
    return re.sub(r"`[^`]*`", "", STATE_RE.sub("", text or ""))


def seconds_ago(iso_text):
    """Seconds between an ISO-8601 timestamp (a trailing Z or no zone means UTC) and now."""
    when = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).total_seconds()


def old_description(run_id, red_since="2026-10-01T00:00:00+00:00", failing=("tests/test_old.py::test_gone",)):
    """A description as an earlier red run would have left it (state block built here, as JSON)."""
    block = {"run_id": run_id, "verdict": "red", "stage": None, "failing": list(failing), "run_url": f"{SERVER}/{REPO}/actions/runs/{run_id}",
             "head_sha": "1" * 40, "anchor_sha": None, "commits": [], "commits_omitted": 0, "red_since": red_since}
    return f"Old state.\n\n<!-- post-merge-suite-state v2 {json.dumps(block)} -->\n"


# --------------------------------------------------------------------------- scratch repository
def _git(path, *args):
    argv = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args]
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        message = f"git {args} failed in {path}: {exc}"
        raise AssertionError(message) from exc


class ScratchRepo:
    """Six commits: A, G (green), then M1 on main, S on a side branch cut from G, MG (merge of S), R (red head)."""

    SUBJECT_M1 = "Merge #12 @octocat <b>fix</b>"

    def __init__(self, path):
        self.path = Path(path)
        try:
            self.path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            message = f"cannot create {self.path}: {exc}"
            raise AssertionError(message) from exc
        _git(self.path, "init", "-q", "-b", "main")
        self.a = self._commit("A initial")
        self.g = self._commit("G last green")
        _git(self.path, "checkout", "-q", "-b", "side")
        self.s = self._commit("S side-branch work")
        _git(self.path, "checkout", "-q", "main")
        self.m1 = self._commit(self.SUBJECT_M1)
        _git(self.path, "merge", "-q", "--no-ff", "side", "-m", "MG merge side")
        self.mg = _git(self.path, "rev-parse", "HEAD")
        self.r = self._commit("R red head")

    def _commit(self, subject):
        _git(self.path, "commit", "-q", "--allow-empty", "-m", subject)
        return _git(self.path, "rev-parse", "HEAD")

    @property
    def expected_range(self):
        """Every commit reachable from R and not from G (all parents followed)."""
        return {self.m1, self.s, self.mg, self.r}


# --------------------------------------------------------------------------- applying a verdict
class Applied(NamedTuple):
    code: int
    log: str


@contextmanager
def captured_logs():
    """Collect every log record emitted while the block runs, whatever logger emitted it."""
    lines, root = [], logging.getLogger()

    class _Collect(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    handler, level = _Collect(), root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield lines
    finally:
        root.removeHandler(handler)
        root.setLevel(level)


class NoticeTestCase(unittest.TestCase):
    """One fake server (and optionally one scratch repository) per class; service state reset per test."""

    needs_repo = False

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.svc = FakeIssueService()
        cls.repo = ScratchRepo(cls.tmp / "repo") if cls.needs_repo else None

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()
        cls._tmp.cleanup()

    def setUp(self):
        self.svc.reset()

    @property
    def notice(self):
        return import_production("scripts.ci.post_merge_notice")

    def apply(self, verdict, run_id, download_outcome=None):
        """Run the notice job's ``apply`` entry point; ``verdict`` None means the artifact is absent.

        ``download_outcome`` is the download step's outcome as the workflow passes it (success | failure).
        """
        path = self.tmp / "post-merge-verdict.json"
        try:
            path.unlink(missing_ok=True)
            if verdict is not None:
                path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            message = f"cannot stage the verdict file: {exc}"
            raise AssertionError(message) from exc
        repo_dir = self.repo.path if self.repo else self.tmp
        argv = ["apply", "--api-url", self.svc.url, "--repo", REPO, "--repo-dir", str(repo_dir), "--run-id", str(run_id), "--verdict-file", str(path)]
        if download_outcome is not None:
            argv += ["--download-outcome", download_outcome]
        with captured_logs() as lines, mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}):
            code = self.notice.main(argv)
        return Applied(code, "\n".join(lines))
