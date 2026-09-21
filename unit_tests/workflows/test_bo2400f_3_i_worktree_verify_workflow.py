"""
MODULE: unit_tests/workflows/test_bo2400f_3_i_worktree_verify_workflow.py
GOAL: RED behavioural (workflow-level) tests for BO-2400f-3-i — the
      worktree-verification guard in fast-lane-ship.js's Phase 1 (Worktree),
      driven through unit_tests/_workflow_engine_harness.py's
      run_workflow_under_e2(), exactly as
      unit_tests/workflows/test_bo2400f_13_workspace_refusal_workflow.py
      already does for the sibling occupied-workspace refusal path.

=== The defect (BO-2400f-3-i) ===

Today's guard (fast-lane-ship.js, the block immediately after the
"fastlane-worktree-verify" agent() dispatch) treats two different situations
as the same thing:

    const gitReportedPath =
      worktreeVerify && worktreeVerify.worktree_path ? worktreeVerify.worktree_path : "";
    const gitRaw = (worktreeVerify && worktreeVerify.raw) || "";

    if (gitReportedPath && !gitRaw.includes(gitReportedPath)) {
      // HALT — the reported path is not quoted from the raw output.
    }
    const worktreePath = gitReportedPath || claimedWorktreePath;

  - "git said NOTHING at all" (the probe could not be run, or crashed) and
  - "git answered, and its answer is EMPTY OF THIS RUN'S OWN BRANCH" (the
    probe ran, but somewhere with no record for the branch this run just
    created a moment earlier — e.g. a stale second clone of the repo)

both collapse to the same falsy `gitReportedPath`, so both fall back to
`claimedWorktreePath` — trusting the very claim the probe existed to check.
This is exactly the failure observed twice on 2026-09-14: two runs reported
their worktree as a stale clone on the Windows mount and died at Resolve
looking for fast_lane.py there, even though the worktree phase had in fact
created the correct worktree in the right place.

The fix this suite specifies must distinguish the two: an answer that lists
worktrees but omits this run's own branch is POSITIVE evidence the probe
looked somewhere without the branch, and must halt; an absent answer (probe
never ran / crashed) is not evidence of anything and must still fall back,
exactly as today.

=== Why this is not a grep test ===

Every assertion below drives fast-lane-ship.js through run_workflow_under_e2(),
which executes the script's REAL top-level control flow in a Node.js
subprocess (inside a locked-down vm context — see _workflow_engine_harness.py)
and records every agent() dispatch verbatim, plus the script's own terminal
return value. Nothing here inspects the JS source text — see
"Gate / Workflow ACs — Verify Behaviorally, Not by Grep" in this repo's
CLAUDE.md.
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


class TestProbeAnsweringWithoutTheRunsOwnBranchHalts(_FixtureCase):
    """BO-2400f-3-i, descriptor 1 (angle: failure).

    The probe answers — it lists worktrees — but none of them is this run's
    own branch. That is positive evidence the probe looked at a repository
    without this run's branch (e.g. a stale second clone), not silence. The
    run must halt instead of falling back to the claim.
    """

    def test_a_probe_answering_without_the_runs_own_branch_halts(self) -> None:
        # covers: BO-2400f-3-i
        # angle: failure
        stale_clone_raw = (
            "worktree /some/other/checkout\n"
            "HEAD deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /some/other/checkout/worktrees/unrelated-feature\n"
            "HEAD cafebabecafebabecafebabecafebabecafebabe\n"
            "branch refs/heads/feature/unrelated-work\n"
        )
        result = _run_lane(
            {
                "fastlane-worktree": _opened_worktree_payload(_CLAIMED_PATH),
                "fastlane-worktree-verify": {
                    "worktree_path": "",
                    "raw": stale_clone_raw,
                },
            }
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result
        self.assertNotEqual(
            (payload or {}).get("status"),
            "ok",
            f"An answer that lists worktrees but omits this run's own branch "
            f"must not be treated as a silent probe and quietly forgiven — "
            f"the run must halt. Got: {payload}",
        )
        self.assertFalse(
            _calls_with_label(result, "resolve-connected"),
            f"The run must halt BEFORE Resolve when the probe's answer omits "
            f"this run's own branch. Labels seen: {_labels_seen(result)}. "
            f"stderr={result.stderr!r}",
        )


class TestHaltNamesTheUnconfirmedBranchAndTheClaimedLocation(_FixtureCase):
    """BO-2400f-3-i, descriptor 2 (angle: criterion).

    The halt payload must name both the branch that could not be confirmed
    and the location the worktree phase claimed — a halt naming neither
    leaves the reader unable to tell a wrong-repo probe from a genuine
    absence.
    """

    def test_the_halt_names_the_unconfirmed_branch_and_the_claimed_location(
        self,
    ) -> None:
        # covers: BO-2400f-3-i
        # angle: criterion
        stale_clone_raw = (
            "worktree /some/other/checkout\n"
            "HEAD deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n"
            "branch refs/heads/main\n"
        )
        result = _run_lane(
            {
                "fastlane-worktree": _opened_worktree_payload(_CLAIMED_PATH),
                "fastlane-worktree-verify": {
                    "worktree_path": "",
                    "raw": stale_clone_raw,
                },
            }
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        self.assertNotEqual(
            payload.get("status"),
            "ok",
            f"This case must produce an actual HALT, not a successful "
            f"payload that merely happens to echo the branch/path fields as "
            f"part of a normal 'ok' result (that would satisfy the name "
            f"checks below without the run having stopped at all). "
            f"Got: {payload}",
        )
        as_text = str(payload)
        self.assertIn(
            _BRANCH,
            as_text,
            f"The halt payload must name the branch that could not be "
            f"confirmed ({_BRANCH}). Got: {payload}",
        )
        self.assertIn(
            _CLAIMED_PATH,
            as_text,
            f"The halt payload must name the location the worktree phase "
            f"claimed ({_CLAIMED_PATH}), so a reader can tell a wrong-repo "
            f"probe from a genuine absence. Got: {payload}",
        )


class TestNoLaterPhaseRunsAgainstTheClaimedLocation(_FixtureCase):
    """BO-2400f-3-i, descriptor 3 (angle: criterion) — LOAD-BEARING.

    Asserted on whether the Resolve phase was DISPATCHED, not on the
    returned status: a run can report a halt and still have taken the step.
    The observed failure reached Resolve and died there — a status field
    saying "halt" would not have prevented that.
    """

    def test_no_later_phase_runs_against_the_claimed_location(self) -> None:
        # covers: BO-2400f-3-i
        # angle: criterion
        stale_clone_raw = (
            "worktree /some/other/checkout\n"
            "HEAD deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n"
            "branch refs/heads/main\n"
        )
        result = _run_lane(
            {
                "fastlane-worktree": _opened_worktree_payload(_CLAIMED_PATH),
                "fastlane-worktree-verify": {
                    "worktree_path": "",
                    "raw": stale_clone_raw,
                },
                # If Resolve is (wrongly) reached, give it something so a
                # bug that proceeds does not also crash for an unrelated
                # reason and mask the dispatch-count assertion below.
                "resolve-connected": {"ac_ids": [], "message": "0 to build"},
            }
        )

        self.assertFalse(
            _calls_with_label(result, "resolve-connected"),
            f"The resolve phase must NEVER be dispatched against a location "
            f"whose only confirmation came from a probe that omitted this "
            f"run's own branch — proof by absence of the call itself, not by "
            f"the terminal status. Labels seen: {_labels_seen(result)}. "
            f"stderr={result.stderr!r}",
        )


class TestProbeThatListsTheRunsBranchProceedsOnGitsPath(_FixtureCase):
    """BO-2400f-3-i, descriptor 4 (angle: criterion) — non-regression arm.

    A probe answering from the RIGHT repository, listing this run's own
    branch, must let the run proceed using GIT'S reported path — even when
    that differs from the worktree phase's own claim. Fails any fix that
    halts whenever the probe is anything but a byte-for-byte match with the
    claim.
    """

    def test_a_probe_that_lists_the_runs_branch_proceeds_on_gits_path(self) -> None:
        # covers: BO-2400f-3-i
        # angle: criterion
        real_path = str(self.real_worktree_root)
        real_raw = (
            f"worktree {real_path}\n"
            "HEAD 1111111111111111111111111111111111111111\n"
            f"branch refs/heads/{_BRANCH}\n"
        )
        result = _run_lane(
            {
                # The claimed path deliberately differs from git's real
                # answer, so we can prove which one the run actually used.
                "fastlane-worktree": _opened_worktree_payload(_CLAIMED_PATH),
                "fastlane-worktree-verify": {
                    "worktree_path": real_path,
                    "raw": real_raw,
                },
                "resolve-connected": {"ac_ids": [], "message": "0 to build"},
            }
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        self.assertNotIn(
            payload.get("status"),
            ("refused", "error"),
            f"A probe that confirms this run's own branch from the right "
            f"repository must never halt the lane. Got: {payload}",
        )

        resolve_calls = _calls_with_label(result, "resolve-connected")
        self.assertTrue(
            resolve_calls,
            f"An opened workspace confirmed by a correct probe must proceed "
            f"to dispatch the resolver. Labels seen: {_labels_seen(result)}. "
            f"stderr={result.stderr!r}",
        )
        dispatch_text = str(resolve_calls[0].prompt)
        self.assertIn(
            real_path,
            dispatch_text,
            f"The resolver must be dispatched against the location GIT "
            f"reported, not the worktree phase's own claim — git outranks "
            f"the claim wherever it actually answers. Dispatch text: "
            f"{dispatch_text!r}",
        )
        self.assertNotIn(
            _CLAIMED_PATH,
            dispatch_text,
            f"The resolver must NOT be dispatched against the merely-claimed "
            f"location once git has confirmed a different one. Dispatch "
            f"text: {dispatch_text!r}",
        )


class TestProbeThatCouldNotRunAtAllStillFallsBack(_FixtureCase):
    """BO-2400f-3-i, descriptor 5 (angle: boundary) — narrowing arm.

    No answer of any kind (the probe dispatch itself hiccuped/crashed) must
    still fall back to the claim, exactly as today. Fails any fix that
    deletes the fallback wholesale rather than narrowing it, which would
    halt the lane on a single flaky dispatch.
    """

    def test_a_probe_that_could_not_run_at_all_still_falls_back(self) -> None:
        # covers: BO-2400f-3-i
        # angle: boundary
        result = _run_lane(
            {
                "fastlane-worktree": _opened_worktree_payload(_CLAIMED_PATH),
                # Genuinely absent answer: no path, no raw output at all —
                # distinct from "answered but omitted the branch".
                "fastlane-worktree-verify": {"worktree_path": "", "raw": ""},
                "resolve-connected": {"ac_ids": [], "message": "0 to build"},
            }
        )

        self.assertIsNotNone(result.result, f"stderr={result.stderr!r}")
        payload = result.result or {}
        self.assertNotIn(
            payload.get("status"),
            ("refused", "error"),
            f"An unanswered probe (no path, no raw output) is not evidence "
            f"of anything and must not halt the lane. Got: {payload}",
        )

        resolve_calls = _calls_with_label(result, "resolve-connected")
        self.assertTrue(
            resolve_calls,
            f"An unanswered probe must still let the run proceed to Resolve "
            f"on the worktree phase's own claim. Labels seen: "
            f"{_labels_seen(result)}. stderr={result.stderr!r}",
        )
        dispatch_text = str(resolve_calls[0].prompt)
        self.assertIn(
            _CLAIMED_PATH,
            dispatch_text,
            f"With no probe answer at all, the resolver must be dispatched "
            f"against the claimed location — the documented fallback. "
            f"Dispatch text: {dispatch_text!r}",
        )


if __name__ == "__main__":
    unittest.main()
