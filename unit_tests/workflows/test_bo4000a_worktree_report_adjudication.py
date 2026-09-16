"""
MODULE: unit_tests/workflows/test_bo4000a_worktree_report_adjudication.py
GOAL: Behavioral tests for BO-4000a — a worktree step that reports any
    location other than the one it was told stops the run before a single
    phase agent is dispatched.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_0e0872f9-453, 2026-09-14. The
    worktree-setup agent opened a worktree at a location it was never told.
    See BO-4000a.yaml.
ARCHITECTURE: Every test drives templates/workflows-js/build-feature.js's
    own top-level body through unit_tests/_workflow_engine_harness.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
TICKET = "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/07_TICKET-x.md"


def _run(label_responses):
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS, label_responses=label_responses, args={"target": bfx.EPIC_NAME}
    )


def _phase_calls(result):
    """Any dispatch that is not one of the Resolve-Target-phase facts calls."""
    facts_labels = {
        "resolve-target", "worktree-facts-resolved", "worktree-base",
        "worktree-facts-location", "branch-standing", "worktree-setup",
    }
    return [c for c in result.agent_calls if c.label not in facts_labels]


class TestWrongReportedLocationRefusesBeforeAnyPhaseAgent(unittest.TestCase):
    def test_reported_location_other_than_instructed_stops_before_any_phase_agent(self) -> None:
        # covers: BO-4000a
        # angle: failure
        """The worktree-opening agent reporting the incident's nested
        epic-folder path instead of the instructed location stops the run,
        naming both locations, before any phase agent is dispatched.
        """
        result = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], opened_worktree_path=bfx.INCIDENT_NESTED,
        ))
        self.assertEqual(_phase_calls(result), [])
        payload = result.result or {}
        self.assertEqual(payload.get("abort_reason"), "worktree-location-mismatch")
        self.assertIn(bfx.NAMED_LOCATION, payload.get("instructed_location", ""))
        self.assertIn(bfx.INCIDENT_NESTED, payload.get("reported_location", ""))


class TestSameLocationDifferentlySpelledIsAccepted(unittest.TestCase):
    def test_same_location_in_another_spelling_is_accepted(self) -> None:
        # covers: BO-4000a
        # angle: boundary
        """Forward-slash, lower-case, and trailing-separator spellings of the
        instructed location are accepted and the run proceeds.
        """
        for spelling in (
            bfx.NAMED_LOCATION.lower(),
            bfx.NAMED_LOCATION + "/",
            bfx.NAMED_LOCATION.replace("/", "\\"),
        ):
            with self.subTest(spelling=spelling):
                result = _run(bfx.success_label_responses(
                    ticket_paths=[TICKET], opened_worktree_path=spelling,
                ))
                self.assertTrue(_phase_calls(result), f"stderr={result.stderr!r}")


class TestUnreadableResultRefusesDistinguishably(unittest.TestCase):
    def test_unreadable_worktree_result_refuses_distinguishably_from_wrong_location(self) -> None:
        # covers: BO-4000a
        # angle: failure
        """No usable result from the worktree-opening agent stops the run
        with a reason distinguishable from a wrong-location refusal.
        """
        responses = bfx.success_label_responses(ticket_paths=[TICKET])
        responses["worktree-setup"] = {"status": "failed", "error": "boom"}
        result = _run(responses)
        self.assertEqual(_phase_calls(result), [])
        payload = result.result or {}
        self.assertEqual(payload.get("abort_reason"), "worktree-report-unusable")
        self.assertNotEqual(payload.get("abort_reason"), "worktree-location-mismatch")


class TestLaterWorktreePathDoesNotReplaceResolvedWorktree(unittest.TestCase):
    def test_later_worktree_path_in_an_agent_result_does_not_replace_the_resolved_worktree(self) -> None:
        # covers: BO-4000a
        # angle: seam
        """In the reuse case, a stray worktree_path in a LATER agent result
        (here, the epic-planner's own reply) does not change the root of
        subsequent phase prompts.
        """
        responses = bfx.success_label_responses(
            ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE,
            resolved_worktree_facts=bfx.facts(),
        )
        responses["epic-planner"]["worktree_path"] = "/some/other/place"
        result = _run(responses)
        calls = [c for c in result.agent_calls if c.label == "ticket-planner"]
        self.assertTrue(calls, f"stderr={result.stderr!r}")
        self.assertIn(bfx.UXP_WORKTREE, calls[0].prompt or "")
        self.assertNotIn("/some/other/place", calls[0].prompt or "")


class TestReachableFromTopLevelBody(unittest.TestCase):
    def test_worktree_report_adjudication_is_reachable_from_the_workflow_top_level_body(self) -> None:
        # covers: BO-4000a
        # angle: reachability
        """The wrong-location, unreadable-result, and reuse-not-overwritten
        cases are each driven through the harness running build-feature.js's
        own top-level body.
        """
        wrong = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], opened_worktree_path=bfx.INCIDENT_NESTED,
        ))
        self.assertEqual(_phase_calls(wrong), [])

        unreadable_responses = bfx.success_label_responses(ticket_paths=[TICKET])
        unreadable_responses["worktree-setup"] = {"status": "failed"}
        unreadable = _run(unreadable_responses)
        self.assertEqual(_phase_calls(unreadable), [])

        reuse = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE,
            resolved_worktree_facts=bfx.facts(),
        ))
        self.assertTrue(_phase_calls(reuse))


if __name__ == "__main__":
    unittest.main()
