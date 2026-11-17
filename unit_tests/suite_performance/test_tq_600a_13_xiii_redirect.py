"""
Tests for TQ-600a-13-xiii (download half) -- the artifact zip endpoint answers with a 302 to a signed blob URL on another
origin; ``GitHubClient.get_bytes`` follows exactly that one redirect, without the token.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiii.yaml
The JSON requests keep refusing every redirect (test_tq_600a_13_vii_review.py); only ``get_bytes`` has the one hop.
"""

from __future__ import annotations

import unittest

from ._comment_harness import ForeignListener
from ._ending_harness import Cases
from ._notice_fakes import import_production
from .test_tq_600a_13_vii_review import Redirector


class TestTq600a13XiiiTheDownloadHopDropsTheToken(unittest.TestCase):
    def _server(self, factory, *args):
        server = factory(*args)
        self.addCleanup(server.close)
        return server

    def test_tq600a_13_xiii_the_token_is_not_sent_to_the_redirect_target(self):
        # covers: TQ-600a-13-xiii
        # angle: failure
        """API root -> 302 -> another origin: the bytes arrive, the API saw the request, the target saw NO Authorization.

        Wrong versions caught: a client that copies the Authorization header to the redirect target; one that refuses
        the redirect (the real service always redirects); one that follows a second redirect.
        """
        rest = import_production("scripts.ci._github_rest")
        rows = Cases()
        for code in (301, 302, 303, 307, 308):
            with rows.case(f"HTTP {code}: one hop, bytes returned, token dropped"):
                foreign = self._server(ForeignListener)
                api = self._server(Redirector, foreign.url, code)
                data = rest.GitHubClient(api.url, "secret-token").get_bytes("/repos/o/r/actions/artifacts/1/zip")
                self.assertEqual(b"[]", data)
                self.assertEqual(["/repos/o/r/actions/artifacts/1/zip"], [seen["path"] for seen in api.seen])
                self.assertEqual([{"path": "/repos/o/r/actions/artifacts/1/zip", "auth": ""}], foreign.hits)
        with rows.case("a second redirect is refused and never requested"):
            foreign = self._server(ForeignListener)
            second = self._server(Redirector, foreign.url, 302)
            first = self._server(Redirector, second.url, 302)
            with self.assertRaises(rest.GitHubError):
                rest.GitHubClient(first.url, "secret-token").get_bytes("/repos/o/r/actions/artifacts/1/zip")
            self.assertEqual([], foreign.hits, "the second redirect was followed")
        rows.check()
