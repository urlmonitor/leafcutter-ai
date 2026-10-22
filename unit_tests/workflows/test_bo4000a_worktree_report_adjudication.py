"""
MODULE: unit_tests/workflows/test_bo4000a_worktree_report_adjudication.py
GOAL: Behavioral tests for BO-4000a -- a worktree step that reports anything other than a usable answer
    stops the run before a single phase agent is dispatched.
BUSINESS CONTEXT: FIELD EVIDENCE -- run wf_0e0872f9-453, 2026-09-14. The worktree-setup agent opened a
    worktree at a location it was never told. See BO-4000a.yaml.
RE-POINTED BY BO-4300c-3 / BO-4300a-1-ia: no agent is told a location any more, so there is no "instructed"
    location to mismatch. The workflow runs the maker's command once and adjudicates the reply: only an ok
    answer naming a workspace_path is accepted, and its path is used exactly as spelled; a reply that is no
    usable answer (a refusal, a failed command, prose, nothing) stops the run, quoting what came back,
    before any phase agent. The two failure modes stay distinguishable by what the stop quotes.
ARCHITECTURE: Every test drives templates/workflows-js/build-feature.js's own top-level body through
    unit_tests/_workflow_engine_harness.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2, shell_step_reply  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
TICKET = "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/07_TICKET-x.md"


def _run(label_responses):
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS, label_responses=label_responses, args={"target": bfx.EPIC_NAME}
    )


def _phase_calls(result):
    """Any dispatch that is not one of the Resolve-Target-phase calls."""
    return [c for c in result.agent_calls if c.label not in bfx.RESOLVE_PHASE_LABELS]


class TestWrongReportedLocationRefusesBeforeAnyPhaseAgent(unittest.TestCase):
    def test_reported_location_other_than_instructed_stops_before_any_phase_agent(self) -> None:
        # covers: BO-4000a
        # angle: failure
        """The workspace step reporting a refusal that names the incident's nested epic-folder path as the
        occupant (the maker declining to place a workspace there) stops the run, quoting what it said, before
        any phase agent is dispatched -- and the nested path is never adopted as the location.
        """
        refusal = bfx.refused_workspace(
            "OCCUPIED", "the location is occupied", occupied_path=bfx.INCIDENT_NESTED,
        )
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=refusal))
        self.assertEqual(_phase_calls(result), [])
        payload = result.result or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertIn("the workspace maker refused", str(payload.get("message")))
        self.assertIn(bfx.INCIDENT_NESTED, str(payload.get("message")), "the reply must be quoted")
        self.assertNotEqual((payload.get("resolved_target") or {}).get("worktree_path"), bfx.INCIDENT_NESTED)


class TestSameLocationDifferentlySpelledIsAccepted(unittest.TestCase):
    def test_same_location_in_another_spelling_is_accepted(self) -> None:
        # covers: BO-4000a
        # angle: boundary
        """Forward-slash, lower-case, backslash and trailing-separator spellings of the location in the
        maker's answer are all accepted and the run proceeds (the answer's spelling is taken as given; there
        is no second spelling to compare it against).
        """
        for spelling in (
            bfx.NAMED_LOCATION.lower(),
            bfx.NAMED_LOCATION + "/",
            bfx.NAMED_LOCATION.replace("/", "\\"),
        ):
            with self.subTest(spelling=spelling):
                result = _run(bfx.success_label_responses(
                    ticket_paths=[TICKET], workspace_reply=bfx.ready_workspace(spelling),
                ))
                self.assertTrue(_phase_calls(result), f"stderr={result.stderr!r}")


class TestUnreadableResultRefusesDistinguishably(unittest.TestCase):
    def test_unreadable_worktree_result_refuses_distinguishably_from_wrong_location(self) -> None:
        # covers: BO-4000a
        # angle: failure
        """No usable result from the workspace step (a failed command, whose stdout is not the maker's
        answer) stops the run with a reason distinguishable from a refusal: it says no valid answer was
        received instead of saying the maker refused.
        """
        unreadable = shell_step_reply({"status": "failed", "error": "boom"}, exit_status=1)
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=unreadable))
        self.assertEqual(_phase_calls(result), [])
        payload = result.result or {}
        self.assertEqual(payload.get("status"), "error")
        message = str(payload.get("message"))
        self.assertIn("no valid answer was received", message)
        self.assertNotIn("the workspace maker refused", message)

        refused = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], workspace_reply=bfx.refused_workspace("OCCUPIED", "occupied"),
        ))
        self.assertNotEqual(message, str((refused.result or {}).get("message")))


class TestLaterWorktreePathDoesNotReplaceResolvedWorktree(unittest.TestCase):
    def test_later_worktree_path_in_an_agent_result_does_not_replace_the_resolved_worktree(self) -> None:
        # covers: BO-4000a
        # angle: seam
        """In the reuse case, a stray worktree_path in a LATER agent result (here, the epic-planner's own
        reply) does not change the root of subsequent phase prompts.
        """
        responses = bfx.success_label_responses(
            ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE,
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
        """The refused, unreadable-result, and reuse-not-overwritten cases are each driven through the
        harness running build-feature.js's own top-level body.
        """
        refused = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], workspace_reply=bfx.refused_workspace("OCCUPIED", "occupied"),
        ))
        self.assertEqual(_phase_calls(refused), [])

        unreadable = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], workspace_reply=shell_step_reply({"status": "failed"}, exit_status=1),
        ))
        self.assertEqual(_phase_calls(unreadable), [])

        reuse = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE,
        ))
        self.assertTrue(_phase_calls(reuse))


if __name__ == "__main__":
    unittest.main()
