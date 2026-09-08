"""
MODULE: unit_tests/workflows/test_bo2400f_13_workspace_refusal_workflow.py
GOAL: RED behavioural (workflow-level) tests for the BO-2400f-13 family —
      BO-2400f-13, BO-2400f-13-i, BO-2400f-13-ii, BO-2400f-13-iii, and
      BO-2400f-13-iv — driving fast-lane-ship.js's Phase 1 (Worktree) guard
      through unit_tests/_workflow_engine_harness.py's run_workflow_under_e2().

=== Target contract (greenfield today) ===

Today, fast-lane-ship.js's ONLY check on the worktree phase result is:

    if (!worktreeResult || !worktreeResult.worktree_path) {
      return { status: "error", message: "...", failing_phase: "worktree" };
    }

This means:
  - A refusal payload (no worktree_path) already halts the run today — but
    the terminal status is the generic "error", never the distinct
    "refused" outcome the AC requires, and none of the refusal's facts
    (occupant, uncommitted_changes, published, options, message) are
    relayed to the operator at all.
  - A payload that HAS worktree_path but a null/absent `outcome` (the
    fail-closed case BO-2400f-13 requires) is treated as a SUCCESS today —
    the run proceeds straight to Resolve. This is the sharpest RED case:
    a payload the AC says must refuse instead builds.
  - A fully "opened" payload's `created` / `base_commit` /
    `base_matches_origin_main` facts (BO-2400f-13-iv) are never read or
    relayed anywhere in the script.

=== Why this is not a grep test ===

Every assertion below drives fast-lane-ship.js through run_workflow_under_e2(),
which executes the script's REAL top-level control flow in a Node.js
subprocess (inside a locked-down vm context — see _workflow_engine_harness.py)
and records every agent() dispatch verbatim, plus the script's own terminal
return value. Nothing here inspects the JS source text.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

_DOWNSTREAM_LABELS = {
    "resolve-connected",
    "check-producibility",
    "claim-connected",
    "test-writer",
    "commit",
    "pull-request",
}
_BUILD_AGENT_TYPES = {"python-coder", "test-writer"}


def _run_lane(
    ac_id: str, label_responses: dict[str, Any], args: dict[str, Any] | None = None
) -> HarnessResult:
    return run_workflow_under_e2(
        _WORKFLOW_PATH,
        label_responses=label_responses,
        args={"ac": ac_id, **(args or {})},
    )


def _calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def _labels_seen(result: HarnessResult) -> list[str | None]:
    return [c.label for c in result.agent_calls]


class _FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        (self.worktree_root / "docs" / "acceptance-criteria").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestOccupiedWorkspaceRefusesBeforeAnyDispatch(_FixtureCase):
    """BO-2400f-13 / BO-2400f-13-iii: LOAD-BEARING zero-dispatch test."""

    def test_occupied_workspace_refuses_before_any_dispatch(self) -> None:
        # covers: BO-2400f-13
        # angle: criterion
        refusal_payload = {
            "outcome": "refused",
            "branch": "fast-lane/BO-STUB-1",
            "refusal": {
                "reason": "workspace_occupied",
                "ac_id": "BO-STUB-1",
                "occupied_path": str(self.worktree_root / "worktrees" / "bo-stub-1"),
                "occupant": "foreign",
                "occupant_branch": None,
                "uncommitted_changes": None,
                "published": {"pushed": None, "pr_url": None, "pr_lookup": "not_attempted"},
                "options": [
                    {"action": "inspect", "description": "Look inside the workspace.", "destructive": False}
                ],
                "message": "The workspace for BO-STUB-1 is occupied at <path>.",
            },
        }
        result = _run_lane("BO-STUB-1", {"fastlane-worktree": refusal_payload})

        labels = _labels_seen(result)
        self.assertEqual(
            labels,
            ["fastlane-worktree"],
            f"Only the worktree-phase dispatch may occur before/at the refusal — "
            f"the operator has paid for exactly one check. Got labels: {labels}. "
            f"stderr={result.stderr!r}",
        )
        for forbidden in _DOWNSTREAM_LABELS:
            self.assertFalse(
                _calls_with_label(result, forbidden),
                f"'{forbidden}' must NOT be dispatched on an occupied workspace.",
            )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertEqual(
            payload.get("status"),
            "refused",
            f"Expected the distinct 'refused' terminal status (today's code "
            f"returns the generic 'error'). Got: {payload}",
        )
        self.assertFalse(payload.get("pr_url"))


class TestOccupiedRefusalDoesNotInvokeRelease(_FixtureCase):
    """BO-2400f-13-iii: the refusal precedes the claim by two phases — no release."""

    def test_refusing_run_does_not_invoke_the_release_step(self) -> None:
        # covers: BO-2400f-13-iii
        # angle: failure
        refusal_payload = {
            "outcome": "refused",
            "branch": "fast-lane/BO-STUB-1",
            "refusal": {
                "reason": "workspace_occupied",
                "ac_id": "BO-STUB-1",
                "occupied_path": "/tmp/occupied",
                "occupant": "foreign",
                "occupant_branch": None,
                "uncommitted_changes": None,
                "published": {"pushed": None, "pr_url": None, "pr_lookup": "not_attempted"},
                "options": [],
                "message": "occupied",
            },
        }
        result = _run_lane("BO-STUB-1", {"fastlane-worktree": refusal_payload})

        release_labels = [lbl for lbl in _labels_seen(result) if lbl and lbl.startswith("release-on")]
        self.assertEqual(
            release_labels,
            [],
            f"A refusing run at Phase 1 holds no claim and must never dispatch a "
            f"release-on-* call. Got: {release_labels}",
        )
        self.assertFalse(_calls_with_label(result, "claim-connected"))
        self.assertIsNotNone(result.result)
        self.assertEqual(result.result.get("status"), "refused", f"Got: {result.result}")


class TestBlankOrMissingOutcomeRefuses(_FixtureCase):
    """BO-2400f-13: FAIL CLOSED on an unreadable/legacy worktree payload."""

    def _assert_refuses_and_no_resolver(self, payload: dict[str, Any], case_name: str) -> None:
        result = _run_lane("BO-STUB-1", {"fastlane-worktree": payload})

        self.assertFalse(
            _calls_with_label(result, "resolve-connected"),
            f"[{case_name}] An unreadable/legacy worktree outcome must refuse "
            f"before Resolve, never proceed to dispatch the resolver. "
            f"Labels seen: {_labels_seen(result)}. stderr={result.stderr!r}",
        )
        self.assertIsNotNone(result.result, f"[{case_name}] stderr={result.stderr!r}")
        self.assertEqual(
            result.result.get("status"),
            "refused",
            f"[{case_name}] Got: {result.result}",
        )
        self.assertIn(
            "could not be determined",
            (result.result.get("message") or "").lower(),
            f"[{case_name}] The refusal must say occupancy could not be "
            f"determined. Got: {result.result}",
        )

    def test_blank_or_missing_outcome_refuses_rather_than_proceeding(self) -> None:
        # covers: BO-2400f-13
        # angle: failure
        """Three fail-closed shapes in turn: the legacy empty-path success
        shape, a totally empty reply, and — the sharpest case — a reply that
        DOES carry a worktree_path but whose outcome is explicitly null. Today's
        code treats the third shape as a SUCCESS (proceeds to Resolve) because
        its only check is `!worktreeResult.worktree_path`."""
        self._assert_refuses_and_no_resolver(
            {"worktree_path": ""}, "legacy-blank-worktree-path"
        )
        self._assert_refuses_and_no_resolver({}, "empty-reply")
        self._assert_refuses_and_no_resolver(
            {
                "outcome": None,
                "worktree_path": "/tmp/some/existing/path",
                "branch": "fast-lane/BO-STUB-1",
            },
            "null-outcome-with-present-worktree-path",
        )


class TestOwnLeftoverRefusalReachesOperator(_FixtureCase):
    """BO-2400f-13-i: the own-prior-attempt facts must reach the operator."""

    def test_own_leftover_refusal_reaches_the_operator_with_no_dispatch(self) -> None:
        # covers: BO-2400f-13-i
        # angle: criterion
        refusal_payload = {
            "outcome": "refused",
            "branch": "fast-lane/BO-STUB-1",
            "refusal": {
                "reason": "workspace_occupied",
                "ac_id": "BO-STUB-1",
                "occupied_path": "/tmp/own-leftover",
                "occupant": "own_prior_attempt",
                "occupant_branch": "fast-lane/BO-STUB-1",
                "uncommitted_changes": True,
                "published": {"pushed": False, "pr_url": None, "pr_lookup": "ok"},
                "options": [
                    {"action": "inspect", "description": "Look inside.", "destructive": False},
                    {"action": "clear", "description": "Clear and re-run.", "destructive": True},
                    {"action": "elsewhere", "description": "Aim the lane elsewhere.", "destructive": False},
                ],
                "message": "Your own earlier attempt at BO-STUB-1 left uncommitted work.",
            },
        }
        result = _run_lane("BO-STUB-1", {"fastlane-worktree": refusal_payload})

        for forbidden in _DOWNSTREAM_LABELS:
            self.assertFalse(_calls_with_label(result, forbidden))

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertEqual(payload.get("status"), "refused", f"Got: {payload}")
        refusal = payload.get("refusal") or {}
        self.assertEqual(
            refusal.get("occupant"),
            "own_prior_attempt",
            f"The occupant classification must reach the operator. Got: {payload}",
        )
        self.assertIs(
            refusal.get("uncommitted_changes"),
            True,
            f"The uncommitted-changes fact must reach the operator. Got: {payload}",
        )
        self.assertEqual(
            (refusal.get("published") or {}).get("pushed"),
            False,
            f"The published/pushed fact must reach the operator. Got: {payload}",
        )


class TestForeignOccupantRefusalReachesOperator(_FixtureCase):
    """BO-2400f-13-ii: a foreign occupant's facts must reach the operator."""

    def test_foreign_occupant_refusal_reaches_the_operator_with_no_dispatch(self) -> None:
        # covers: BO-2400f-13-ii
        # angle: criterion
        refusal_payload = {
            "outcome": "refused",
            "branch": "fast-lane/BO-STUB-1",
            "refusal": {
                "reason": "workspace_occupied",
                "ac_id": "BO-STUB-1",
                "occupied_path": "/tmp/foreign-occupant",
                "occupant": "foreign",
                "occupant_branch": "feature/unrelated-work",
                "occupant_kind": "registered_worktree_other_branch",
                "options": [
                    {"action": "inspect", "description": "Look inside.", "destructive": False}
                ],
                "message": "The workspace is occupied by unrelated work on feature/unrelated-work.",
            },
        }
        result = _run_lane("BO-STUB-1", {"fastlane-worktree": refusal_payload})

        for forbidden in _DOWNSTREAM_LABELS:
            self.assertFalse(_calls_with_label(result, forbidden))

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertEqual(payload.get("status"), "refused", f"Got: {payload}")
        refusal = payload.get("refusal") or {}
        self.assertEqual(
            refusal.get("occupant"),
            "foreign",
            f"The foreign classification must reach the operator. Got: {payload}",
        )
        self.assertEqual(
            refusal.get("occupant_kind"),
            "registered_worktree_other_branch",
            f"The occupant_kind must reach the operator. Got: {payload}",
        )
        options = refusal.get("options") or []
        self.assertTrue(options, f"Options must reach the operator. Got: {payload}")
        for opt in options:
            self.assertFalse(
                opt.get("destructive", True),
                f"No option on a foreign refusal may be destructive. Got: {opt}",
            )


class TestFreeLocationProceedsToDownstreamDispatches(_FixtureCase):
    """BO-2400f-13-iv: LOAD-BEARING proceed-by-presence test."""

    def test_free_location_proceeds_to_the_downstream_dispatches(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: criterion
        opened_payload = {
            "outcome": "opened",
            "worktree_path": str(self.worktree_root),
            "branch": "fast-lane/BO-STUB-1",
            "ac_store_path": str(self.worktree_root / "docs" / "acceptance-criteria"),
            "created": True,
            "base_commit": "a" * 40,
            "base_matches_origin_main": True,
        }
        result = _run_lane(
            "BO-STUB-1",
            {
                "fastlane-worktree": opened_payload,
                "resolve-connected": {"ac_ids": [], "message": "0 to build"},
            },
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertNotEqual(
            payload.get("status"),
            "refused",
            f"A free-location opened workspace must never be refused. Got: {payload}",
        )
        self.assertTrue(
            _calls_with_label(result, "resolve-connected"),
            f"An opened workspace must proceed to dispatch the resolver "
            f"(proof by PRESENCE, not merely the absence of a refusal — a "
            f"crashed run would also satisfy that weaker check). "
            f"Labels seen: {_labels_seen(result)}. stderr={result.stderr!r}",
        )

        # The newness/base-commit facts (BO-2400f-13-iv) must ride the payload
        # all the way to the operator — today nothing in fast-lane-ship.js
        # reads or relays created/base_commit/base_matches_origin_main at all.
        self.assertIn(
            "created",
            payload,
            f"The terminal payload must carry whether the workspace is new. Got: {payload}",
        )
        self.assertIn(
            "base_commit",
            payload,
            f"The terminal payload must name the mainline point the workspace "
            f"was cut from. Got: {payload}",
        )
        self.assertIn(
            "base_matches_origin_main",
            payload,
            f"The terminal payload must say whether the base matches the "
            f"current origin/main. Got: {payload}",
        )


if __name__ == "__main__":
    unittest.main()
