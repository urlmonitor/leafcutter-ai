"""
MODULE: unit_tests/workflows/test_tq_600a_13_xx_finalize_hold.py
GOAL: Prove TQ-600a-13-xx -- finalize-feature.js reads a pull request's checks at
    Step 4, reports a PR held only by `Post-merge suite status` as held
    EXTERNALLY (no merge, no success), reports a hold beside a real failure as
    the branch's own failure naming only the real one, and leaves the all-green
    path untouched apart from the single added read.

Behavioural only: the REAL finalize-feature.js runs under the Node-backed E2
harness with recorded label_responses; assertions are on the returned payload
and the ordered agent dispatches the executed script issued. The script's
source text is never read.

CONTRACT the coder must satisfy (the tests key off these constants):
  - CHECKS_LABEL: ONE status-checker dispatch, once per run, after
    `step-4-pr-state` reports OPEN and BEFORE `step-4-merge-gate`. Its reply is
    the `gh pr checks --json name,state,bucket,link,description` JSON array.
  - Held-only halt: status "halted", halted_at_step 4, reason HOLD_REASON,
    external_hold {name,state,link,description}, message quotes description+link.
  - Hold beside others: status "halted", reason OWN_REASON, own_failures (the
    non-hold failing checks), external_hold kept separate.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import (  # noqa: E402
    finalize_baseline_responses, run_workflow_under_e2, shell_step_reply, workspace_ensure_reply,
)

_ROOT = _UNIT_TESTS_DIR.parent
_JS = _ROOT / "templates" / "workflows-js" / "finalize-feature.js"
_SCENARIOS = (
    _ROOT / "docs" / "acceptance-criteria" / "testing-quality"
    / "TQ-600-suite-feedback-latency" / "TQ-600a-13-xviii-scenarios"
)

CHECKS_LABEL = "step-4-pr-checks"
HOLD_NAME = "Post-merge suite status"
HOLD_REASON = "held_externally"
OWN_REASON = "required_checks_failing"
NOTICE_REF = "#9001"

_MERGE_GATE = "step-4-merge-gate"
_MERGE = "step-4-merge-pr"
_CLEANUP = "cleanup-baseline-worktree"
_AFTER_HOLD_FORBIDDEN_LABELS = (
    _MERGE_GATE, _MERGE, "step-5-sync-main", "step-6-scope-detect",
    "step-7-worktree-probe", "step-7-remove-worktree",
)
_FORBIDDEN_PROMPT_FRAGMENTS = (
    "git push", "git commit", "--allow-empty", "gh run rerun", "--watch",
    "gh pr edit", "post-merge-", "scripts/ci/", "post_merge_tunables",
    "ruleset", "Fixes #",
)
# The dispatches finalize issued BEFORE this change, on an all-green run (BO-4300: the workspace maker's
# answer replaces the pre-flight probe; the baseline is a scratch workspace, a deploy, one pytest run, its removal).
_PRE_CHANGE_LABELS = [
    "resolve-maker-path",  # BO-4300a-1-ia: the one maker-path probe before the first maker request (consumer_drift)
    "workspace-ensure", "gh-config", "step-0-baseline-workspace", "step-0-baseline-deploy",
    "step-0-baseline", _CLEANUP, "step-1-pr-probe",
    "step-2-merge-main", "step-3-test-run", "step-3.5-closure-probe",
    "pre-step-4-sync-check", "step-4-pr-state", _MERGE_GATE, _MERGE,
    "step-5-sync-main", "step-6-scope-detect", "step-7-worktree-probe",
    "step-7-pr-merged-probe", "step-7-unpublished-learnings",
    "step-7-remove-worktree",
]
_PRE_CHANGE_STEP4_OUTCOME = "PR #7 merged to main"


def _scenario(name: str) -> list[dict[str, Any]]:
    """Recorded `gh pr checks --json` reply, verbatim from the on-disk fixture."""
    return json.loads((_SCENARIOS / name).read_text(encoding="utf-8"))


def _with_notice(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = copy.deepcopy(checks)
    for c in out:
        if c["name"] == HOLD_NAME:
            c["description"] += f" Notice: {NOTICE_REF}"
    return out


def _all_green(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = copy.deepcopy(checks)
    for c in out:
        c["state"] = "SUCCESS"
        c["description"] = ""
    return out


def _responses(checks_reply: Any) -> dict[str, Any]:
    return {
        "workspace-ensure": workspace_ensure_reply("/tmp/tq600a13xx-wt", branch="feature/hold"),
        "gh-config": {"gh_target_account": None, "gh_repo": None},
        **finalize_baseline_responses(),
        "step-0-baseline-deploy": shell_step_reply("", exit_status=0),
        "step-1-pr-probe": {"found": True, "number": 7, "url": "https://example.invalid/pull/7"},
        "step-2-merge-main": {"status": "merged", "merge_strategy": "merged_main"},
        "step-3-test-run": {"passed": True, "output": "ok", "failing_tests": []},
        "step-3.5-closure-probe": {"already_committed": True},
        "pre-step-4-sync-check": {"status": "up_to_date", "local_sha": "def5678", "origin_sha": "def5678"},
        "step-4-pr-state": {"state": "OPEN"},
        CHECKS_LABEL: checks_reply,
        _MERGE_GATE: {"status": "ok"},
        _MERGE: {"merged": True, "sha": "fee1dead"},
        "step-5-sync-main": {"head_sha": "def5678", "head_message": "Merge PR #7"},
        "step-6-scope-detect": {"scope": "single-ticket", "tickets_in_scope": [],
                                "tickets_done": [], "tickets_not_done": [], "skipped": False},
        "step-7-worktree-probe": {"exists": True},
        "step-7-pr-merged-probe": {"state": "MERGED"},
        "step-7-remove-worktree": {"removed": True, "conflict_pids": []},
    }


class _FinalizeHoldCase(unittest.TestCase):
    def run_with(self, checks_reply: Any) -> Any:
        result = run_workflow_under_e2(_JS, timeout=30, label_responses=_responses(checks_reply))
        self.assertEqual(result.error, "", result.error)
        self.assertIsInstance(result.result, dict, result.stderr[-2000:])
        return result

    @staticmethod
    def labels(result: Any) -> list[str]:
        return [c.label for c in result.agent_calls]

    @staticmethod
    def names(entries: Any) -> list[str]:
        return [e["name"] if isinstance(e, dict) else str(e) for e in (entries or [])]

    def after_read(self, result: Any) -> list[Any]:
        reads = [c for c in result.agent_calls if c.label == CHECKS_LABEL]
        self.assertEqual(len(reads), 1, f"checks read must happen once: {self.labels(result)}")
        return [c for c in result.agent_calls if c.call_index > reads[0].call_index]

    def assert_no_merge_path(self, result: Any) -> None:
        self.assertEqual(
            [lb for lb in self.labels(result) if lb in _AFTER_HOLD_FORBIDDEN_LABELS], [],
            self.labels(result),
        )


class TestHoldOnlyAndHoldBesideRealFailure(_FinalizeHoldCase):
    def test_tq600a_13_xx_hold_only_ends_held_externally_without_merging(self) -> None:
        # covers: TQ-600a-13-xx
        # angle: criterion
        checks = _with_notice(_scenario("scenario-A-hold-only.json"))
        hold = next(c for c in checks if c["name"] == HOLD_NAME)
        result = self.run_with(checks)
        payload = result.result
        self.assertEqual(payload.get("status"), "halted", payload)
        self.assertEqual(payload.get("halted_at_step"), 4, payload)
        self.assertEqual(payload.get("reason"), HOLD_REASON, payload)
        self.assertNotIn(payload.get("reason"), ("test_regression", OWN_REASON))
        self.assertEqual(self.names([payload.get("external_hold")]), [HOLD_NAME], payload)
        message = str(payload.get("message", ""))
        self.assertIn(hold["description"], message)
        self.assertIn(hold["link"], message)
        self.assertIn(NOTICE_REF, message)
        self.assert_no_merge_path(result)
        self.assertNotIn("merged to main", json.dumps(payload.get("step_summary", "")))
        self.assertIsNot(payload.get("worktree_removed"), True, payload)

    def test_tq600a_13_xx_hold_beside_a_real_failure_blames_only_the_real_failure(self) -> None:
        # covers: TQ-600a-13-xx
        # angle: discrimination
        result = self.run_with(_with_notice(_scenario("scenario-B-hold-plus-pytest-failure.json")))
        payload = result.result
        self.assertEqual(payload.get("status"), "halted", payload)
        self.assertEqual(payload.get("reason"), OWN_REASON, payload)
        self.assertEqual(self.names(payload.get("own_failures")), ["Test suite (pytest)"], payload)
        self.assertEqual(self.names([payload.get("external_hold")]), [HOLD_NAME], payload)
        self.assertNotIn(HOLD_NAME, self.names(payload.get("own_failures")))
        self.assert_no_merge_path(result)


class TestAllGreenAndForbiddenActions(_FinalizeHoldCase):
    def test_tq600a_13_xx_all_green_is_unchanged_apart_from_the_one_read(self) -> None:
        # covers: TQ-600a-13-xx
        # angle: reachability
        result = self.run_with(_all_green(_scenario("scenario-A-hold-only.json")))
        expected = list(_PRE_CHANGE_LABELS)
        expected.insert(expected.index(_MERGE_GATE), CHECKS_LABEL)
        self.assertEqual(self.labels(result), expected)
        payload = result.result
        self.assertEqual(payload.get("status"), "ok", payload)
        step4 = [e["outcome"] for e in payload["step_outcomes"] if e["step"] == "Step 4 of 9"]
        self.assertEqual(step4, [_PRE_CHANGE_STEP4_OUTCOME])
        self.assertIn(4, payload["completed_steps"])
        self.assertEqual(payload["merge_result"], {"merged": True, "sha": "fee1dead"})

    def test_tq600a_13_xx_held_paths_take_no_forbidden_action(self) -> None:
        # covers: TQ-600a-13-xx
        # angle: discrimination
        for name in ("scenario-A-hold-only.json", "scenario-B-hold-plus-pytest-failure.json"):
            with self.subTest(scenario=name):
                result = self.run_with(_scenario(name))
                read = [c for c in result.agent_calls if c.label == CHECKS_LABEL]
                self.assertEqual(len(read), 1, self.labels(result))
                self.assertNotIn("--watch", str(read[0].prompt))
                self.assertNotIn("gh run rerun", str(read[0].prompt))
                later = self.after_read(result)
                self.assertEqual([c.label for c in later if c.label != _CLEANUP], [])
                for call in later:
                    for fragment in _FORBIDDEN_PROMPT_FRAGMENTS:
                        self.assertNotIn(fragment, str(call.prompt), call.label)


class TestOnlyTheExactNameIsTheHold(_FinalizeHoldCase):
    LOOKALIKES = ("post-merge suite status", "Post-merge suite status (copy)", "Post-merge suite")

    def test_tq600a_13_xx_only_the_exact_check_name_is_the_hold(self) -> None:
        # covers: TQ-600a-13-xx
        # angle: boundary
        for lookalike in self.LOOKALIKES:
            with self.subTest(name=lookalike):
                checks = _scenario("scenario-A-hold-only.json")
                for c in checks:
                    if c["name"] == HOLD_NAME:
                        c["name"] = lookalike
                result = self.run_with(checks)
                payload = result.result
                self.assertEqual(len(self.labels_of(result, CHECKS_LABEL)), 1, self.labels(result))
                self.assertNotEqual(payload.get("reason"), HOLD_REASON, payload)
                self.assertFalse(payload.get("external_hold"), payload)
                self.assertEqual(len(self.labels_of(result, _MERGE)), 1, self.labels(result))
                self.assertEqual(payload.get("status"), "ok", payload)
        for malformed in ("no json in this reply at all", {"oops": True}, []):
            with self.subTest(reply=malformed):
                result = self.run_with(malformed)
                self.assertEqual(len(self.labels_of(result, CHECKS_LABEL)), 1, self.labels(result))
                self.assertNotEqual(result.result.get("reason"), HOLD_REASON, result.result)
                self.assertFalse(result.result.get("external_hold"), result.result)
                self.assertEqual(len(self.labels_of(result, _MERGE)), 1, self.labels(result))
                self.assertEqual(result.result.get("status"), "ok", result.result)

    def labels_of(self, result: Any, label: str) -> list[Any]:
        return [c for c in result.agent_calls if c.label == label]


if __name__ == "__main__":
    unittest.main()
