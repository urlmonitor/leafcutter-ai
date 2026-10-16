"""
MODULE: unit_tests/workflows/test_bo2400f_13_workspace_refusal_workflow.py
GOAL: Behavioural (workflow-level) tests for the BO-2400f-13 family --
      BO-2400f-13, BO-2400f-13-i, BO-2400f-13-ii, BO-2400f-13-iii, and
      BO-2400f-13-iv -- driving fast-lane-ship.js's Phase 1 (Worktree) guard
      through unit_tests/_workflow_engine_harness.py's run_workflow_under_e2().

=== Restated for BO-4300c-3 (test-drift repair, classification: test_drift) ===

Before BO-4300c-3 fast-lane-ship.js read a worktree-phase payload keyed by
``outcome`` (``opened`` / ``refused``), treated a payload with a path but no
outcome as a fail-closed refusal, and ended an occupied workspace with a
distinct ``refused`` terminal status carrying the refusal's facts as structured
fields.

The run now takes its workspace from the workspace maker's answer and from
nowhere else (BO-4300c-2 / BO-4300c-3): one JSON object whose ``status`` is
``"ok"`` and whose ``workspace_path`` is a non-empty string. Anything else --
a refusal included -- ends the run with ``status: "error"`` and
``abort_reason: "workspace-not-ready"``, quoting what was received. The same
intent survives in the maker's terms:

  * an occupied workspace stops the run before ANY dispatch, so no downstream
    step and no release step runs;
  * the refusal's facts (who occupies the workspace, the unsent work, the
    options and which of them destroy) still reach the operator -- as the quoted
    answer in the stop message;
  * an answer that is not unmistakably "ok" with a workspace path (the legacy
    empty-path shape, an empty reply, a path with no status) fails closed
    before Resolve;
  * a ready answer proceeds, proved by PRESENCE of the next dispatch, and its
    newness / base-commit facts ride the terminal payload.

The maker's answer is handed to the workflow as ``args.workspace`` (the way an
entry skill passes it, BO-4300a-1-ib), so each hostile or refused shape reaches
the workflow exactly as written; the harness does not restate it.

=== Why this is not a grep test ===

Every assertion below drives fast-lane-ship.js through run_workflow_under_e2(),
which executes the script's REAL top-level control flow in a Node.js
subprocess (inside a locked-down vm context -- see _workflow_engine_harness.py)
and records every agent() dispatch verbatim, plus the script's own terminal
return value. Nothing here inspects the JS source text.
"""
from __future__ import annotations

import json
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
    ac_id: str, workspace_answer: Any, label_responses: dict[str, Any] | None = None
) -> HarnessResult:
    """Run the lane with the maker's answer handed in as args.workspace."""
    return run_workflow_under_e2(
        _WORKFLOW_PATH,
        label_responses=label_responses or {},
        args={"ac": ac_id, "workspace": workspace_answer},
    )


def _calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def _labels_seen(result: HarnessResult) -> list[str | None]:
    return [c.label for c in result.agent_calls]


def _quoted(payload: dict[str, Any]) -> str:
    """The stop message, with every JSON string made comparable (compact form)."""
    return payload.get("message") or ""


def _refusal(**refusal: Any) -> dict[str, Any]:
    """A refused maker answer carrying ``refusal`` facts (status states refused)."""
    return {
        "status": "refused",
        "code": "WORKSPACE_OCCUPIED",
        "branch": "fast-lane/BO-STUB-1",
        "refusal": {"reason": "workspace_occupied", "ac_id": "BO-STUB-1", **refusal},
        "message": "The workspace for BO-STUB-1 is occupied.",
    }


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
        refusal_payload = _refusal(
            occupied_path=str(self.worktree_root / "worktrees" / "bo-stub-1"),
            occupant="foreign",
            options=[
                {"action": "inspect", "description": "Look inside the workspace.", "destructive": False}
            ],
        )
        result = _run_lane("BO-STUB-1", refusal_payload)

        labels = _labels_seen(result)
        self.assertEqual(
            labels,
            [],
            f"No dispatch of any kind may follow a refused workspace answer. "
            f"Got labels: {labels}. stderr={result.stderr!r}",
        )
        for forbidden in _DOWNSTREAM_LABELS:
            self.assertFalse(
                _calls_with_label(result, forbidden),
                f"'{forbidden}' must NOT be dispatched on an occupied workspace.",
            )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertEqual(payload.get("status"), "error", f"Got: {payload}")
        self.assertEqual(payload.get("abort_reason"), "workspace-not-ready", f"Got: {payload}")
        self.assertIn("WORKSPACE_OCCUPIED", _quoted(payload), f"Got: {payload}")
        self.assertFalse(payload.get("pr_url"))


class TestOccupiedRefusalDoesNotInvokeRelease(_FixtureCase):
    """BO-2400f-13-iii: the refusal precedes the claim by two phases -- no release."""

    def test_refusing_run_does_not_invoke_the_release_step(self) -> None:
        # covers: BO-2400f-13-iii
        # angle: failure
        refusal_payload = _refusal(
            occupied_path="/tmp/occupied", occupant="foreign", options=[]
        )
        result = _run_lane("BO-STUB-1", refusal_payload)

        release_labels = [lbl for lbl in _labels_seen(result) if lbl and lbl.startswith("release-on")]
        self.assertEqual(
            release_labels,
            [],
            f"A refusing run at Phase 1 holds no claim and must never dispatch a "
            f"release-on-* call. Got: {release_labels}",
        )
        self.assertFalse(_calls_with_label(result, "claim-connected"))
        self.assertIsNotNone(result.result)
        self.assertEqual(result.result.get("status"), "error", f"Got: {result.result}")
        self.assertEqual(
            result.result.get("abort_reason"), "workspace-not-ready", f"Got: {result.result}"
        )


class TestBlankOrMissingOutcomeRefuses(_FixtureCase):
    """BO-2400f-13: FAIL CLOSED on an unreadable/legacy workspace answer."""

    def _assert_refuses_and_no_resolver(self, answer: Any, case_name: str) -> None:
        result = _run_lane("BO-STUB-1", answer)

        self.assertFalse(
            _calls_with_label(result, "resolve-connected"),
            f"[{case_name}] An unreadable/legacy workspace answer must refuse "
            f"before Resolve, never proceed to dispatch the resolver. "
            f"Labels seen: {_labels_seen(result)}. stderr={result.stderr!r}",
        )
        self.assertEqual(
            _labels_seen(result), [], f"[{case_name}] No dispatch may follow the stop."
        )
        self.assertIsNotNone(result.result, f"[{case_name}] stderr={result.stderr!r}")
        self.assertEqual(
            result.result.get("status"), "error", f"[{case_name}] Got: {result.result}"
        )
        self.assertEqual(
            result.result.get("abort_reason"),
            "workspace-not-ready",
            f"[{case_name}] Got: {result.result}",
        )
        self.assertIn(
            "Received:",
            _quoted(result.result),
            f"[{case_name}] The stop must quote what it received. Got: {result.result}",
        )

    def test_blank_or_missing_outcome_refuses_rather_than_proceeding(self) -> None:
        # covers: BO-2400f-13
        # angle: failure
        """Three fail-closed shapes in turn: the legacy empty-path success
        shape, a totally empty reply, and -- the sharpest case -- an answer that
        DOES carry a worktree_path but states no status. That last shape was
        once read as a SUCCESS because the only check was on the path; the one
        acceptance predicate takes the location only from a ready answer."""
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
        refusal_payload = _refusal(
            occupied_path="/tmp/own-leftover",
            occupant="own_prior_attempt",
            occupant_branch="fast-lane/BO-STUB-1",
            uncommitted_changes=True,
            published={"pushed": False, "pr_url": None, "pr_lookup": "ok"},
            options=[
                {"action": "inspect", "description": "Look inside.", "destructive": False},
                {"action": "clear", "description": "Clear and re-run.", "destructive": True},
                {"action": "elsewhere", "description": "Aim the lane elsewhere.", "destructive": False},
            ],
        )
        result = _run_lane("BO-STUB-1", refusal_payload)

        for forbidden in _DOWNSTREAM_LABELS:
            self.assertFalse(_calls_with_label(result, forbidden))

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertEqual(payload.get("status"), "error", f"Got: {payload}")
        message = _quoted(payload)
        # The facts reach the operator inside the quoted answer, each as the maker wrote it.
        self.assertIn(
            '"occupant":"own_prior_attempt"',
            message,
            f"The occupant classification must reach the operator. Got: {payload}",
        )
        self.assertIn(
            '"uncommitted_changes":true',
            message,
            f"The uncommitted-changes fact must reach the operator. Got: {payload}",
        )
        self.assertIn(
            '"pushed":false',
            message,
            f"The published/pushed fact must reach the operator. Got: {payload}",
        )


class TestForeignOccupantRefusalReachesOperator(_FixtureCase):
    """BO-2400f-13-ii: a foreign occupant's facts must reach the operator."""

    def test_foreign_occupant_refusal_reaches_the_operator_with_no_dispatch(self) -> None:
        # covers: BO-2400f-13-ii
        # angle: criterion
        refusal_payload = _refusal(
            occupied_path="/tmp/foreign-occupant",
            occupant="foreign",
            occupant_branch="feature/unrelated-work",
            occupant_kind="registered_worktree_other_branch",
            options=[
                {"action": "inspect", "description": "Look inside.", "destructive": False}
            ],
        )
        result = _run_lane("BO-STUB-1", refusal_payload)

        for forbidden in _DOWNSTREAM_LABELS:
            self.assertFalse(_calls_with_label(result, forbidden))

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertEqual(payload.get("status"), "error", f"Got: {payload}")
        message = _quoted(payload)
        self.assertIn(
            '"occupant":"foreign"',
            message,
            f"The foreign classification must reach the operator. Got: {payload}",
        )
        self.assertIn(
            '"occupant_kind":"registered_worktree_other_branch"',
            message,
            f"The occupant_kind must reach the operator. Got: {payload}",
        )
        self.assertIn(
            '"action":"inspect"',
            message,
            f"Options must reach the operator. Got: {payload}",
        )
        self.assertNotIn(
            '"destructive":true',
            message,
            f"No option on a foreign refusal may be destructive. Got: {payload}",
        )


class TestFreeLocationProceedsToDownstreamDispatches(_FixtureCase):
    """BO-2400f-13-iv: LOAD-BEARING proceed-by-presence test."""

    def test_free_location_proceeds_to_the_downstream_dispatches(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: criterion
        ready_answer = {
            "status": "ok",
            "code": "OK",
            "workspace_path": str(self.worktree_root),
            "worktree_path": str(self.worktree_root),
            "branch": "fast-lane/BO-STUB-1",
            "ac_store_path": str(self.worktree_root / "docs" / "acceptance-criteria"),
            "created": True,
            "base_commit": "a" * 40,
            "base_matches_origin_main": True,
        }
        result = _run_lane(
            "BO-STUB-1",
            ready_answer,
            {"resolve-connected": {"ac_ids": [], "message": "0 to build"}},
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertNotEqual(
            payload.get("abort_reason"),
            "workspace-not-ready",
            f"A ready workspace answer must never be refused. Got: {payload}",
        )
        self.assertTrue(
            _calls_with_label(result, "resolve-connected"),
            f"A ready workspace must proceed to dispatch the resolver "
            f"(proof by PRESENCE, not merely the absence of a refusal -- a "
            f"crashed run would also satisfy that weaker check). "
            f"Labels seen: {_labels_seen(result)}. stderr={result.stderr!r}",
        )

        # The newness/base-commit facts (BO-2400f-13-iv) must ride the payload
        # all the way to the operator.
        self.assertIn(
            "created",
            payload,
            f"The terminal payload must carry whether the workspace is new. Got: {payload}",
        )
        self.assertEqual(payload.get("created"), True, f"Got: {payload}")
        self.assertEqual(
            payload.get("base_commit"),
            "a" * 40,
            f"The terminal payload must name the mainline point the workspace "
            f"was cut from. Got: {payload}",
        )
        self.assertIs(
            payload.get("base_matches_origin_main"),
            True,
            f"The terminal payload must say whether the base matches the "
            f"current origin/main. Got: {payload}",
        )

    def test_a_ready_answer_scripted_as_the_maker_dispatch_is_taken_the_same_way(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: seam
        """The same ready answer, delivered as the reply to the ONE maker dispatch
        (no args.workspace, the run names its project root), is accepted and the
        run proceeds -- so the proof above does not depend on the hand-in path."""
        ready_answer = {
            "status": "ok",
            "workspace_path": str(self.worktree_root),
            "branch": "fast-lane/BO-STUB-1",
            "created": False,
            "base_commit": "b" * 40,
            "base_matches_origin_main": False,
        }
        result = run_workflow_under_e2(
            _WORKFLOW_PATH,
            label_responses={
                "fastlane-worktree": ready_answer,
                "resolve-connected": {"ac_ids": [], "message": "0 to build"},
            },
            args={"ac": "BO-STUB-1", "project_root": str(self.worktree_root)},
        )
        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        self.assertEqual(_labels_seen(result)[:2], ["fastlane-worktree", "resolve-connected"])
        self.assertEqual(result.result.get("base_commit"), "b" * 40, f"Got: {result.result}")
        self.assertIs(result.result.get("created"), False, f"Got: {result.result}")
        self.assertEqual(
            json.dumps(result.result.get("base_matches_origin_main")), "false", f"Got: {result.result}"
        )


if __name__ == "__main__":
    unittest.main()
