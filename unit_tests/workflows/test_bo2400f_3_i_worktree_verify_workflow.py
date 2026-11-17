"""
MODULE: unit_tests/workflows/test_bo2400f_3_i_worktree_verify_workflow.py
GOAL: behavioural (workflow-level) tests for BO-2400f-3-i -- the lane must never trust a CLAIMED
      worktree location -- driven through unit_tests/_workflow_engine_harness.py's
      run_workflow_under_e2() against fast-lane-ship.js's workspace step.

=== The defect (BO-2400f-3-i) and how BO-4300c-3 closes it for good ===

The lane used to take its location from a worktree agent's claim and cross-check it with a second
"fastlane-worktree-verify" git probe. An absent probe answer and a probe answer that omitted this run's
own branch both collapsed to the same falsy value and both fell back to the claim, so two runs died on
2026-09-14 at Resolve inside a stale second clone.

Since BO-4300c-3 / BO-4300a-1-ia the claim, the probe and the fallback are all gone. The location is the
``workspace_path`` of the workspace maker's ACCEPTED answer (one ``workspace-ensure`` dispatch, or
``args.workspace``) and nothing else: anything that is not an ok answer with a workspace_path ends the run,
quoting what was received, before any later phase. These tests re-state the descriptor arms against that
contract: a reply that is a stale-clone git listing instead of an answer halts before Resolve and is
quoted (not forgiven), no later phase is dispatched, a good answer is used verbatim even when another
field names a different path, and an absent answer is NOT forgiven by a fallback.

=== Why this is not a grep test ===

Every assertion below drives fast-lane-ship.js through run_workflow_under_e2(), which executes the
script's REAL top-level control flow in a Node.js subprocess and records every agent() dispatch
verbatim, plus the script's own terminal return value. Nothing here inspects the JS source text.
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

from _workflow_engine_harness import (  # noqa: E402
    HarnessResult,
    resolve_connected_reply,
    run_workflow_under_e2,
    shell_step_reply,
    workspace_ensure_from_opened,
)

_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

_AC_ID = "BO-STUB-1"
_BRANCH = f"fast-lane/{_AC_ID}"
_CLAIMED_PATH = "/mnt/c/Users/henzeh/Documents/Scripts/leafcutter/leafcutter-ai"


def _run_lane(label_responses: dict[str, Any]) -> HarnessResult:
    return run_workflow_under_e2(
        _WORKFLOW_PATH,
        label_responses=label_responses,
        args={"ac": _AC_ID},
    )


def _labels_seen(result: HarnessResult) -> list[str | None]:
    return [c.label for c in result.agent_calls]


def _calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def _opened_worktree_payload(worktree_path: str) -> dict[str, Any]:
    """A well-formed, successfully-opened Phase 1 reply — the claim under test."""
    return {
        "outcome": "opened",
        "worktree_path": worktree_path,
        "branch": _BRANCH,
        "created": True,
        "base_commit": "a" * 40,
        "base_matches_origin_main": True,
    }


class _FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.real_worktree_root = Path(self._tmp.name)
        (self.real_worktree_root / "docs" / "acceptance-criteria").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()


_STALE_CLONE_RAW = (
    "worktree /some/other/checkout\n"
    "HEAD deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n"
    "branch refs/heads/main\n"
    "\n"
    "worktree /some/other/checkout/worktrees/unrelated-feature\n"
    "HEAD cafebabecafebabecafebabecafebabecafebabe\n"
    "branch refs/heads/feature/unrelated-work\n"
)


class TestAReplyThatIsAGitListingInsteadOfAnAnswerHalts(_FixtureCase):
    """BO-2400f-3-i, descriptor 1 (angle: failure).

    The workspace step comes back with a worktree LISTING (somewhere without this run's branch) instead of
    the maker's answer. That is not an answer and must not be quietly forgiven: the run halts.
    """

    def test_a_probe_answering_without_the_runs_own_branch_halts(self) -> None:
        # covers: BO-2400f-3-i
        # angle: failure
        result = _run_lane({"workspace-ensure": shell_step_reply(_STALE_CLONE_RAW)})

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertEqual(
            (payload or {}).get("status"),
            "error",
            f"A listing that is not the maker's answer must halt the run. Got: {payload}",
        )
        self.assertFalse(
            _calls_with_label(result, "resolve-connected"),
            f"The run must halt BEFORE Resolve. Labels seen: {_labels_seen(result)}. stderr={result.stderr!r}",
        )


class TestHaltNamesWhatWasReceived(_FixtureCase):
    """BO-2400f-3-i, descriptor 2 (angle: criterion).

    The halt payload quotes what the workspace step returned, so a reader can tell a wrong-repo reply
    from a genuine absence.
    """

    def test_the_halt_names_the_unconfirmed_branch_and_the_claimed_location(self) -> None:
        # covers: BO-2400f-3-i
        # angle: criterion
        result = _run_lane({"workspace-ensure": shell_step_reply(_STALE_CLONE_RAW)})

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        self.assertEqual(payload.get("status"), "error", f"This case must be an actual HALT. Got: {payload}")
        message = str(payload.get("message"))
        self.assertIn("/some/other/checkout", message, f"The halt must quote the received listing. Got: {payload}")
        self.assertIn("refs/heads/main", message, f"Got: {payload}")
        self.assertIn(
            "no other location was used", message.lower(),
            f"The halt must say no other location was substituted. Got: {payload}",
        )


class TestNoLaterPhaseRunsAgainstAClaimedLocation(_FixtureCase):
    """BO-2400f-3-i, descriptor 3 (angle: criterion) -- LOAD-BEARING.

    Asserted on whether ANY dispatch followed the workspace step, not on the returned status: a run can
    report a halt and still have taken the step.
    """

    def test_no_later_phase_runs_against_the_claimed_location(self) -> None:
        # covers: BO-2400f-3-i
        # angle: criterion
        result = _run_lane(
            {
                "workspace-ensure": shell_step_reply(_STALE_CLONE_RAW),
                # If Resolve is (wrongly) reached, give it something so a bug that proceeds does not also
                # crash for an unrelated reason and mask the dispatch assertion below.
                "resolve-connected": resolve_connected_reply([]),
            }
        )

        self.assertEqual(
            _labels_seen(result),
            ["resolve-maker-path", "workspace-ensure"],  # BO-4300a-1-ia: the one maker-path probe precedes the step (consumer_drift)
            f"Nothing may be dispatched after a workspace step that gave no answer. stderr={result.stderr!r}",
        )


class TestAnAcceptedAnswerIsUsedVerbatim(_FixtureCase):
    """BO-2400f-3-i, descriptor 4 (angle: criterion) -- non-regression arm.

    A good answer lets the run proceed on the answer's ``workspace_path`` -- even when another field of the
    same answer names a different path, and even when a stale git listing is scripted for the retired
    probe label (which is never dispatched).
    """

    def test_a_probe_that_lists_the_runs_branch_proceeds_on_gits_path(self) -> None:
        # covers: BO-2400f-3-i
        # angle: criterion
        real_path = str(self.real_worktree_root)
        answer = workspace_ensure_from_opened(
            {"worktree_path": real_path, "branch": _BRANCH, "created": True}
        )
        # The workspace_path is the accepted location; a different legacy field must not outrank it.
        body = json.loads(answer["stdout"])
        body["worktree_path"] = _CLAIMED_PATH
        answer["stdout"] = json.dumps(body)
        result = _run_lane(
            {
                "workspace-ensure": answer,
                "fastlane-worktree-verify": {"worktree_path": "", "raw": _STALE_CLONE_RAW},
                "resolve-connected": resolve_connected_reply([]),
            }
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        self.assertNotIn(
            payload.get("status"),
            ("refused", "error"),
            f"A good workspace answer must never halt the lane. Got: {payload}",
        )
        self.assertNotIn("fastlane-worktree-verify", _labels_seen(result), "the retired probe must not be dispatched")

        resolve_calls = _calls_with_label(result, "resolve-connected")
        self.assertTrue(
            resolve_calls,
            f"An accepted answer must proceed to dispatch the resolver. Labels seen: {_labels_seen(result)}. "
            f"stderr={result.stderr!r}",
        )
        # The prompt is a JSON request; read the command out of it so path separators compare as typed.
        command = json.loads(resolve_calls[0].prompt)["command"]
        self.assertIn(
            real_path,
            command,
            f"The resolver must be dispatched against the answer's workspace_path. Command: {command!r}",
        )
        self.assertNotIn(
            _CLAIMED_PATH,
            command,
            f"The resolver must NOT be dispatched against any other path named in the reply. "
            f"Command: {command!r}",
        )


class TestAnAbsentAnswerIsNotForgiven(_FixtureCase):
    """BO-2400f-3-i, descriptor 5 (angle: boundary).

    No answer of any kind (empty output) used to fall back to the claim. There is no claim and no fallback
    now: the run halts, quoting that no valid answer was received.
    """

    def test_a_probe_that_could_not_run_at_all_still_falls_back(self) -> None:
        # covers: BO-2400f-3-i
        # angle: boundary
        result = _run_lane(
            {
                "workspace-ensure": shell_step_reply(""),
                "resolve-connected": resolve_connected_reply([]),
            }
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        self.assertEqual(payload.get("status"), "error", f"An absent answer must halt, not fall back. Got: {payload}")
        self.assertIn("no valid answer", str(payload.get("message")).lower())
        self.assertEqual(_labels_seen(result), ["resolve-maker-path", "workspace-ensure"], "no fallback location may be used")  # BO-4300a-1-ia probe (consumer_drift)


if __name__ == "__main__":
    unittest.main()
