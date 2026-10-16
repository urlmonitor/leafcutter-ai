"""
MODULE: unit_tests/workflows/test_bo2400f_3_i_worktree_verify_workflow.py
GOAL: Behavioural (workflow-level) tests for the location guard in
      fast-lane-ship.js's Phase 1 (Worktree), driven through
      unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() --
      restated for BO-4300c-3 (test-drift repair, classification: test_drift).

=== What this file used to prove (BO-2400f-3-i) ===

fast-lane-ship.js asked git a second time where the worktree was (the
'fastlane-worktree-verify' dispatch) and chose ``gitReportedPath ||
claimedWorktreePath``. This file pinned the narrowing of that fallback: a probe
that listed worktrees but omitted this run's own branch halted the run, a
probe that confirmed the branch won over the worktree phase's own claim, and a
probe that never answered fell back to the claim.

=== What replaced it (BO-4300c-3, BO-4300f-1) ===

The lane takes its location from the workspace maker's ready answer and from
nowhere else: ``workspace_path`` of one JSON object whose status is "ok". There
is no second git question and no claimed-versus-reported choice, so there is no
fallback left to narrow. The guarantees this file now holds the lane to are the
ones that replace the old three:

  * no second probe of the location is dispatched at all;
  * every later phase runs against the maker's ``workspace_path`` -- a scripted
    reply for the old probe label, whatever it says, is never consulted;
  * an answer that is not a ready one stops the lane before Resolve, quoting
    what it received, so a location nobody was given is never used.

Each assertion is on the RECORDED dispatch list and the run's terminal payload;
nothing here inspects the JS source text.
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

_AC_ID = "BO-STUB-1"
_BRANCH = f"fast-lane/{_AC_ID}"
_OTHER_CLONE_PATH = "/mnt/c/Users/henzeh/Documents/Scripts/leafcutter/leafcutter-ai"
_RETIRED_PROBE_LABEL = "fastlane-worktree-verify"


def _run_lane(
    workspace_answer: Any, label_responses: dict[str, Any] | None = None
) -> HarnessResult:
    """Run the lane with the maker's answer handed in as args.workspace."""
    return run_workflow_under_e2(
        _WORKFLOW_PATH,
        label_responses=label_responses or {},
        args={"ac": _AC_ID, "workspace": workspace_answer},
    )


def _labels_seen(result: HarnessResult) -> list[str | None]:
    return [c.label for c in result.agent_calls]


def _calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def _ready_answer(workspace_path: str) -> dict[str, Any]:
    """A well-formed ready maker answer (BO-4300c-2)."""
    return {
        "status": "ok",
        "code": "OK",
        "workspace_path": workspace_path,
        "worktree_path": workspace_path,
        "branch": _BRANCH,
        "created": True,
        "base_commit": "a" * 40,
        "base_matches_origin_main": True,
    }


def _stale_clone_probe_reply() -> dict[str, Any]:
    """What the retired second probe used to say from a stale second clone."""
    return {
        "worktree_path": _OTHER_CLONE_PATH,
        "raw": (
            f"worktree {_OTHER_CLONE_PATH}\n"
            "HEAD deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n"
            "branch refs/heads/main\n"
        ),
    }


class _FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.real_worktree_root = Path(self._tmp.name)
        (self.real_worktree_root / "docs" / "acceptance-criteria").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestNoSecondProbeOfTheLocation(_FixtureCase):
    """The lane no longer asks git where the workspace is (angle: criterion)."""

    def test_no_second_probe_of_the_location_is_dispatched(self) -> None:
        # covers: BO-4300c-3
        # angle: criterion
        result = _run_lane(
            _ready_answer(str(self.real_worktree_root)),
            {"resolve-connected": {"ac_ids": [], "message": "0 to build"}},
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        self.assertTrue(
            _calls_with_label(result, "resolve-connected"),
            f"A ready workspace must proceed to Resolve (proof by presence). "
            f"Labels seen: {_labels_seen(result)}. stderr={result.stderr!r}",
        )
        self.assertEqual(
            _calls_with_label(result, _RETIRED_PROBE_LABEL),
            [],
            f"The lane must not dispatch a second location probe "
            f"({_RETIRED_PROBE_LABEL!r}). Labels seen: {_labels_seen(result)}",
        )


class TestLaterPhasesRunAgainstTheMakersWorkspacePath(_FixtureCase):
    """The ready answer's workspace_path outranks anything else (angle: discrimination).

    Goes red under the wrong version that keeps ``gitReportedPath ||
    claimedWorktreePath``: a scripted reply for the old probe label that names a
    DIFFERENT clone would win there, and the resolver would be dispatched
    against it.
    """

    def test_a_scripted_reply_for_the_retired_probe_is_never_consulted(self) -> None:
        # covers: BO-4300c-3
        # angle: discrimination
        real_path = str(self.real_worktree_root)
        result = _run_lane(
            _ready_answer(real_path),
            {
                _RETIRED_PROBE_LABEL: _stale_clone_probe_reply(),
                "resolve-connected": {"ac_ids": [], "message": "0 to build"},
            },
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        resolve_calls = _calls_with_label(result, "resolve-connected")
        self.assertTrue(
            resolve_calls,
            f"The lane must proceed to Resolve on the maker's ready answer. "
            f"Labels seen: {_labels_seen(result)}. stderr={result.stderr!r}",
        )
        dispatch_text = str(resolve_calls[0].prompt)
        self.assertIn(
            real_path,
            dispatch_text,
            f"The resolver must be dispatched against the maker's "
            f"workspace_path. Dispatch text: {dispatch_text!r}",
        )
        self.assertNotIn(
            _OTHER_CLONE_PATH,
            dispatch_text,
            f"A location the maker did not give must never reach a dispatch. "
            f"Dispatch text: {dispatch_text!r}",
        )
        self.assertNotIn(
            _OTHER_CLONE_PATH,
            " ".join(str(c.prompt) for c in result.agent_calls),
            "No dispatch of the run may name a location other than the maker's.",
        )

    def test_the_location_comes_only_from_workspace_path_not_from_worktree_path(self) -> None:
        # covers: BO-4300c-3
        # angle: boundary
        """A ready answer whose legacy alias disagrees with workspace_path: the
        lane uses workspace_path (BO-4300c-2: worktree_path is only its alias)."""
        real_path = str(self.real_worktree_root)
        answer = _ready_answer(real_path)
        answer["worktree_path"] = _OTHER_CLONE_PATH
        result = _run_lane(
            answer, {"resolve-connected": {"ac_ids": [], "message": "0 to build"}}
        )

        resolve_calls = _calls_with_label(result, "resolve-connected")
        self.assertTrue(resolve_calls, f"Labels seen: {_labels_seen(result)}")
        dispatch_text = str(resolve_calls[0].prompt)
        self.assertIn(real_path, dispatch_text)
        self.assertNotIn(_OTHER_CLONE_PATH, dispatch_text)


class TestAnAnswerThatIsNotReadyStopsBeforeResolve(_FixtureCase):
    """An answer without status ok and a workspace_path stops the lane (angle: failure)."""

    def test_a_path_without_a_ready_status_halts_before_resolve(self) -> None:
        # covers: BO-4300c-3
        # angle: failure
        """The old claim, a location with no status, is exactly the shape the
        lane once forgave by falling back to the claim. It must now stop the
        run before Resolve and quote what was received, naming the path only as
        part of that quote."""
        result = _run_lane(
            {"worktree_path": _OTHER_CLONE_PATH, "branch": _BRANCH},
            {"resolve-connected": {"ac_ids": [], "message": "0 to build"}},
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        self.assertEqual(payload.get("status"), "error", f"Got: {payload}")
        self.assertEqual(payload.get("abort_reason"), "workspace-not-ready", f"Got: {payload}")
        self.assertIn(_BRANCH, str(payload.get("message")), f"Got: {payload}")
        self.assertEqual(
            _labels_seen(result),
            [],
            f"No dispatch may follow the stop. Labels seen: {_labels_seen(result)}",
        )


if __name__ == "__main__":
    unittest.main()
