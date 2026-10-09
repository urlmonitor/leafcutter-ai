"""
Tests for TQ-600a-13-vii, review findings -- the hardening round after the independent review: the write token must
never follow a redirect, hostile or oversized text must stay inert and bounded in the comment, a hostile response must not
crash past the verdict, and a comment is "ours" only when its id and ``issue_url`` are what the service would give.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-vii.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by python-coder after review; test first, shown red)
M-1 ``_github_rest.GitHubClient`` never lets the Authorization header reach a redirect target and treats any redirect as
    a failed call (``GitHubError``); the hold then writes nothing.
L-2 the exempt reason is rendered as ONE inline code span of at most 300 characters.
L-3 a hostile, deeply nested response body is a ``GitHubError`` (not a ``RecursionError``); the comment sync catches only
    ``GitHubError``, so a render bug is raised, not hidden.
L-4 on a lift, the previous body is folded only when it still has the shape the check renders (our marker, one of our held
    headlines, no ``</details>``, no ``@`` / ``<`` / ``](`` outside code); otherwise a one-line summary is folded.
L-5 a comment is the check's own only when its ``id`` is a positive int (not a bool) and its ``issue_url`` ends with
    ``/issues/{pr}``; the edit path is built from that id.
L-6 the whole body stays under 60,000 characters (GitHub's limit is 65,536), however large the previous body or the notice.
======================================================================
"""

from __future__ import annotations

import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest import mock

from ._comment_harness import BOT, MARKER, PR, CommentTestCase, ForeignListener, outside_code, outside_details, pr_event, run_main, write_event
from ._ending_harness import CHECK, Cases
from ._hold_harness import NOW
from ._notice_fakes import REPO, import_production

BODY_LIMIT = 60_000
HOSTILE_REASON = "[click here](http://evil.example/steal)\nhttp://evil.example/bare `tick` @someone <b>bold</b>\n# INJECTED HEADING " + "z" * 900


class Redirector:
    """A server that answers every request with a redirect to ``target`` (another origin), recording what it saw."""

    def __init__(self, target, code):
        outer, self.seen = self, []
        self.code = code

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return None

            def _go(self):
                outer.seen.append({"method": self.command, "path": self.path})
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                self.send_response(outer.code)
                self.send_header("Location", f"{target}{self.path}")
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_GET = do_POST = do_PATCH = _go  # noqa: N815 -- http.server naming

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def close(self):
        self._server.shutdown()
        self._server.server_close()


class TestTq600a13viiRedirects(CommentTestCase):
    def _foreign_and_redirector(self, code):
        foreign = ForeignListener()
        self.addCleanup(foreign.close)
        redirector = Redirector(foreign.url, code)
        self.addCleanup(redirector.close)
        return foreign, redirector

    def test_tq600a_13_vii_the_token_never_follows_a_redirect_to_another_origin(self):
        # covers: TQ-600a-13-vii
        # angle: failure
        """The API root answers with a 301/302/303/307/308 to a second server. The client raises ``GitHubError`` and the
        second server never receives an Authorization header (urllib would copy it across origins).

        Wrong versions caught: a client built on the default redirect handling with the token as an ordinary header.
        """
        rest = import_production("scripts.ci._github_rest")
        cases = Cases()
        for code in (301, 302, 303, 307, 308):
            with cases.case(f"HTTP {code}"):
                foreign, redirector = self._foreign_and_redirector(code)
                client = rest.GitHubClient(redirector.url, "secret-token")
                with CHECK.assertRaises(rest.GitHubError):
                    client.get("/repos/o/r/issues")
                CHECK.assertEqual([], [hit for hit in foreign.hits if hit["auth"]], "the token reached another origin")
        cases.check()

    def test_tq600a_13_vii_a_hold_whose_api_redirects_writes_no_comment_and_still_holds(self):
        # covers: TQ-600a-13-vii
        # angle: failure
        """Through the real entry point with the API root redirecting to another origin: the token goes nowhere else, the
        redirector sees no POST or PATCH, and the verdict still holds (exit 1).

        Wrong versions caught: following the redirect and trusting what the other origin served; a write attempted anyway.
        """
        foreign, redirector = self._foreign_and_redirector(302)
        ran = run_main(SimpleNamespace(url=redirector.url), write_event(self.tmp, pr_event(PR)))
        cases = Cases()
        with cases.case("held, nothing written, token kept"):
            CHECK.assertEqual(1, ran.code, ran.out)
            CHECK.assertEqual([], [s for s in redirector.seen if s["method"] != "GET"])
            CHECK.assertEqual([], [hit for hit in foreign.hits if hit["auth"]])
        cases.check()


class TestTq600a13viiHostileResponses(CommentTestCase):
    def test_tq600a_13_vii_a_hostile_deeply_nested_comment_list_does_not_crash_past_the_verdict(self):
        # covers: TQ-600a-13-vii
        # angle: failure
        """The comment list's body is nested far past the interpreter's limit. The check prints the verdict's reason, exits with
        the verdict's code (1 held, 0 pass) and writes no comment, instead of raising ``RecursionError``.

        Wrong versions caught: a ``RecursionError`` escaping the client's JSON decode and the comment sync.
        """
        rest = import_production("scripts.ci._github_rest")
        real = rest.GitHubClient._decode
        deep = b"[" * 400_000 + b"]" * 400_000

        def hostile(method, path, raw):
            return real(method, path, deep if method == "GET" and path.endswith("/comments") else raw)

        cases = Cases()
        with mock.patch.object(rest.GitHubClient, "_decode", staticmethod(hostile)):
            with cases.case("held"):
                self.red_history()
                ran = self.drive()
                CHECK.assertEqual((1, []), (ran.code, self.svc.comment_writes), ran.out)
                CHECK.assertIn("not green", ran.out)
            with cases.case("pass"):
                self.green_history()
                ran = self.drive()
                CHECK.assertEqual((0, []), (ran.code, self.svc.comment_writes), ran.out)
        cases.check()

    def test_tq600a_13_vii_a_render_bug_is_raised_not_hidden(self):
        # covers: TQ-600a-13-vii
        # angle: failure
        """Only ``GitHubError`` is caught at the comment boundary: a bug in rendering propagates out of the check (a raise exits
        non-zero, which still holds the pull request).

        Wrong versions caught: a wide ``except`` tuple turning a defect into a silently missing comment.
        """
        self.red_history()
        comment = import_production("scripts.ci._hold_comment")
        with mock.patch.object(comment, "render_comment", side_effect=KeyError("bug")):
            with CHECK.assertRaises(KeyError):
                self.drive()
        CHECK.assertEqual([], self.svc.comment_writes)


class TestTq600a13viiBodyHardening(CommentTestCase):
    def _lift(self, previous, reason=None):
        hold = import_production("scripts.ci.post_merge_hold")
        self.green_history(9)
        passed = self.evaluate(now=NOW)
        verdict = passed if reason is None else {**passed, "state": "exempt", "reason": reason}
        return hold.render_comment(verdict, NOW, previous)

    def _held(self, **notice):
        self.red_history(**notice)
        self.drive()
        return self.svc.own_one()["body"]

    def test_tq600a_13_vii_an_exempt_reason_is_one_bounded_code_span(self):
        # covers: TQ-600a-13-vii
        # angle: discrimination
        """A link-shaped, multi-line, backtick-bearing, mention-bearing, 900-character exempt reason renders as a single inline
        code span of at most 300 characters: no live link, mention, heading or HTML outside code.

        Wrong versions caught: escaping only ``<`` and ``@`` (markdown links, bare URLs, backticks, newlines survive).
        """
        body = self._lift(self._held(), HOSTILE_REASON)
        shown = outside_code(outside_details(body))
        spans = re.findall(r"`[^`]*`", outside_details(body))
        cases = Cases()
        with cases.case("nothing live outside code"):
            CHECK.assertEqual([], [t for t in ("evil.example", "@", "<", "](", "INJECTED", "click here") if t in shown])
            CHECK.assertFalse([line for line in body.splitlines() if line.startswith("#")])
        with cases.case("one bounded span carries it"):
            CHECK.assertTrue(any("click here" in s for s in spans))
            CHECK.assertLessEqual(max(len(s) for s in spans), 302)
        cases.check()

    def test_tq600a_13_vii_a_hand_edited_previous_body_is_not_folded_raw(self):
        # covers: TQ-600a-13-vii
        # angle: discrimination
        """The previous comment was edited by a human (allowed to edit a bot comment on some repositories) to hold a closing
        ``</details>``, a mention and a link. The lifted body folds a one-line summary instead: one ``</details>`` only, no
        mention and no link outside code. Control: an untouched previous body is still folded whole.

        Wrong versions caught: folding the previous body raw, so its markup breaks out of the collapsed block.
        """
        held = self._held(notice_failing=["tests/t.py::test_kept_in_the_fold"])
        edited = held.replace("Evaluated at", "</details>\n@someone [x](http://evil.example)\n\nEvaluated at")
        cases = Cases()
        with cases.case("edited"):
            body = self._lift(edited)
            CHECK.assertEqual(1, body.count("</details>"))
            CHECK.assertEqual([], [t for t in ("@someone", "evil.example", "](") if t in outside_code(body)])
            CHECK.assertEqual(MARKER, body.splitlines()[0])
        with cases.case("a mention appended outside code"):
            body = self._lift(held + "\nping @octocat\n")
            CHECK.assertNotIn("@octocat", body)
        with cases.case("control: untouched"):
            body = self._lift(held)
            CHECK.assertIn("test_kept_in_the_fold", body)
            CHECK.assertEqual(1, body.count("</details>"))
        cases.check()

    def test_tq600a_13_vii_the_body_stays_under_the_service_limit(self):
        # covers: TQ-600a-13-vii
        # angle: boundary
        """(1) An oversized, shaped previous body (200,000 characters) is cut on a line boundary so the lifted body stays under
        60,000 and still closes its ``<details>``. (2) A held body for a notice of 100 enormous node ids stays under 60,000.

        Wrong versions caught: a body past 65,536 characters, which the service refuses, so the comment is never lifted.
        """
        held = self._held()
        huge = held + "".join(f"- `{'x' * 1000}`\n" for _ in range(200))
        cases = Cases()
        with cases.case("lifted, oversized previous"):
            body = self._lift(huge)
            CHECK.assertLess(len(body), BODY_LIMIT)
            CHECK.assertEqual((1, 1), (body.count("<details>"), body.count("</details>")))
            CHECK.assertIn("lifted", outside_details(body).lower())
        with cases.case("held, enormous node ids"):
            self.svc.reset()
            self.red_history(notice_failing=[f"tests/t.py::test_{n}_" + "y" * 5000 for n in range(100)])
            self.drive()
            CHECK.assertLess(len(self.svc.own_one()["body"]), BODY_LIMIT)
        cases.check()


class TestTq600a13viiOwnCommentIdentity(CommentTestCase):
    def _seed(self, **overrides):
        comment = {"id": 4242, "body": f"{MARKER}\nsomething", "user": dict(BOT), "issue_url": f"{self.svc.url}/repos/{REPO}/issues/{PR}", **overrides}
        self.svc.pr_comments.setdefault(PR, []).append(comment)

    def test_tq600a_13_vii_a_comment_is_ours_only_with_a_sane_id_and_this_pull_requests_issue_url(self):
        # covers: TQ-600a-13-vii
        # angle: discrimination
        """A bot comment with the marker whose id is a bool or a string, whose ``issue_url`` names another pull request or is
        missing, is not the check's own: the check creates its own comment and PATCHes none of them. Control: the same
        comment with an int id and this pull request's ``issue_url`` is edited.

        Wrong versions caught: an id interpolated into the PATCH path unchecked; a comment from another thread edited.
        """
        other = f"{self.svc.url}/repos/{REPO}/issues/{PR + 1}"
        bad = {"bool id": {"id": True}, "string id": {"id": "4242/../../x"}, "other thread": {"issue_url": other}, "no issue_url": {"issue_url": None}, "suffix trick": {"issue_url": f"{other[:-2]}9{PR}"}}
        cases = Cases()
        for label, overrides in bad.items():
            with cases.case(label):
                self.svc.reset()
                self.red_history()
                self._seed(**overrides)
                self.drive()
                CHECK.assertEqual(["create"], self.svc.kinds())
        with cases.case("control: sane id and issue_url"):
            self.svc.reset()
            self.red_history()
            self._seed()
            self.drive()
            CHECK.assertEqual([("edit", 4242)], [(w["kind"], w.get("id")) for w in self.svc.comment_writes])
        cases.check()
