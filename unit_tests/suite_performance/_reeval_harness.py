"""Test infrastructure for TQ-600a-13-xv (re-evaluating every open hold when the verdict changes). Not a test: underscore-named.

* ``ReevalService`` -- a STATEFUL recording fake of exactly the endpoints the re-evaluation may touch, on 127.0.0.1:
  the open pull requests (honours ``state`` / ``base`` / ``per_page`` / ``page``, serves a page at most ``pr_page_cap``
  long and says so with a ``Link: rel="next"`` header), the correctness suite's run list, the hold workflow's run list
  (honours ``head_sha`` / ``event`` / ``per_page``; INSERTION order, so "the latest" must come from ``run_number``),
  other workflows' runs, and ``POST /actions/runs/{id}/rerun`` (refuses the ids in ``refuse`` with 403). Every other
  write answers 404 and is recorded, so a test asserts what the server SAW, not what the code claims.
* ``seed_world`` -- the shared double: open pull requests with hold runs that are completed, in progress, 29 and 31 days
  old, one with no hold run at all, plus a pull request on another base and a closed one that must be left alone.
* ``run_reeval`` -- calls the REAL ``scripts.ci.post_merge_reeval.main`` in-process, through the REAL REST client.

CONTRACT SHARED BY ALL TEST FILES (the interface the python-coder builds):

``python scripts/ci/post_merge_reeval.py --api-url URL --repo OWNER/NAME --event-path PATH --output-file PATH``
(also ``post_merge_reeval.main(argv) -> int``). Token from env ``GITHUB_TOKEN``. ``--event-path`` is the
``workflow_run`` event file (``GITHUB_EVENT_PATH``): ``workflow_run.name``, ``.id``, ``.head_sha``. ``--output-file`` is
``GITHUB_OUTPUT``: exactly ONE line ``unrerunnable=<single-line JSON list of {pr, head_sha, reason}>`` is appended on
every run that reaches a decision (``[]`` when nothing is unrerunnable or nothing was re-run), and the same JSON is printed.
Exit 0 whenever the decision ran, whatever it named; non-zero (and no re-run requested) when the history or the pull
request list cannot be read.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from unittest import mock

from ._notice_fakes import REPO, SERVER, captured_logs, import_production, run_record

SUITE_NAME, PROOF_NAME, TIMING_NAME = "Post-merge suite", "Post-merge fix proof", "Post-merge timing suite"
REEVAL_MODULE = "scripts.ci.post_merge_reeval"
HOLD_FILE, SUITE_FILE = "post-merge-hold.yml", "post-merge-suite.yml"
_PREFIX = f"/repos/{REPO}"
_RUNS = re.compile(r"/actions/workflows/([^/]+)/runs")
_RERUN = re.compile(r"/actions/runs/(\d+)/rerun")
_JOBS = re.compile(r"/actions/runs/(\d+)/jobs")
_ONE_RUN = re.compile(r"/actions/runs/(\d+)")
SHAS = {name: char * 40 for name, char in zip("ABCDEFGH", "abcdef01", strict=True)}
OPEN_PRS = {"A": 11, "B": 12, "C": 13, "D": 14, "E": 15, "F": 16}  # the six that count; G (other base) and H (closed) do not


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
        code, payload, headers = self.server.service.handle(method, self.path, body)
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for name, value in headers.items():
            self.send_header(name, value)
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


class ReevalService:
    """Serves pull requests and workflow runs; records every request and every write attempt."""

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

    def reset(self, *, pr_page_cap=2):
        self.prs, self.pr_page_cap = [], pr_page_cap
        self.workflows = {}  # workflow file name -> run records, served in insertion order
        self.refuse, self.failing = set(), []  # run ids whose re-run is refused with 403; path fragments that answer 500
        self.requests, self.write_attempts = [], []

    # ---- routing
    def handle(self, method, raw_path, body):
        parsed = urlparse(raw_path)
        query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
        self.requests.append((method, raw_path))
        if method != "GET":
            self.write_attempts.append({"method": method, "path": parsed.path, "body": body})
        if method == "GET" and any(fragment in parsed.path for fragment in self.failing):
            return 500, {"message": "Server Error"}, {}
        rest = parsed.path[len(_PREFIX) :] if parsed.path.startswith(_PREFIX) else None
        if rest is None:
            return 404, {"message": "Not Found"}, {}
        if method == "GET" and rest == "/pulls":
            return self._pulls(query)
        runs_match = _RUNS.fullmatch(rest) if method == "GET" else None
        if runs_match:
            return 200, self._runs(self.workflows.get(runs_match.group(1), []), query), {}
        if method == "GET" and rest == "/actions/runs":
            return 200, self._runs([r for runs in self.workflows.values() for r in runs], query), {}
        if method == "GET" and _JOBS.fullmatch(rest):
            return 200, {"total_count": 0, "jobs": []}, {}
        one_run = _ONE_RUN.fullmatch(rest) if method == "GET" else None
        if one_run:  # one run with its workflow `path` (TQ-600a-13-xi: the client reads it before it re-runs it)
            found = [r for runs in self.workflows.values() for r in runs if r["id"] == int(one_run.group(1))]
            return (200, found[0], {}) if found else (404, {"message": "Not Found"}, {})
        rerun_match = _RERUN.fullmatch(rest) if method == "POST" else None
        if rerun_match:
            return self._rerun(int(rerun_match.group(1)))
        return 404, {"message": "Not Found"}, {}

    def _pulls(self, query):
        wanted = [p for p in self.prs if query.get("state", "open") in ("all", p["state"]) and query.get("base", p["base"]["ref"]) == p["base"]["ref"]]
        size, page = min(int(query.get("per_page", 30)), self.pr_page_cap), int(query.get("page", 1))
        headers = {}
        if page * size < len(wanted):
            headers["Link"] = f'<{self.url}{_PREFIX}/pulls?{urlencode({**query, "per_page": size, "page": page + 1})}>; rel="next"'
        return 200, wanted[(page - 1) * size : page * size], headers

    @staticmethod
    def _runs(runs, query):
        found = [
            r
            for r in runs
            if query.get("head_sha", r.get("head_sha")) == r.get("head_sha")
            and query.get("event", r.get("event")) == r.get("event")
            and query.get("branch", r.get("head_branch")) == r.get("head_branch")
            and ("status" not in query or query["status"] in (r.get("status"), r.get("conclusion")))
            and not (query.get("exclude_pull_requests") == "true" and r.get("event") == "pull_request")
        ]
        found = found[: min(int(query.get("per_page", 30)), 100)]
        return {"total_count": len(found), "workflow_runs": found}

    def _rerun(self, run_id):
        if run_id not in {r["id"] for runs in self.workflows.values() for r in runs}:
            return 404, {"message": "Not Found"}, {}
        if run_id in self.refuse:
            return 403, {"message": "Resource not accessible by integration"}, {}
        return 201, {}, {}

    # ---- what the server saw
    def rerun_ids(self):
        """The run ids a re-run was requested for (refused ones included), sorted."""
        found = [_RERUN.fullmatch(a["path"][len(_PREFIX) :]) for a in self.write_attempts if a["method"] == "POST"]
        return sorted(int(m.group(1)) for m in found if m)

    def other_writes(self):
        """Every write attempt that is NOT a re-run request."""
        return [a for a in self.write_attempts if not (a["method"] == "POST" and _RERUN.fullmatch(a["path"][len(_PREFIX) :]))]

    def reads_of(self, fragment):
        return [raw for method, raw in self.requests if method == "GET" and fragment in urlparse(raw).path]


# --------------------------------------------------------------------------- records
def _stamp(when):
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def hold_run(number, sha, *, status="completed", event="pull_request_target", age_days=1.0, conclusion="success"):
    """A run of ``post-merge-hold.yml`` as the API serves it; its id is 1000 + number."""
    run = run_record(number, conclusion, head_sha=sha, status=status, event=event, branch=f"pr-{sha[:7]}")
    run["id"] = 1000 + number
    run["html_url"] = f"{SERVER}/{REPO}/actions/runs/{run['id']}"
    run["path"] = f".github/workflows/{HOLD_FILE}"
    run["head_repository"] = {"full_name": REPO}  # as the API serves it; the client reads it before a re-run (TQ-600a-13-xi)
    run["created_at"] = run["run_started_at"] = _stamp(datetime.now(timezone.utc) - timedelta(days=age_days))
    return run


def pull_request(number, sha, *, base="main", state="open"):
    return {"number": number, "state": state, "base": {"ref": base}, "head": {"sha": sha}}


def seed_world(svc, *, refuse=()):
    """Open pull requests A-F (11-16, three pages of two) with hold runs of every state, plus G (base ``release``) and H (closed).

    A  #3 older and #5 latest, both completed, + #7 of event ``pull_request`` (a PR-edited copy: never re-run)  -> re-run 1005
    B  #4 completed, #6 in progress (the latest)                                                                -> skipped
    C  #8 completed, 31 days old                                                                                -> older_than_30_days
    D  #9 completed (the one whose re-run is refused when 1009 is in ``refuse``)                                -> 1009
    E  no ``pull_request_target`` run (only an event-``pull_request`` one, #10)                                 -> no_hold_run
    F  #11 completed, 29 days old (inside the window)                                                           -> 1011
    G  #12 completed, base ``release``;  H  #13 completed, state closed                                         -> never touched
    A also has a higher-numbered run (#20) of ``ci.yml`` for the same head: never re-run.
    """
    s = SHAS
    svc.prs = [
        pull_request(11, s["A"]), pull_request(12, s["B"]), pull_request(13, s["C"]), pull_request(14, s["D"]),
        pull_request(15, s["E"]), pull_request(16, s["F"]),
        pull_request(17, s["G"], base="release"), pull_request(18, s["H"], state="closed"),
    ]  # fmt: skip
    ci_run = hold_run(20, s["A"])
    ci_run.update(id=2020, path=".github/workflows/ci.yml")
    svc.workflows[HOLD_FILE] = [
        hold_run(3, s["A"], age_days=2), hold_run(5, s["A"]), hold_run(7, s["A"], event="pull_request"),
        hold_run(4, s["B"]), hold_run(6, s["B"], status="in_progress"),
        hold_run(8, s["C"], age_days=31), hold_run(9, s["D"]), hold_run(10, s["E"], event="pull_request"),
        hold_run(11, s["F"], age_days=29), hold_run(12, s["G"]), hold_run(13, s["H"]),
    ]  # fmt: skip
    svc.workflows["ci.yml"] = [ci_run]
    svc.refuse = set(refuse)


def suite_history(svc, *rows):
    """Serve the correctness suite's runs: each row is ``(conclusion, status)`` or a bare conclusion; run N has id 100 + N."""
    runs = []
    for number, row in enumerate(rows, start=1):
        conclusion, status = row if isinstance(row, tuple) else (row, "completed")
        runs.append(run_record(number, conclusion, status=status))
    svc.workflows[SUITE_FILE] = runs


def expected_named(*, refused=()):
    """What the double must name: C (too old), E (no hold run) and every refused pull request, ordered by number."""
    named = {13: (SHAS["C"], "older_than_30_days"), 15: (SHAS["E"], "no_hold_run")}
    named.update({pr: (SHAS[name], f"rerun_refused_{status}") for pr, name, status in refused})
    return [{"pr": pr, "head_sha": sha, "reason": reason} for pr, (sha, reason) in sorted(named.items())]


# --------------------------------------------------------------------------- driving the entry point
def write_event(directory, name, run_id, head_sha, overrides=None):
    """Write a ``workflow_run`` event file (the real serializer) and return its path.

    A fix-proof run is a ``pull_request_target`` run of this repository (``head_repository.full_name`` is the repo); the
    suite's is a ``push``. ``overrides`` replaces keys of ``workflow_run`` (a value of None removes the key).
    """
    path = Path(directory) / "event.json"
    event = "pull_request_target" if name == PROOF_NAME else "push"
    run = {"id": run_id, "name": name, "head_sha": head_sha, "status": "completed", "event": event, "head_repository": {"full_name": REPO}}
    for key, value in (overrides or {}).items():
        if value is None:
            run.pop(key, None)
        else:
            run[key] = value
    payload = {"action": "completed", "workflow_run": run}
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as exc:
        message = f"cannot write the event file: {exc}"
        raise AssertionError(message) from exc
    return path


@dataclass
class Reeval:
    code: int
    lines: list  # every line appended to the output file
    log: str  # everything logged or printed

    @property
    def unrerunnable_lines(self):
        return [ln for ln in self.lines if ln.startswith("unrerunnable=")]

    @property
    def unrerunnable(self):
        """The decoded ``unrerunnable`` output, or None when no such output line was written."""
        found = self.unrerunnable_lines
        return json.loads(found[-1].split("=", 1)[1]) if found else None


def run_reeval(svc, directory, name, run_id, head_sha, overrides=None):
    """Call ``scripts.ci.post_merge_reeval.main`` with a ``workflow_run`` event for the named run, through the real REST client."""
    module = import_production(REEVAL_MODULE)
    out = Path(directory) / "github-output.txt"
    try:
        out.write_text("", encoding="utf-8")
    except OSError as exc:
        message = f"cannot stage the output file: {exc}"
        raise AssertionError(message) from exc
    event = write_event(directory, name, run_id, head_sha, overrides)
    argv = ["--api-url", svc.url, "--repo", REPO, "--event-path", str(event), "--output-file", str(out)]
    printed = io.StringIO()
    with captured_logs() as lines, contextlib.redirect_stdout(printed), mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}):
        code = module.main(argv)
    try:
        written = out.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        message = f"cannot read the output file: {exc}"
        raise AssertionError(message) from exc
    return Reeval(code, written, printed.getvalue() + "\n".join(lines))
