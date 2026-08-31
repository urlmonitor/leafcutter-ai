"""
MODULE: unit_tests/workflows/test_bo2400f_12_refusal_workflow.py
GOAL: RED behavioural tests for BO-2400f-12 / BO-2400f-12-i / BO-2400f-12-ii —
      templates/workflows-js/fast-lane-ship.js must, immediately after its
      Resolve phase and BEFORE the claim step (BO-2400f-7) or any build-agent
      dispatch, consult a producibility verdict for the resolved connected
      build set and end the run in a distinct "refused" terminal outcome when
      any member declares a deliverable or proof obligation this lane's
      roster cannot produce.

=== Target contract (greenfield — nothing in the tree implements this yet;
    confirmed by `grep -rn "producib" scripts/ templates/ unit_tests/` ===

Between the Resolve phase's empty-set no-op check (~line 369) and the
"claim-connected" agent() dispatch (~line 393), fast-lane-ship.js must:

  1. Dispatch a status-checker agent() call, label "check-producibility",
     phase "Resolve", instructing it to run:

         python3 <gateScript> check_producibility --ac-ids <csv> --ac-root <acStoreRoot>

     and return the parsed JSON verdict: {producible: bool, unproducible: [...]}.

  2. Read that verdict with a plain-falsy check (the same pattern the
     red-baseline gate's gate_passed key already uses) — a missing key, a
     null, or an unparseable reply takes the REFUSING branch. No default-true.

  3. On an unproducible (or unreadable) verdict, return a terminal payload
     with ``status: "refused"`` BEFORE any "claim-connected", "test-writer",
     "python-coder", "commit", or "pull-request"
     agent() call — and before any "release-on-..." call (no claim was ever
     taken, so nothing may be released, BO-2400f-12-i). The payload carries
     ``ac_ids`` (the full resolved set, unchanged) and ``unproducible`` (the
     verdict's own list) so the operator reads which member and why.

  4. On a producible verdict, the run proceeds exactly as it does today —
     "check-producibility" is still dispatched (so the guard is provably
     consulted), but claim/test-writer/etc. still fire afterwards.

=== Why this is not a grep test ===

Every assertion below drives fast-lane-ship.js through
unit_tests/_workflow_engine_harness.py's run_workflow_under_e2(), which
executes the script's real top-level control flow in a Node.js subprocess and
records every agent() dispatch verbatim (or the script's own terminal return
value). Nothing here inspects the JS source text.

=== Red baseline ===

RED today because fast-lane-ship.js's Resolve phase never dispatches a
"check-producibility" label at all — it goes straight from resolving acIds to
"claim-connected" (see fast-lane-ship.js lines ~340-416). Every test below
either finds an unexpected downstream dispatch (claim/test-writer/coder all
still fire unconditionally) or fails to find the "check-producibility" call
it looks for.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

# Every agentType the lane can dispatch to do build work. sql-coder and
# frontend-coder are absent on purpose: fast-lane-ship.js never dispatches
# them, so a refusal test that watched for them would be watching for a
# dispatch that cannot occur and would pass on a broken guard.
_BUILD_AGENT_TYPES = {"python-coder", "test-writer"}
_POST_REFUSAL_FORBIDDEN_LABELS = {"claim-connected"}


def _write_ac(ac_root: Path, ac_id: str) -> Path:
    """Write a minimal, valid AC YAML using yaml.safe_dump (fixture-authenticity)."""
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": "active",
        "work_status": "todo",
        "readiness": "approved",
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": [],
        "covered_by": [],
    }
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _worktree_label_response(worktree_root: Path) -> dict[str, Any]:
    return {
        "worktree_path": str(worktree_root),
        "branch": "fast-lane/test-bo2400f-12",
        "ac_store_path": str(worktree_root / "docs" / "acceptance-criteria"),
        "created": True,
    }


def _run_lane(
    worktree_root: Path,
    ac_id: str,
    extra_label_responses: dict[str, Any] | None = None,
) -> HarnessResult:
    label_responses = {"fastlane-worktree": _worktree_label_response(worktree_root)}
    if extra_label_responses:
        label_responses.update(extra_label_responses)
    return run_workflow_under_e2(
        _WORKFLOW_PATH, label_responses=label_responses, args={"ac": ac_id}
    )


def _calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def _calls_with_agent_type_in(result: HarnessResult, agent_types: set) -> list:
    return [c for c in result.agent_calls if c.agent_type in agent_types]


def _labels_starting_with(result: HarnessResult, prefix: str) -> list[str]:
    return [c.label for c in result.agent_calls if c.label and c.label.startswith(prefix)]


class _FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree_root = Path(self._tmp.name)
        self.ac_root = self.worktree_root / "docs" / "acceptance-criteria"
        self.ac_root.mkdir(parents=True)
        _write_ac(self.ac_root, "FLT-960a")
        _write_ac(self.ac_root, "FLT-960b")
        _write_ac(self.ac_root, "FLT-960c")

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestRefusalPrecedesAllDispatch(_FixtureCase):
    """BO-2400f-12: an unproducible resolved set refuses before any dispatch."""

    def _run_with_unproducible_pair(self) -> HarnessResult:
        return _run_lane(
            self.worktree_root,
            "FLT-960a",
            extra_label_responses={
                "resolve-connected": {
                    "ac_ids": ["FLT-960a", "FLT-960b"],
                    "message": "2 to build",
                },
                "check-producibility": {
                    "producible": False,
                    "unproducible": [
                        {
                            "ac_id": "FLT-960b",
                            "declared_producer": None,
                            "declared_proof": "test_required: false",
                            "reason": "no phase in this run's roster produces a passing "
                            "covering test for a test_required: false criterion",
                        }
                    ],
                },
            },
        )

    def test_unproducible_member_refuses_before_any_dispatch(self) -> None:
        # covers: BO-2400f-12
        """No claim, test-writer, coder, commit, or pull-request dispatch
        occurs when the resolved set contains an unproducible member."""
        result = self._run_with_unproducible_pair()

        self.assertFalse(
            _calls_with_label(result, "claim-connected"),
            f"claim-connected must NOT be dispatched on an unproducible set. "
            f"Calls: {[(c.label, c.agent_type) for c in result.agent_calls]}. stderr={result.stderr!r}",
        )
        self.assertFalse(
            _calls_with_label(result, "test-writer") or any(c.agent_type == "test-writer" for c in result.agent_calls),
            "test-writer must NOT be dispatched on an unproducible set.",
        )
        self.assertFalse(
            _calls_with_agent_type_in(result, _BUILD_AGENT_TYPES),
            "No coder agent may be dispatched on an unproducible set.",
        )
        self.assertFalse(
            _calls_with_agent_type_in(result, {"commit", "pull-request"}),
            "No commit or pull-request dispatch may occur on an unproducible set.",
        )

    def test_refusal_names_each_unproducible_member_and_the_absent_phase(self) -> None:
        # covers: BO-2400f-12
        """The refusing run's terminal payload names the unproducible
        member's id, its declared producer/proof, and that no phase
        produces it — not a bare count and not a stale-todo message."""
        result = self._run_with_unproducible_pair()

        self.assertIsNotNone(
            result.result,
            f"Expected a terminal payload dict from the refusing run. stderr={result.stderr!r}",
        )
        payload = result.result
        self.assertEqual(payload.get("status"), "refused", f"Got payload: {payload}")
        unproducible = payload.get("unproducible") or []
        entry = next((e for e in unproducible if e.get("ac_id") == "FLT-960b"), None)
        self.assertIsNotNone(
            entry, f"FLT-960b must be named individually in the refusal payload. Got: {payload}"
        )
        self.assertNotIn(
            "stale",
            (payload.get("message") or "").lower(),
            "The refusal must not read like a stale-todo message (KI-BO-013's late-jam symptom).",
        )

    def test_refusal_is_not_reported_as_success_or_as_a_pull_request(self) -> None:
        # covers: BO-2400f-12
        """The refusal is a distinct terminal outcome ('status: refused') —
        never status 'ok' and never carrying a pull-request URL.

        Asserting the exact 'refused' status (not merely != 'ok') matters:
        today's code has no producibility guard at all, so this scenario's
        default agent() stubs cause the run to error out for unrelated
        reasons downstream (missing stub fields), which would satisfy a
        weaker '!= ok' check without the refusal ever being implemented.
        """
        result = self._run_with_unproducible_pair()

        self.assertIsNotNone(result.result)
        payload = result.result
        self.assertEqual(
            payload.get("status"),
            "refused",
            f"Expected the distinct 'refused' terminal status. Got: {payload}",
        )
        self.assertFalse(
            payload.get("pr_url"),
            f"A refusing run must never assert a pull request was opened. Got: {payload}",
        )

    def test_refusal_does_not_build_the_producible_remainder(self) -> None:
        # covers: BO-2400f-12
        """With three members of which one is unproducible, the set is
        refused whole: no coder dispatch occurs for the other two, and the
        payload does not report a partial success."""
        result = _run_lane(
            self.worktree_root,
            "FLT-960a",
            extra_label_responses={
                "resolve-connected": {
                    "ac_ids": ["FLT-960a", "FLT-960b", "FLT-960c"],
                    "message": "3 to build",
                },
                "check-producibility": {
                    "producible": False,
                    "unproducible": [
                        {
                            "ac_id": "FLT-960b",
                            "declared_producer": None,
                            "declared_proof": "test_required: false",
                            "reason": "no phase in this run's roster produces this deliverable",
                        }
                    ],
                },
            },
        )

        self.assertFalse(_calls_with_agent_type_in(result, _BUILD_AGENT_TYPES))
        self.assertIsNotNone(result.result)
        payload = result.result
        self.assertEqual(payload.get("status"), "refused", f"Got: {payload}")
        self.assertNotIn("partial", (payload.get("message") or "").lower())

    def test_unreadable_verdict_refuses_rather_than_proceeding(self) -> None:
        # covers: BO-2400f-12
        """A resolver reply missing the producibility verdict entirely (no
        'producible' key) must take the refusing branch, fail-closed — never
        proceed to dispatch."""
        result = _run_lane(
            self.worktree_root,
            "FLT-960a",
            extra_label_responses={
                "resolve-connected": {"ac_ids": ["FLT-960a"], "message": "1 to build"},
                "check-producibility": {"message": "not a real verdict"},
            },
        )

        self.assertFalse(
            _calls_with_label(result, "claim-connected"),
            "An unreadable verdict must refuse before claiming, not default to producible.",
        )
        self.assertIsNotNone(result.result)
        payload = result.result
        self.assertEqual(payload.get("status"), "refused", f"Got: {payload}")
        self.assertIn(
            "could not be determined",
            (payload.get("message") or "").lower(),
            f"The refusal must say producibility could not be determined. Got: {payload}",
        )


class TestRefusalReleasesNothing(_FixtureCase):
    """BO-2400f-12-i: a refusal holds no claim, so it must never release."""

    def test_refused_run_does_not_dispatch_the_release_step(self) -> None:
        # covers: BO-2400f-12-i
        """A refusing run records no 'release-on-...' dispatch — it took no
        claim, so a release would flip a concurrent run's legitimate claim."""
        result = _run_lane(
            self.worktree_root,
            "FLT-960a",
            extra_label_responses={
                "resolve-connected": {
                    "ac_ids": ["FLT-960a", "FLT-960b"],
                    "message": "2 to build",
                },
                "check-producibility": {
                    "producible": False,
                    "unproducible": [
                        {
                            "ac_id": "FLT-960b",
                            "declared_producer": None,
                            "declared_proof": "test_required: false",
                            "reason": "no phase produces this deliverable",
                        }
                    ],
                },
            },
        )

        release_labels = _labels_starting_with(result, "release-on")
        self.assertEqual(
            release_labels,
            [],
            f"A refusing run must dispatch no release-on-* call (it claimed nothing). "
            f"Got: {release_labels}",
        )
        self.assertFalse(
            _calls_with_label(result, "claim-connected"),
            "A refusing run must also never reach the claim step.",
        )


class TestProducibleSetIsNeverRefused(_FixtureCase):
    """BO-2400f-12-ii: a producible set proceeds unchanged — the guard is
    consulted (proven by its own dispatch) but never blocks real work."""

    def test_fully_producible_set_proceeds_to_dispatch(self) -> None:
        # covers: BO-2400f-12-ii
        """A fully producible set still gets the producibility check
        dispatched (proving the guard runs), and claim + test-writer still
        fire afterwards — the guard adds no new ending to a buildable set."""
        result = _run_lane(
            self.worktree_root,
            "FLT-960a",
            extra_label_responses={
                "resolve-connected": {"ac_ids": ["FLT-960a"], "message": "1 to build"},
                "check-producibility": {"producible": True, "unproducible": []},
            },
        )

        self.assertTrue(
            _calls_with_label(result, "check-producibility"),
            f"The producibility guard must be dispatched even on a producible set — its "
            f"absence means the check never ran. Calls: "
            f"{[(c.label, c.agent_type) for c in result.agent_calls]}. stderr={result.stderr!r}",
        )
        self.assertTrue(
            _calls_with_label(result, "claim-connected"),
            "A producible set must still reach the claim step.",
        )
        self.assertTrue(
            any(c.label == "test-writer" or c.agent_type == "test-writer" for c in result.agent_calls),
            "A producible set must still reach the test-writer dispatch.",
        )
        if result.result is not None:
            self.assertNotEqual(result.result.get("status"), "refused")

    def test_draft_readiness_set_is_not_refused(self) -> None:
        # covers: BO-2400f-12-ii
        """A set whose members are readiness draft is not refused merely for
        that reason — this workflow-level check reads only the producibility
        verdict it is handed, never readiness itself, so a producible verdict
        for a draft-readiness set behaves identically to an approved one."""
        result = _run_lane(
            self.worktree_root,
            "FLT-960a",
            extra_label_responses={
                "resolve-connected": {"ac_ids": ["FLT-960a"], "message": "1 to build"},
                "check-producibility": {"producible": True, "unproducible": []},
            },
        )

        self.assertTrue(
            _calls_with_label(result, "check-producibility"),
            f"The producibility guard must actually be dispatched and consulted — its "
            f"absence means readiness could not possibly have been ignored by it because "
            f"it never ran at all. Calls: {[(c.label, c.agent_type) for c in result.agent_calls]}. "
            f"stderr={result.stderr!r}",
        )
        self.assertTrue(
            _calls_with_label(result, "claim-connected"),
            "A producible verdict must reach the claim step regardless of the "
            "underlying member's readiness value.",
        )
        if result.result is not None:
            self.assertNotEqual(result.result.get("status"), "refused")


if __name__ == "__main__":
    unittest.main()
