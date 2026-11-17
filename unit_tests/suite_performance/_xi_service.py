"""A minimal recording fake of the hosting service for the client allowlist test of TQ-600a-13-xi. Not a test: underscore-named.

It ACCEPTS every write it is sent (a 201 or 200) and RECORDS it, so "the client refused it" can only mean the request was never sent.
It answers the two reads the allowlist is specified to make before a write: one issue (its labels) and one run (its workflow ``path``).
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ._notice_fakes import REPO

_ISSUE = re.compile(rf"/repos/{re.escape(REPO)}/issues/(\d+)")
_COMMENT = re.compile(rf"/repos/{re.escape(REPO)}/issues/comments/(\d+)")
_RUN = re.compile(rf"/repos/{re.escape(REPO)}/actions/runs/(\d+)")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return None

    def _dispatch(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        body = json.loads(raw) if raw else None
        code, payload = self.server.service.handle(method, self.path, body, self.headers.get("Authorization", ""))
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = lambda self: self._dispatch(self.command)  # noqa: E731 -- http.server verbs


class RecordingService:
    """Issues and runs are seeded by the test; ``drop_labels`` makes a created issue come back WITHOUT its label (the platform can)."""

    def __init__(self):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.service = self
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()
        self.requests, self.issues, self.runs, self.created = [], {}, {}, 0
        self.drop_labels = False
        self.pulls, self.run_meta, self.comments = set(), {}, {}  # issue numbers that are pull requests; per-run overrides; comment id -> issue_url/body/user

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def writes(self):
        """Every write the server saw, as ``(method, path)`` in arrival order."""
        return [(method, path) for method, path, _body in self.requests if method != "GET"]

    def handle(self, method, path, body, _auth):
        self.requests.append((method, path, body))
        issue, run = _ISSUE.fullmatch(path), _RUN.fullmatch(path)
        comment = _COMMENT.fullmatch(path)
        if method == "GET" and comment:
            found = self.comments.get(int(comment.group(1)))
            return (404, {"message": "Not Found"}) if found is None else (200, {"id": int(comment.group(1)), **found})
        if method == "GET" and issue:
            number = int(issue.group(1))
            labels = self.issues.get(number)
            if labels is None:
                return 404, {"message": "Not Found"}
            return 200, {"number": number, "labels": [{"name": n} for n in labels], **({"pull_request": {}} if number in self.pulls else {})}
        if method == "GET" and run:
            workflow = self.runs.get(int(run.group(1)))
            if workflow is None:
                return 404, {"message": "Not Found"}
            return 200, {"id": int(run.group(1)), "path": workflow, "event": "pull_request_target", "head_repository": {"full_name": REPO}, **self.run_meta.get(int(run.group(1)), {})}
        if method == "POST" and path == f"/repos/{REPO}/issues":
            self.created += 1
            labels = [] if self.drop_labels else (body or {}).get("labels", [])
            return 201, {"number": 500 + self.created, "labels": [{"name": n} for n in labels]}
        if method == "POST" and path == f"/repos/{REPO}/check-runs":
            self.created += 1
            return 201, {"id": 5000 + self.created, "name": (body or {}).get("name")}
        return (200, {"id": 1}) if method != "POST" else (201, {"id": 1})
