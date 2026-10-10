"""Test infrastructure for TQ-600a-13-vii (the held pull request's one comment). Not a test: underscore-named.

* ``CommentService`` -- the hold's recording fake plus the pull-request comment endpoints: it serves a pull
  request's comments in PAGES with a real ``Link`` header (``rel="next"``), caps the page size the way the
  hosting service does (the cap is lowered on request so a handful of comments spans several pages), records
  every comment write ATTEMPT (create, edit, delete) apart from the issue writes, and can refuse or fail them.
  It applies an edit to whichever comment id it is given, so a test sees the damage of editing a stranger's.
* ``ForeignListener`` -- a second listener on another origin that records what reaches it (a ``Link`` header
  naming it must never be requested: the request would carry the job's write token).
* ``CommentTestCase`` -- the hold test case over a ``CommentService``; ``drive`` runs the REAL ``main`` with a real
  event file written by ``json.dump`` (the job's own entry point), ``own`` lists the check's own comments.
* ``notice_description`` -- a notice description built by the REAL producer chain (``post_merge_suite``'s verdict
  file, ``_notice_render.build_state`` and ``render_description``), never hand-typed.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple
from unittest import mock
from urllib.parse import parse_qs, urlparse

from ._app_fake import _LOCAL, AppService
from ._app_harness import SECRET_PREFIX, app_secrets, secrets_as_env
from ._ending_harness import CHECK
from ._hold_harness import DNC_JOBS, HOLD_MODULE, JOB_NAME, OBSERVER, RED_JOBS, WORKFLOW, HoldRun, HoldTestCase, JobOutcome, make_run, scratch_default_branch
from ._notice_fakes import REPO, _Handler, import_production, make_verdict

MARKER = "<!-- post-merge-suite-status v1 -->"
BOT = {"login": "github-actions[bot]", "type": "Bot", "id": 41898282}
HUMAN = {"login": "octocat", "type": "User", "id": 583231}
OTHER_BOT = {"login": "dependabot[bot]", "type": "Bot", "id": 49699333}
PR = 42
_LIST = re.compile(rf"{re.escape(f'/repos/{REPO}/issues/')}(\d+)/comments")
_ONE = re.compile(rf"{re.escape(f'/repos/{REPO}/issues/comments/')}(\d+)")
CODE_SPAN = re.compile(r"`[^`]*`")
ALLOWED_TAGS = re.compile(r"</?(?:details|summary)>")


# --------------------------------------------------------------------------- the fake service
class _LinkHandler(_Handler):
    """The shared handler, except the service may also return response headers (a ``Link`` header)."""

    def _dispatch(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = {"_unparseable": raw.decode("utf-8", "replace")}
        code, payload, headers = self.server.service.handle_full(method, self.path, body, self.headers.get("Authorization", ""))
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)


class CommentService(AppService):
    """``AppService`` (the hold App's token exchange and check runs) plus paginated, recorded pull-request comments."""

    def __init__(self):  # noqa: PLR0913 -- same shape as the base class, with a Link-aware handler
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _LinkHandler)
        self._server.service = self
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()
        self.reset()

    def reset(self, **kwargs):
        super().reset(**kwargs)
        self.pr_comments, self.comment_writes, self.comment_gets, self.comment_auth = {}, [], [], []
        self.page_cap, self.next_id, self.foreign_next = 100, 9000, None
        self.refuse_comment_writes = self.fail_comment_reads = False

    def add_comment(self, pr, body, user=None):
        """Seed a comment as a bystander (default: a human); returns its id."""
        self.next_id += 1
        self.pr_comments.setdefault(pr, []).append({"id": self.next_id, "body": body, "user": dict(user or HUMAN), "issue_url": self._issue_url(pr)})
        return self.next_id

    def _issue_url(self, pr):
        """The ``issue_url`` the hosting service puts on every comment it serves."""
        return f"{self.url}/repos/{REPO}/issues/{pr}"

    def own(self, pr=PR):
        """The comments the check itself authored on ``pr``: the bot's, whose first line is the marker."""
        return [c for c in self.pr_comments.get(pr, []) if c["user"] == BOT and c["body"].splitlines()[:1] == [MARKER]]

    def own_one(self, pr=PR):
        """The check's one comment on ``pr``; the absence of it is the failing assertion, never an IndexError."""
        found = self.own(pr)
        CHECK.assertEqual(1, len(found), f"expected the check's one comment on #{pr}; the service holds {self.pr_comments.get(pr)}")
        return found[0]

    def kinds(self):
        return [w["kind"] for w in self.comment_writes]

    def handle_full(self, method, raw_path, body, auth=""):
        parsed = urlparse(raw_path)
        listed, one = _LIST.fullmatch(parsed.path), _ONE.fullmatch(parsed.path)
        if not (listed or one):
            _LOCAL.auth = auth.removeprefix("Bearer ").removeprefix("token ").strip()  # the App plane authorises by bearer
            code, payload = self.handle(method, raw_path, body)
            return code, payload, {}
        self.requests.append((method, raw_path))
        self.comment_auth.append(auth)
        if method == "GET" and listed:
            return self._page(int(listed.group(1)), parse_qs(parsed.query), raw_path)
        record = {"kind": {"POST": "create", "PATCH": "edit", "DELETE": "delete"}.get(method, method), "path": parsed.path, "body": (body or {}).get("body")}
        if listed:
            record["pr"] = int(listed.group(1))
        if one:
            record["id"] = int(one.group(1))
        self.comment_writes.append(record)
        if self.refuse_comment_writes:
            return 403, {"message": "Resource not accessible by integration"}, {}
        if method == "POST" and listed:
            self.next_id += 1
            made = {"id": self.next_id, "body": record["body"], "user": dict(BOT), "issue_url": self._issue_url(record["pr"])}
            self.pr_comments.setdefault(record["pr"], []).append(made)
            return 201, made, {}
        found = [c for comments in self.pr_comments.values() for c in comments if one and c["id"] == record["id"]]
        if not found:
            return 404, {"message": "Not Found"}, {}
        if method == "PATCH":
            found[0]["body"] = record["body"]
            return 200, found[0], {}
        return 204, None, {}

    def _page(self, pr, query, raw_path):
        self.comment_gets.append({"pr": pr, "query": {k: v[-1] for k, v in query.items()}})
        if self.fail_comment_reads:
            return 500, {"message": "Server Error"}, {}
        comments = self.pr_comments.get(pr, [])
        asked = int(query.get("per_page", ["30"])[-1])
        size, page = max(1, min(asked, self.page_cap, 100)), int(query.get("page", ["1"])[-1])
        headers = {}
        if self.foreign_next and page == 1:
            headers["Link"] = f'<{self.foreign_next}>; rel="next"'
        elif page * size < len(comments):
            base = f"{self.url}/repos/{REPO}/issues/{pr}/comments?per_page={asked}"
            last = -(-len(comments) // size)
            headers["Link"] = f'<{base}&page={page + 1}>; rel="next", <{base}&page={last}>; rel="last"'
        return 200, comments[(page - 1) * size : page * size], headers


class ForeignListener:
    """A listener on another origin; ``hits`` records every request that reaches it with its credentials."""

    def __init__(self):
        outer = self
        self.hits = []

        class _Recorder(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return None

            def do_GET(self):  # noqa: N802 -- http.server naming
                outer.hits.append({"path": self.path, "auth": self.headers.get("Authorization", "")})
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"[]")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


# --------------------------------------------------------------------------- driving the real entry point
class Ran(NamedTuple):
    code: int
    out: str


def write_event(folder, payload):
    """Write an event file with the real serializer, as the runner does; returns its path."""
    path = Path(folder) / "event.json"
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as exc:
        message = f"cannot write the event file: {exc}"
        raise AssertionError(message) from exc
    return path


def pr_event(number=PR, **extra):
    """An ``opened`` payload shaped like the platform's, the number in both places the platform puts it."""
    return {"action": "opened", "number": number, "pull_request": {"number": number, "body": "A change.", "head": {"sha": "9" * 40}, "base": {"ref": "main"}}, **extra}


def run_main(svc, event_path):
    """The hold's real ``main`` with the environment the job gives it; ``event_path`` None leaves it unset."""
    hold = import_production(HOLD_MODULE)
    env = {"GITHUB_API_URL": svc.url, "GITHUB_TOKEN": "fake-token", "GITHUB_REPOSITORY": REPO}
    if event_path is not None:
        env["GITHUB_EVENT_PATH"] = str(event_path)
    out = io.StringIO()
    with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
        if event_path is None:
            os.environ.pop("GITHUB_EVENT_PATH", None)
        code = hold.main([])
    return Ran(code, out.getvalue())


class CommentTestCase(HoldTestCase):
    """The hold test case over a ``CommentService``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc.close()
        cls.svc = CommentService()

    def drive(self, number=PR):
        """One evaluation of pull request ``number`` through the real ``main`` and a real event file."""
        path = write_event(self.tmp, pr_event(number))
        return run_main(self.svc, path)

    def red_history(self, *, numbers=(6, 7), notice_failing=("tests/t.py::test_a",), **notice):
        """Serve a green run then red runs, the last red run described by a notice built by the real producer."""
        now = datetime.now(timezone.utc)
        runs = [make_run(n, "failure" if n > numbers[0] else "success", hours_ago=2 - n / 10, now=now) for n in numbers]
        self.serve(runs, {r["id"]: DNC_JOBS if notice.get("stage") else RED_JOBS for r in runs})
        self.svc.issues.clear()
        if notice_failing is not None:
            self.svc.add_issue(50, title="Post-merge suite is red", body=notice_description(runs[-1]["id"], failing=notice_failing, **notice), labels=["post-merge-red"])
        return runs

    def green_history(self, number=9):
        self.serve([make_run(number, "success", hours_ago=0.5, now=datetime.now(timezone.utc))])


def notice_description(run_id, *, failing=(), stage=None, red_since="2026-10-01T00:00:00+00:00", commits=(), anchor=None, omitted=0):
    """A notice description as the REAL notice producer writes it; ``stage`` set means a did-not-complete run."""
    suite, render = import_production("scripts.ci.post_merge_suite"), import_production("scripts.ci._notice_render")
    env = {"GITHUB_SHA": "7" * 40, "GITHUB_RUN_ID": str(run_id), "GITHUB_REPOSITORY": REPO, "GITHUB_SERVER_URL": "https://github.com", "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "push"}
    if stage:
        verdict = suite.build_verdict_file({"results": {}, "exitstatus": 5, "ran": 0, "expected": 0, "runner": "r"}, None, env)
        CHECK.assertEqual(stage, verdict["stage"], "the real producer no longer ends this way; pick another stage")
    else:
        verdict = make_verdict("red", run_id=run_id, head_sha="7" * 40, failing=failing)
    commit_range = render.CommitRange(render.RANGE_LISTED, anchor, [(sha, "a subject") for sha in commits], omitted) if anchor else render.CommitRange(render.RANGE_NO_GREEN)
    return render.render_description(render.build_state(verdict, commit_range, red_since), commit_range)


# --------------------------------------------------------------------------- reading a comment
def headline(body):
    """The first line after the marker that says something: the state's wording."""
    lines = [line.strip() for line in body.splitlines()[1:] if line.strip()]
    return lines[0] if lines else ""


def outside_code(body):
    """What a reader sees as prose: the marker, inline code spans and the collapsible's own tags removed."""
    return ALLOWED_TAGS.sub("", CODE_SPAN.sub("", body.replace(MARKER, "")))


def outside_details(body):
    """The body without any collapsed ``<details>`` block."""
    return re.sub(r"<details>.*?</details>", "", body, flags=re.DOTALL)


# --------------------------------------------------------------------------- the executed job, with a chosen payload
def run_job_with_event(svc, base, payload):
    """Execute the hold job verbatim with ``payload`` as the event file; returns (outcome, event path)."""
    base = Path(base)
    default = scratch_default_branch(base)
    observer, state_dir = base / "observer", base / "state"
    for folder in (observer, state_dir):
        folder.mkdir()
    (observer / "sitecustomize.py").write_text(OBSERVER, encoding="utf-8")
    event, log = write_event(base, payload), base / "observed.json"
    env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_EVENT_NAME": "pull_request_target", "PYTHONPATH": str(observer), "PYTHONDONTWRITEBYTECODE": "1", "HOLD_OBSERVER_LOG": str(log), "HOME": str(state_dir)}
    env.update({f"{SECRET_PREFIX}{name}": value for name, value in app_secrets().items()})  # the job mints the hold App's token
    run = HoldRun(secrets_as_env(WORKFLOW, base / "workflow-under-test.yml"), default, None, base / "scratch", env, svc.url)
    result = run.execute_job(JOB_NAME)
    events = [e for part in sorted(base.glob(f"{log.name}.*")) for e in json.loads(part.read_text(encoding="utf-8"))]
    return JobOutcome(result, run, events, None, state_dir), event
