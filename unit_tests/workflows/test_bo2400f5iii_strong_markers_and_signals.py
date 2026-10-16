"""Regression tests (re-review findings M-1, M-2, M-4 and the neutral message)
for BO-2400f-5-iii's `classifyStepReply` design:

- STRONG refusal markers (leading "Refusing/Declining this task", misrouted,
  not my role, outside my role/charter/scope, role mismatch) make a reply
  `declined` even when it carries a failure status or `outcome: null`.
- A SUCCESS signal (status ok, a true boolean gate field, producible true or
  false, non-empty ac_ids, pr_url / worktree_path, a string bundle, a non-null
  outcome) is ALWAYS a `result`, whatever its wording.
- The declined_step halt message never claims the step was "never attempted".

No subTest(): problems are accumulated and asserted once.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests.workflows._bo2400f5iii_fixtures import (  # noqa: E402
    AC_ID,
    BASE_RESPONSES,
    classify_in_node,
    decline_reply_for,
    run_lane,
)

_PLAIN = {"step": "x", "agent": "a", "isCommandStep": False}
_WEAK = "I declined to do the optional part of this"

# One case per success-signal family, each carrying ONLY that signal plus a
# first-person refusal sentence. Removing any one signal from the classifier
# must turn at least one of these into `declined`.
_SIGNAL_CASES = [
    "({status: 'ok', message: '%s'})",
    "({gate_passed: true, message: '%s'})",
    "({green: true, message: '%s'})",
    "({verdict_obtained: true, message: '%s'})",
    "({obtained: true, message: '%s'})",
    "({coverage_ok: true, message: '%s'})",
    "({created: true, message: '%s'})",
    "({entry_added: true, message: '%s'})",
    "({producible: true, reason: '%s'})",
    "({producible: false, reason: '%s'})",
    "({ac_ids: ['BO-X-1'], message: '%s'})",
    "({pr_url: 'https://example.com/pull/1', message: '%s'})",
    "({worktree_path: 'C:/w', message: '%s'})",
    "({bundle: 'ARCH ...', message: '%s'})",
    "({outcome: 'opened', message: '%s'})",
    "({outcome: 'refused', message: '%s'})",
]


def _with(label: str, **changes: Any) -> dict[str, Any]:
    return {**BASE_RESPONSES[label], **changes}


class TestStrongMarkerWithFailureStatusIsDeclined(unittest.TestCase):
    """M-1."""

    _CASES = [
        "({status: 'error', reason: 'Refusing this task. I am status-checker, scoped to ticket state'})",
        "({outcome: null, message: 'I am declining: this is outside my role'})",
        "({status: 'blocker', message: 'I am the pr-reviewer, not a test writer'})",
        "({status: 'error', message: 'wrong agent; I am status-checker, scoped to investigating ticket state'})",
        "({status: 'failed', message: 'This request is misrouted to me'})",
    ]

    def test_classifier_declines_strong_marker_despite_failure_status(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: discrimination
        problems = [
            f"{js}: expected declined, got {v}"
            for js in self._CASES
            if (v := classify_in_node(js, _PLAIN)).get("kind") != "declined"
        ]
        self.assertEqual(problems, [], "\n".join(problems))

    def test_end_to_end_strong_marker_halts_as_declined_step_naming_step_and_agent(
        self,
    ) -> None:
        # covers: BO-2400f-5-iii
        # angle: reachability
        cases = [
            ("fastlane-commit", "commit",
             {"status": "error", "reason": "Refusing this task. I am status-checker, scoped to ticket state"}),
            # BO-4300c-3: the former ("fastlane-worktree", "worktree-agent", ...) case is
            # gone -- the workspace step is the maker's answer handed in as
            # args.workspace, not a dispatch of the lane.
            ("test-writer-connected", "test-writer",
             {"status": "blocker", "message": "I am the pr-reviewer, not a test writer"}),
            ("resolve-connected", "status-checker",
             {"status": "error",
              "message": "wrong agent; I am status-checker, scoped to investigating ticket state"}),
        ]
        problems: list[str] = []
        for label, agent, reply in cases:
            payload = run_lane({label: reply}).result or {}
            if payload.get("halt_kind") != "declined_step":
                problems.append(f"[{label}] not a declined_step halt: {payload}")
                continue
            if payload.get("step") != label or payload.get("agent") != agent:
                problems.append(f"[{label}] wrong step/agent (want {agent}): {payload}")
        self.assertEqual(problems, [], "\n".join(problems))


class TestSuccessSignalIsAlwaysAResult(unittest.TestCase):
    """M-2."""

    def test_each_success_signal_with_refusal_wording_is_a_result(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: discrimination
        problems = []
        for template in _SIGNAL_CASES:
            js = template % _WEAK
            verdict = classify_in_node(js, _PLAIN)
            if verdict.get("kind") != "result":
                problems.append(f"{js}: expected result, got {verdict}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_end_to_end_signal_replies_keep_their_own_branch(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: reachability
        cases: list[tuple[str, Any, bool]] = [
            ("test-writer-connected", _with("test-writer-connected", gate_passed=True, message="I declined to add a test for X"), True),
            ("coder-connected", _with("coder-connected", green=True, message="I refused to touch unrelated files"), True),
            ("coder-connected", _with("coder-connected", message="I declined the optional refactor"), True),
            ("fastlane-review", _with("fastlane-review", verdict_obtained=True, message="I declined to file the low findings"), True),
            ("resolve-connected", {"ac_ids": [AC_ID], "message": "I declined to include Y"}, True),
            ("fastlane-pr", _with("fastlane-pr", message="I declined to add labels"), True),
            ("fastlane-context-bundle", _with("fastlane-context-bundle", message="I declined to include the stale layer"), True),
            ("check-producibility",
             {"producible": False, "reason": "I refuse to build a set with an unapproved member"}, False),
        ]
        problems: list[str] = []
        for label, reply, reaches_pr in cases:
            result = run_lane({label: reply})
            payload = result.result or {}
            labels = [c.label for c in result.agent_calls]
            if payload.get("halt_kind") == "declined_step":
                problems.append(f"[{label}] wrongly declined_step: {payload}")
            elif reaches_pr and "fastlane-pr" not in labels:
                problems.append(f"[{label}] did not continue to the PR step: {labels}")
            elif not reaches_pr and (
                payload.get("status") != "refused"
                or "Refusing the resolved connected build set" not in str(payload.get("message"))
            ):
                problems.append(f"[{label}] lost its BO-2400f-12 unproducible halt: {payload}")
        self.assertEqual(problems, [], "\n".join(problems))


class TestWeakWordingBlockerGoesToTheStepsOwnBranch(unittest.TestCase):
    """M-3."""

    def test_blocker_with_only_weak_wording_is_a_result(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: discrimination
        problems = []
        for js in (
            "({status: 'blocker', message: 'I cannot proceed: not authorized to ship without sign-off'})",
            "({status: 'blocker', message: 'I must refuse to continue: AC is untestable'})",
            "({status: 'blocker', message: 'I am unable to make tests green; I cannot help further without the fixture'})",
            "({status: 'error', message: 'I refuse to retry'})",
        ):
            verdict = classify_in_node(js, _PLAIN)
            if verdict.get("kind") != "result":
                problems.append(f"{js}: expected result, got {verdict}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_end_to_end_blocker_takes_the_existing_blocked_branch(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: reachability
        cases = [
            ("coder-connected", "python-coder", "python-coder phase did not return ok",
             "release-on-coder-fail",
             {"status": "blocker", "message": "I cannot proceed: not authorized to ship without sign-off"}),
            ("coder-connected", "python-coder", "python-coder phase did not return ok",
             "release-on-coder-fail",
             {"status": "blocker", "message": "I must refuse to continue: AC is untestable"}),
            ("test-writer-connected", "test-writer", "test-writer phase did not return ok",
             "release-on-test-writer-fail",
             {"status": "blocker",
              "message": "I am unable to make tests green; I cannot help further without the fixture"}),
        ]
        problems: list[str] = []
        for label, phase, wording, release, reply in cases:
            result = run_lane({label: reply})
            payload = result.result or {}
            labels = [c.label for c in result.agent_calls]
            if payload.get("halt_kind") == "declined_step":
                problems.append(f"[{label}] wrongly declined_step: {payload}")
                continue
            if payload.get("status") != "blocked" or payload.get("failing_phase") != phase:
                problems.append(f"[{label}] not the existing blocked branch: {payload}")
            if wording not in str(payload.get("message")):
                problems.append(f"[{label}] message lacks {wording!r}: {payload}")
            if release not in labels:
                problems.append(f"[{label}] expected {release}; saw {labels}")
        self.assertEqual(problems, [], "\n".join(problems))


class TestContextBundleWithoutObtainedIsNotADecline(unittest.TestCase):
    """M-4."""

    def test_bundle_without_obtained_and_weak_wording_is_not_obtained_not_declined(
        self,
    ) -> None:
        # covers: BO-2400f-5-iii
        # angle: boundary
        reply = {"bundle": "ARCH ... stale", "message": "I declined to include the stale layer"}
        verdict = classify_in_node(
            "({bundle: 'ARCH ... stale', message: 'I declined to include the stale layer'})",
            _PLAIN,
        )
        payload = run_lane({"fastlane-context-bundle": reply}).result or {}
        problems = []
        if verdict.get("kind") != "result":
            problems.append(f"classifier: expected result, got {verdict}")
        if payload.get("halt_kind") == "declined_step":
            problems.append(f"wrongly halted as declined_step: {payload}")
        if payload.get("failing_phase") != "context-bundle" or (
            payload.get("context_bundle_state") != "not_obtained"
        ):
            problems.append(f"not the existing not-obtained bundle halt: {payload}")
        self.assertEqual(problems, [], "\n".join(problems))


class TestDeclinedStepMessageIsNeutral(unittest.TestCase):
    """The halt message must not claim the step was 'never attempted'."""

    # BO-4300c-3: 'fastlane-worktree' / 'fastlane-worktree-verify' are no longer
    # steps of the lane (see _bo2400f5iii_fixtures.WORKSPACE_ANSWER).
    _LABELS = (
        "resolve-connected",
        "check-producibility", "claim-connected", "fastlane-context-bundle",
        "test-writer-connected", "coder-connected", "fastlane-review",
        "fastlane-changelog", "fastlane-commit", "fastlane-pr",
    )

    def test_no_declined_step_message_says_never_attempted(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: criterion
        problems: list[str] = []
        for label in self._LABELS:
            payload = run_lane({label: decline_reply_for("some-agent")}).result or {}
            if payload.get("halt_kind") != "declined_step":
                problems.append(f"[{label}] not a declined_step halt: {payload}")
                continue
            message = str(payload.get("message"))
            # BO-2400f-7-iii: a declined claim claims nothing, so the claim step alone states "never attempted".
            if label == "claim-connected":
                if "never attempted" not in message.lower():
                    problems.append(f"[{label}] message must state the claim was never attempted: {message}")
            elif "never attempted" in message.lower():
                problems.append(f"[{label}] message claims 'never attempted': {message}")
            if "declined" not in message.lower():
                problems.append(f"[{label}] message does not say the agent declined: {message}")
        self.assertEqual(problems, [], "\n".join(problems))


class TestToolErrorsWithScopeWordingAreNotDeclines(unittest.TestCase):
    """Final review: 'outside the scope' / 'wrong agent' in a real tool error
    carrying a failure status must not be read as a strong refusal marker."""

    _TOOL_ERRORS = [
        "pre-commit: file is outside the scope of staged paths",
        "check-scope: change is outside of the scope declared by ticket",
        "HTTP 403: token outside the scope required (repo)",
        "gh: wrong agent token? outside the scope of token permissions",
    ]

    def test_tool_errors_with_scope_wording_classify_as_result(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: discrimination
        problems = []
        for text in self._TOOL_ERRORS:
            js = "({status: 'error', message: %r})" % text
            verdict = classify_in_node(js, _PLAIN)
            if verdict.get("kind") != "result":
                problems.append(f"{js}: expected result, got {verdict}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_first_person_role_forms_are_still_declined(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: criterion
        problems = []
        for text in (
            "this is outside my role",
            "I am the pr-reviewer, not a test writer",
        ):
            js = "({status: 'error', message: %r})" % text
            verdict = classify_in_node(js, _PLAIN)
            if verdict.get("kind") != "declined":
                problems.append(f"{js}: expected declined, got {verdict}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_end_to_end_tool_errors_keep_the_commit_and_pr_branches(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: reachability
        problems: list[str] = []

        commit = run_lane({
            "fastlane-commit": {
                "status": "error",
                "message": "pre-commit: file is outside the scope of staged paths",
            }
        })
        payload = commit.result or {}
        labels = [c.label for c in commit.agent_calls]
        if payload.get("halt_kind") == "declined_step":
            problems.append(f"[commit] wrongly declined_step: {payload}")
        elif payload.get("status") != "blocked" or payload.get("failing_phase") != "commit":
            problems.append(f"[commit] not the existing commit-failed branch: {payload}")
        if "release-on-commit-fail" not in labels:
            problems.append(f"[commit] expected release-on-commit-fail; saw {labels}")

        pr = run_lane({
            "fastlane-pr": {
                "status": "error",
                "message": "HTTP 403: token outside the scope required (repo)",
            }
        })
        payload = pr.result or {}
        if payload.get("halt_kind") == "declined_step":
            problems.append(f"[pr] wrongly declined_step: {payload}")
        else:
            if payload.get("status") != "error" or payload.get("failing_phase") != "pull-request":
                problems.append(f"[pr] not the existing PR-failed branch: {payload}")
            if "open the PR manually" not in str(payload.get("message")):
                problems.append(f"[pr] message lacks 'open the PR manually': {payload}")
            for key in ("worktree_path", "branch", "ac_ids"):
                if not payload.get(key):
                    problems.append(f"[pr] payload lacks {key}: {payload}")
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
