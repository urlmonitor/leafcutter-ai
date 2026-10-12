"""Regression tests (pr-reviewer findings H-1 and M-5) for BO-2400f-5-iii.

H-1: a healthy or ordinarily-failed reply that merely MENTIONS a refusal word
must not become a declined_step; each step keeps its pre-existing branch.
M-5: release wiring — post-claim declines release, pre-claim declines do not.

No subTest(): problems are accumulated and asserted once.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests.workflows._bo2400f5iii_fixtures import (  # noqa: E402
    BASE_RESPONSES,
    classify_in_node,
    decline_reply_for,
    run_lane,
)

_PLAIN = {"step": "x", "agent": "a", "isCommandStep": False}


def _with(label: str, **changes: Any) -> dict[str, Any]:
    return {**BASE_RESPONSES[label], **changes}


# (label, reply, expectation). "reaches_pr" means the run continued all the
# way to the PR dispatch; other keys are checked on the terminal payload.
_CASES: list[tuple[str, Any, dict[str, Any]]] = [
    ("test-writer-connected",
     _with("test-writer-connected",
           message="Wrote 3 stubs; declined to add a test for X (already covered)"),
     {"reaches_pr": True}),
    ("coder-connected",
     _with("coder-connected", message="Wired the dependency-injected clock into the gate"),
     {"reaches_pr": True}),
    ("fastlane-review",
     _with("fastlane-review", message="No findings; out of scope items were declined"),
     {"reaches_pr": True}),
    ("check-producibility",
     {"producible": False, "reason": "member BO-1 is declined/deferred status"},
     {"status": "refused", "message_has": "Refusing the resolved connected build set"}),
    ("resolve-connected",
     {"ac_ids": [], "message": "resolution error: manifest refused to parse"},
     {"status": "error", "failing_phase": "resolve",
      "message_has": "Resolver could not resolve"}),
    ("fastlane-commit",
     {"status": "error", "message": "pre-commit hook refused the commit"},
     {"status": "blocked", "failing_phase": "commit",
      "releases": ["release-on-commit-fail"]}),
    ("fastlane-pr",
     {"status": "error", "message": "push refused by remote hook"},
     {"status": "error", "failing_phase": "pull-request",
      "message_has": "open the PR manually",
      "has_keys": ["worktree_path", "branch", "ac_ids"]}),
    ("fastlane-worktree",
     {"outcome": None, "message": "Connection refused"},
     {"status": "refused", "failing_phase": "worktree"}),
]


class TestRefusalWordsInOrdinaryRepliesAreNotDeclines(unittest.TestCase):
    """H-1."""

    def test_classifier_does_not_flag_ordinary_replies_as_declined(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: discrimination
        problems: list[str] = []
        for label, reply, _ in _CASES:
            verdict = classify_in_node(json.dumps(reply), _PLAIN)
            if verdict.get("kind") == "declined":
                problems.append(f"[{label}] classified declined: {verdict}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_each_step_keeps_its_existing_branch_end_to_end(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: reachability
        problems: list[str] = []
        for label, reply, expect in _CASES:
            result = run_lane({label: reply})
            payload = result.result
            if payload is None:
                problems.append(f"[{label}] no terminal payload. stderr={result.stderr!r}")
                continue
            if payload.get("halt_kind") == "declined_step":
                problems.append(f"[{label}] wrongly halted as declined_step: {payload}")
                continue
            labels = [c.label for c in result.agent_calls]
            if expect.get("reaches_pr") and "fastlane-pr" not in labels:
                problems.append(f"[{label}] run did not continue to the PR step: {labels}")
            for key in ("status", "failing_phase"):
                if key in expect and payload.get(key) != expect[key]:
                    problems.append(f"[{label}] {key}={payload.get(key)!r}, want {expect[key]!r}")
            if "message_has" in expect and expect["message_has"] not in str(payload.get("message")):
                problems.append(f"[{label}] message lacks {expect['message_has']!r}: {payload}")
            for key in expect.get("has_keys", []):
                if not payload.get(key):
                    problems.append(f"[{label}] payload lacks {key}: {payload}")
            for rel in expect.get("releases", []):
                if rel not in labels:
                    problems.append(f"[{label}] expected dispatch {rel}, saw {labels}")
        self.assertEqual(problems, [], "\n".join(problems))


_POST_CLAIM = (
    "fastlane-context-bundle", "test-writer-connected", "coder-connected",
    "fastlane-review", "fastlane-changelog", "fastlane-commit",
)
_PRE_OR_AT_CLAIM = (
    "fastlane-worktree", "fastlane-worktree-verify", "resolve-connected",
    "check-producibility", "claim-connected", "fastlane-pr",
)


class TestReleaseWiringOnDecline(unittest.TestCase):
    """M-5 (coverage: may already pass against the current code)."""

    def test_post_claim_decline_dispatches_release_on_step_decline(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: reachability
        problems: list[str] = []
        for label in _POST_CLAIM:
            result = run_lane({label: decline_reply_for("some-agent")})
            labels = [c.label for c in result.agent_calls]
            want = f"release-on-{label}-decline"
            if want not in labels:
                problems.append(f"[{label}] missing {want}; saw {labels}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_pre_claim_and_pr_declines_dispatch_no_release(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: failure
        problems: list[str] = []
        for label in _PRE_OR_AT_CLAIM:
            result = run_lane({label: decline_reply_for("some-agent")})
            releases = [
                c.label for c in result.agent_calls if str(c.label).startswith("release-on")
            ]
            if result.result is None or result.result.get("halt_kind") != "declined_step":
                problems.append(f"[{label}] did not halt as declined_step: {result.result}")
            if releases:
                problems.append(f"[{label}] unexpected release dispatch(es): {releases}")
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
