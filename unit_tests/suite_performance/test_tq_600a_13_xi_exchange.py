"""
Tests for TQ-600a-13-xi (credential-exchange half) -- the App JWT client may exchange only for the ONE permission its caller pinned
(``WritePolicy.exchange_permission``: "checks" for the hold's minter, "actions" for the re-evaluation's), on exactly the bound repository,
with exact values, exact case and exact types.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xi.yaml (it_requirements 1; security
review 2026-10-12, M-1 and L-3).
"""

from __future__ import annotations

import unittest

from ._ending_harness import CHECK, Cases
from ._xi_service import RecordingService
from .test_tq_600a_13_xi_client import EXCHANGE_ACTIONS, EXCHANGE_CHECKS, NAME, make_client, rest

PATH = "/app/installations/777/access_tokens"


def _ask(permissions, repositories=(NAME,)):
    return {"permissions": permissions, "repositories": list(repositories)}


def accepted():
    """``(client, label, body)`` the pinned minters may send."""
    return [("checks", "the hold's minter: checks write, this repository", EXCHANGE_CHECKS), ("actions", "the re-run minter: actions write, this repository", EXCHANGE_ACTIONS)]


def refused():
    """``(client, label, body)`` that no pinned minter may send. A client is named by the permission it pinned (None: pinned nothing)."""
    return [
        # M-1: the permission is pinned PER CALLER, not shared by the two callers
        ("actions", "the re-run minter asking for checks: write", EXCHANGE_CHECKS),
        ("checks", "the hold's minter asking for actions: write", EXCHANGE_ACTIONS),
        (None, "a minter with nothing pinned asking for checks: write", EXCHANGE_CHECKS),
        (None, "a minter with nothing pinned asking for actions: write", EXCHANGE_ACTIONS),
        ("actions", "the re-run minter asking for both", _ask({"checks": "write", "actions": "write"})),
        # L-3: exact value, exact case, exact type
        ("actions", "actions: Write", _ask({"actions": "Write"})),
        ("actions", "ACTIONS: write", _ask({"ACTIONS": "write"})),
        ("checks", "Checks: write", _ask({"Checks": "write"})),
        ("actions", "actions: WRITE", _ask({"actions": "WRITE"})),
        ("actions", "actions: True", _ask({"actions": True})),
        ("actions", "actions: 1", _ask({"actions": 1})),
        ("checks", "checks: True", _ask({"checks": True})),
        ("actions", "a differently-cased repository name", _ask({"actions": "write"}, [NAME.upper()])),
        ("actions", "a repositories entry that is a bool", _ask({"actions": "write"}, [True])),
        ("actions", "a repositories entry that is the full name", _ask({"actions": "write"}, [f"owner/{NAME}"])),
    ]


class TestTq600a13XiExchangeIsPinnedPerCaller(unittest.TestCase):
    def setUp(self):
        self.svc = RecordingService()
        self.addCleanup(self.svc.close)

    def _client(self, pinned):
        return make_client(self.svc.url, "app_jwt", **({"exchange_permission": pinned} if pinned else {}))

    def test_tq600a_13_xi_the_exchange_is_limited_to_the_permission_the_caller_pinned(self):
        # covers: TQ-600a-13-xi
        # angle: discrimination
        """Each pinned minter exchanges for its own permission; every other permission, case, value type and repository spelling is
        refused and never sent. Wrong versions caught: one shared permission tuple (the re-run minter obtaining a checks-write token and
        vice versa); an unpinned minter that exchanges; a case-insensitive or truthy comparison; a repository compared loosely."""
        cases = Cases()
        for pinned, label, body in accepted():
            with cases.case(f"allowed: {label}"):
                self._client(pinned).post(PATH, body)
        sent = self.svc.writes()
        with cases.case("both allowed exchanges reached the server"):
            CHECK.assertEqual(2, len(sent), sent)
        for pinned, label, body in refused():
            before = self.svc.writes()
            with cases.case(f"refused: {label}"):
                with self.assertRaises(rest().GitHubError) as caught:
                    self._client(pinned).post(PATH, body)
                CHECK.assertEqual("refused", caught.exception.kind)
            with cases.case(f"refused, and never sent: {label}"):
                CHECK.assertEqual(before, self.svc.writes())
        cases.check()


if __name__ == "__main__":
    unittest.main()
