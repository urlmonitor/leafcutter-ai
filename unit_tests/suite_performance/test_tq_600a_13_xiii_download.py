"""
Tests for TQ-600a-13-xiii, review follow-ups for ``GitHubClient.get_bytes`` -- the size cap, the schemes a redirect may
reach, a relative ``Location``, the https-to-http downgrade, and a signed URL that never reaches a log or an error.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiii.yaml
"""

from __future__ import annotations

import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from ._comment_harness import ForeignListener
from ._ending_harness import Cases
from ._notice_fakes import captured_logs, import_production

PATH = "/repos/o/r/actions/artifacts/1/zip"
SIGNED = "/blob/SIGNED-SECRET-TOKEN-123"


class Scripted:
    """A server answering each path from ``routes`` (path -> (status, headers, body)); records path and Authorization."""

    def __init__(self, routes):
        outer, self.hits = self, []
        self.routes = routes

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return None

            def do_GET(self):  # noqa: N802 -- http.server naming
                outer.hits.append({"path": self.path, "auth": self.headers.get("Authorization", "")})
                status, headers, body = outer.routes.get(self.path, (404, {}, b""))
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def close(self):
        self._server.shutdown()
        self._server.server_close()


class TestTq600a13XiiiGetBytesHardening(unittest.TestCase):
    def _serve(self, factory, *args):
        server = factory(*args)
        self.addCleanup(server.close)
        return server

    def test_tq600a_13_xiii_the_body_cap_is_inclusive(self):
        # covers: TQ-600a-13-xiii
        # angle: boundary
        """A body of exactly ``max_bytes`` is returned; one byte more is an error, never a truncated answer.

        Wrong versions caught: ``>=`` for ``>``; a read that stops at the cap and returns the head of a larger body.
        """
        rest = import_production("scripts.ci._github_rest")
        client = rest.GitHubClient(self._serve(ForeignListener).url, "t")  # serves the two bytes b"[]"
        self.assertEqual(b"[]", client.get_bytes(PATH, max_bytes=2))
        with self.assertRaises(rest.GitHubError):
            client.get_bytes(PATH, max_bytes=1)

    def test_tq600a_13_xiii_a_redirect_may_only_reach_http_or_https_and_a_relative_one_is_resolved(self):
        # covers: TQ-600a-13-xiii
        # angle: failure
        """``file:`` and ``ftp:`` targets are refused with no request; a relative Location is followed on the same origin, token dropped.

        Wrong versions caught: a scheme that is not checked on the redirect hop; a relative Location that is requested as is.
        """
        rest = import_production("scripts.ci._github_rest")
        rows = Cases()
        for target in ("file:///etc/passwd", "ftp://127.0.0.1/blob"):
            with rows.case(target):
                api = self._serve(Scripted, {PATH: (302, {"Location": target}, b"")})
                with self.assertRaises(rest.GitHubError):
                    rest.GitHubClient(api.url, "secret-token").get_bytes(PATH)
                self.assertEqual([PATH], [hit["path"] for hit in api.hits])
        with rows.case("relative Location"):
            api = self._serve(Scripted, {PATH: (302, {"Location": "/blob/x"}, b""), "/blob/x": (200, {}, b"zipbytes")})
            self.assertEqual(b"zipbytes", rest.GitHubClient(api.url, "secret-token").get_bytes(PATH))
            self.assertEqual(["Bearer secret-token", ""], [hit["auth"] for hit in api.hits])
        rows.check()

    def test_tq600a_13_xiii_an_https_api_never_redirects_to_plain_http(self):
        # covers: TQ-600a-13-xiii
        # angle: failure
        """An https API root answering with an http redirect target is refused: the second hop is never requested.

        Wrong versions caught: any http(s) target accepted. (An http API root, as in the local servers, may still reach http.)
        """
        rest = import_production("scripts.ci._github_rest")
        client = rest.GitHubClient("https://api.example.invalid", "secret-token")
        with mock.patch.object(rest.GitHubClient, "_fetch", return_value=(None, "http://blob.example.invalid/x")) as fetch:
            with self.assertRaises(rest.GitHubError):
                client.get_bytes(PATH)
        self.assertEqual(1, fetch.call_count)

    def test_tq600a_13_xiii_the_signed_url_never_reaches_a_log_or_an_error(self):
        # covers: TQ-600a-13-xiii
        # angle: failure
        """The redirect target carries a secret in its path; a failing second hop and a good one both keep it out of logs and messages.

        Wrong versions caught: a log or an exception that quotes the redirect URL or the transport error that contains it.
        """
        rest = import_production("scripts.ci._github_rest")
        rows = Cases()
        for status in (500, 200):
            with rows.case(f"second hop answers {status}"):
                blob = self._serve(Scripted, {SIGNED: (status, {}, b"x")})
                api = self._serve(Scripted, {PATH: (302, {"Location": f"{blob.url}{SIGNED}"}, b"")})
                with captured_logs() as lines:
                    try:
                        rest.GitHubClient(api.url, "secret-token").get_bytes(PATH)
                        shown = ""
                    except rest.GitHubError as exc:
                        shown = f"{exc} {exc.__cause__} {exc.__context__}"
                self.assertEqual(status == 200, shown == "")
                self.assertNotIn("SIGNED-SECRET", shown + "\n".join(lines))
        with rows.case("the second hop cannot connect"):
            api = self._serve(Scripted, {PATH: (302, {"Location": f"http://127.0.0.1:1{SIGNED}"}, b"")})
            with captured_logs() as lines:
                with self.assertRaises(rest.GitHubError) as caught:
                    rest.GitHubClient(api.url, "secret-token").get_bytes(PATH)
            self.assertNotIn("SIGNED-SECRET", f"{caught.exception} {caught.exception.__cause__}" + "\n".join(lines))
        rows.check()
