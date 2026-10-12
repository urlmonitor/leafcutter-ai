"""Test infrastructure for TQ-600a-13-ix (a hold that could not read fails and says so). Not a test: underscore-named.

* ``FaultService`` -- the exemption harness's recording fake, plus per-request FAULTS produced at the HTTP layer: any
  status with chosen headers (``http``), a raw body (``raw``: not JSON, a list, an object of the wrong shape), or a socket
  that accepts and never answers (``HANG``). A fault may be one-shot (``times=1``), so a retry can succeed. Every faulted
  request is recorded in ``requests`` like any other, so a test counts what the check asked for.
* ``closed_port_url`` / ``silent_listener`` -- a connection that is refused, and a listener that accepts and never answers.
* ``evaluate`` -- the hold's verdict entry point through the REAL REST client with an injected clock, a fraction-of-a-second
  timeout and (when ``evaluate`` accepts it) a recording ``sleep``. ``run_main`` -- the REAL ``main`` with a real event file.

INTERFACE ASSUMED OF THE IMPLEMENTATION (the coder's contract; see the report):
  ``evaluate(client, repo, *, now=None, claim=None, sleep=time.sleep)`` and ``evaluate_pull_request(..., sleep=...)``: ``sleep``
  is the injectable retry delay. ``main`` reads ``POST_MERGE_HOLD_TIMEOUT_SECONDS`` and ``POST_MERGE_HOLD_RETRY_DELAY_SECONDS``.
"""

from __future__ import annotations

import contextlib
import inspect
import io
import os
import socket
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from typing import NamedTuple
from unittest import mock
from urllib.parse import urlparse

from ._comment_harness import PR, Ran, _LinkHandler, write_event
from ._ending_harness import CHECK
from ._exempt_harness import NOTICE, ExemptCase, ExemptService
from ._hold_harness import HOLD_MODULE, NOW, SUITE_STATE_PATH, make_run
from ._notice_fakes import REPO, import_production

TIMEOUT = 0.05  # the client's timeout in every test of this record: a real timeout costs a fraction of a second
HANG_SECONDS = 1.0  # how long the fake holds a connection it will never answer
TIMEOUT_ENV, DELAY_ENV = "POST_MERGE_HOLD_TIMEOUT_SECONDS", "POST_MERGE_HOLD_RETRY_DELAY_SECONDS"
FAST_ENV = {TIMEOUT_ENV: str(TIMEOUT), DELAY_ENV: "0"}
WORKFLOW_PATH, RUNS_PATH = SUITE_STATE_PATH, f"{SUITE_STATE_PATH}/runs"
NOTICES_PATH = f"/repos/{REPO}/issues"
PR_COMMENTS_PATH, NOTICE_COMMENTS_PATH = f"/repos/{REPO}/issues/{PR}/comments", f"/repos/{REPO}/issues/{NOTICE}/comments"
HEADLINE = r"(?i)run history could not be read"  # the could_not_read headline: shared with no other state
CAUSE = {  # the cause each fault must name (the wording is the coder's; the fact named is not)
    401: r"401", 403: r"403", 404: r"404", 429: r"429", 500: r"500", 503: r"503",
    "timeout": r"(?i)time[sd]? ?out", "connection": r"(?i)connect|refused", "not_json": r"(?i)not JSON",
    "list": r"(?i)unexpected shape|expected shape|not an? (JSON )?object",
}


def jobs_path(run_id):
    return f"/repos/{REPO}/actions/runs/{run_id}/jobs"


class Fault(NamedTuple):
    """One scripted answer: ``hang`` accepts the request and never answers; otherwise ``status``, ``body`` and ``headers``."""

    status: int = 200
    body: bytes = b""
    headers: dict | None = None
    hang: bool = False


def http(status, headers=None):
    """A refusal with ``status`` (a JSON error body, as the hosting service sends)."""
    return Fault(status, b'{"message": "refused"}', headers)


def raw(body, status=200):
    """A ``status`` answer whose body is exactly ``body`` (bytes), whatever it is."""
    return Fault(status, body)


HANG = Fault(hang=True)
NOT_JSON, JSON_LIST, NO_STATE, NO_RUNS_LIST = raw(b"<html>Bad gateway</html>"), raw(b"[]"), raw(b'{"id": 1}'), raw(b'{"total_count": 0}')


class _FaultHandler(_LinkHandler):
    """The shared Link-aware handler, except a request with a scripted fault gets the fault instead of the fake's answer."""

    def _dispatch(self, method):
        service = self.server.service
        fault = service.take_fault(method, self.path)
        if fault is None:
            super()._dispatch(method)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        if fault.hang:
            service.release.wait(HANG_SECONDS)
            self.close_connection = True
            return
        self.send_response(fault.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(fault.body)))
        for name, value in (fault.headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(fault.body)


class FaultService(ExemptService):
    """``ExemptService`` (issues, runs, jobs, comments, proof runs) plus scripted faults."""

    def __init__(self):  # noqa: PLR0913 -- same shape as CommentService.__init__, with a fault-aware handler
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _FaultHandler)
        self._server.daemon_threads = True  # a hung connection must not keep ``close`` waiting
        self._server.service = self
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()
        self.reset()

    def reset(self, **kwargs):
        previous = getattr(self, "release", None)
        if previous is not None:
            previous.set()  # let any handler still holding a connection go
        super().reset(**kwargs)
        self.faults, self.release = [], threading.Event()

    def close(self):
        self.release.set()
        super().close()

    def fail(self, method, path, fault, times=None):
        """Answer every ``method`` request to exactly ``path`` with ``fault`` (the first ``times`` of them, when given)."""
        self.faults.append({"method": method, "path": path, "fault": fault, "left": times})

    def take_fault(self, method, raw_path):
        path = urlparse(raw_path).path
        for entry in self.faults:
            if entry["method"] == method and entry["path"] == path and entry["left"] != 0:
                if entry["left"] is not None:
                    entry["left"] -= 1
                self.requests.append((method, raw_path))
                return entry["fault"]
        return None

    def hits(self, path, method="GET"):
        """How many ``method`` requests reached exactly ``path`` (faulted or not)."""
        return sum(1 for m, raw_path in self.requests if m == method and urlparse(raw_path).path == path)


# --------------------------------------------------------------------------- connections that never reach a server
def closed_port_url():
    """A local URL on which nothing listens (the port was bound, then released)."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{probe.getsockname()[1]}"


@contextlib.contextmanager
def silent_listener():
    """A local URL whose socket accepts connections (the kernel backlog) and never answers a byte."""
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(8)
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        sock.close()


# --------------------------------------------------------------------------- driving the real entry points
class Sleeps(list):
    """The injected retry delay: records every requested pause and returns at once."""

    def __call__(self, seconds):
        self.append(seconds)


def evaluate(url, *, claim=None, sleeps=None, timeout=TIMEOUT):
    """``post_merge_hold.evaluate`` through the real REST client (``timeout`` seconds) with the injected clock.

    ``sleeps`` is passed as ``sleep=`` when ``evaluate`` accepts it (otherwise the call is made without it, so a missing
    retry fails on its own assertion, never on a TypeError).
    """
    hold = import_production(HOLD_MODULE)
    rest = import_production("scripts.ci._github_rest")
    client = rest.GitHubClient(url, "fake-token", timeout=timeout, policy=rest.WritePolicy(repo=REPO, notice_comments=True))  # the hold's grant (the exemption record); no PR comment here
    kwargs = {"now": NOW}
    if claim is not None:
        kwargs["claim"] = claim
    if sleeps is not None and "sleep" in inspect.signature(hold.evaluate).parameters:
        kwargs["sleep"] = sleeps
    return hold.evaluate(client, REPO, **kwargs)


def run_main(url, event_path, env_extra=None):
    """The hold's REAL ``main`` with the environment the job gives it, plus ``env_extra``; output captured."""
    hold = import_production(HOLD_MODULE)
    env = {"GITHUB_API_URL": url, "GITHUB_TOKEN": "fake-token", "GITHUB_REPOSITORY": REPO, "GITHUB_EVENT_PATH": str(event_path), **(env_extra or {})}
    out = io.StringIO()
    with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
        code = hold.main([])
    return Ran(code, out.getvalue())


def green_run(number=9):
    """A fresh, settled, green run on main: half an hour old by the REAL clock, which the job's own ``main`` reads (as ``green_history`` does)."""
    return make_run(number, "success", hours_ago=0.5, now=datetime.now(timezone.utc))


class FaultCase(ExemptCase):
    """The exemption test case over a ``FaultService``; ``ask`` drives the real ``main`` against it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc.close()
        cls.svc = FaultService()

    def green(self):
        """Serve a fresh green run on an active workflow."""
        self.serve([green_run()])

    def ask(self, url=None, *, body="A change.", env=None):
        """One evaluation of pull request ``PR`` through the real ``main`` (``body`` is the description)."""
        path = write_event(self.tmp, self.event(body))
        return run_main(url or self.svc.url, path, FAST_ENV if env is None else env)

    def expect_could_not_read(self, verdict, cause, label=""):
        """The verdict is the could-not-read one: its own headline, the cause named, and never a pass."""
        CHECK.assertEqual("could_not_read", verdict["state"], f"{label} {verdict}")
        CHECK.assertRegex(verdict["reason"], HEADLINE, label)
        CHECK.assertIsInstance(verdict["cause"], str, label)
        CHECK.assertRegex(f"{verdict['cause']} {verdict['reason']}", cause, label)
