"""
MODULE: unit_tests/workflows/test_bo3900c_unrecognised_path_refusal.py
GOAL: Behavioral tests for BO-3900c — a path whose form is neither
    recognisably absolute nor recognisably relative is refused by name,
    never joined onto the worktree, never repaired, never silently dropped.
BUSINESS CONTEXT: the incident's root shape was a fallback: whatever
    toWorktreePath() did not recognise got joined onto the worktree anyway.
    A fix that recognises Windows absolute paths but keeps that fallback
    still joins the NEXT unforeseen spelling. These tests feed the fallback
    spellings no recognition rule covers.
ARCHITECTURE: Drives templates/workflows-js/build-feature.js's own top-level
    body through unit_tests/_workflow_engine_harness.py. A batch of three
    tickets is used throughout so "only this ticket is blocked" is asserted
    against real siblings, not inferred.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows import _bo3900_fixtures as fx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"

_SIBLING_A = fx.WORKTREE_FWD + "/tickets/00_inbox/01_sibling_a.md"
_SIBLING_B = fx.WORKTREE_FWD + "/tickets/00_inbox/02_sibling_b.md"


def _run_batch(unrecognised_path: str):
    tickets = [_SIBLING_A, unrecognised_path, _SIBLING_B]
    label_responses = fx.base_epic_label_responses(
        epic_path="EPIC-TruthfulProjectRecord",
        worktree_path=fx.WORKTREE_FWD,
        ticket_paths=tickets,
    )
    result = run_workflow_under_e2(
        _BUILD_FEATURE_JS,
        label_responses=label_responses,
        args={"target": "EPIC-TruthfulProjectRecord"},
    )
    planner_prompts = [
        c.prompt or "" for c in result.agent_calls if c.label == "ticket-planner"
    ]
    halted = (result.result or {}).get("halted_tickets") or []
    return result, planner_prompts, halted


class TestUnrecognisedFormsBlockOnlyTheirOwnTicket(unittest.TestCase):
    def test_unrecognised_path_forms_block_only_their_ticket_and_quote_the_value(
        self,
    ) -> None:
        # covers: BO-3900c
        # angle: failure
        """Each of the four unrecognised forms blocks only its own ticket,
        with a reason quoting the value verbatim, while the two well-formed
        siblings are still dispatched to their own ticket-planner agent.
        """
        for unrecognised in (
            fx.DRIVE_RELATIVE,
            fx.ROOTED_NO_DRIVE,
            fx.BLANK_PATH,
            fx.DOUBLE_ROOT,
        ):
            with self.subTest(unrecognised=unrecognised):
                result, planner_prompts, halted = _run_batch(unrecognised)
                # No phase agent dispatched for the unrecognised ticket.
                self.assertFalse(
                    any(unrecognised.strip() and unrecognised in p for p in planner_prompts),
                    f"an agent was dispatched for the unrecognised path: {planner_prompts!r}",
                )
                # The two well-formed siblings ARE dispatched.
                self.assertTrue(
                    any(_SIBLING_A in p for p in planner_prompts),
                    f"sibling A was not dispatched: {planner_prompts!r}",
                )
                self.assertTrue(
                    any(_SIBLING_B in p for p in planner_prompts),
                    f"sibling B was not dispatched: {planner_prompts!r}",
                )
                # The blocked reason quotes the value verbatim.
                matches = [h for h in halted if h.get("ticket_path") == unrecognised]
                self.assertTrue(matches, f"no halted entry for {unrecognised!r}: {halted!r}")
                self.assertIn(unrecognised, matches[0].get("error", ""))


class TestDoubleRootValueIsNeverRepaired(unittest.TestCase):
    def test_already_joined_double_root_path_is_not_rejoined_or_trimmed(self) -> None:
        # covers: BO-3900c
        # angle: boundary
        """The incident's own corrupted value — a path already carrying a
        second drive root — is refused rather than joined a second time or
        cut down to its trailing absolute part.
        """
        result, planner_prompts, halted = _run_batch(fx.DOUBLE_ROOT)
        self.assertFalse(
            any(fx.DOUBLE_ROOT in p for p in planner_prompts),
            f"double-root value was dispatched: {planner_prompts!r}",
        )
        matches = [h for h in halted if h.get("ticket_path") == fx.DOUBLE_ROOT]
        self.assertTrue(matches, halted)
        # Never trimmed down to only the trailing absolute segment.
        self.assertNotIn(
            r"C:\Users\x\07_TICKET-x.md" + " is not a recognised",
            matches[0].get("error", ""),
        )
        self.assertIn(fx.DOUBLE_ROOT, matches[0].get("error", ""))


class TestUnrecognisedFormAndMissingFileAreDistinguishable(unittest.TestCase):
    def test_unrecognised_form_and_missing_file_are_reported_distinguishably(
        self,
    ) -> None:
        # covers: BO-3900c
        # angle: failure
        """A form refusal (this AC) and a well-formed-but-planner-could-not-
        use-it refusal (BO-1900a-4-ii's existing 'ticket-plan-unusable' path)
        carry visibly different stated reasons.
        """
        result, planner_prompts, halted = _run_batch(fx.ROOTED_NO_DRIVE)
        form_refusal = [h for h in halted if h.get("ticket_path") == fx.ROOTED_NO_DRIVE]
        other_refusal = [h for h in halted if h.get("ticket_path") == _SIBLING_A]
        self.assertTrue(form_refusal, halted)
        self.assertTrue(other_refusal, halted)
        self.assertNotEqual(
            form_refusal[0].get("error", ""), other_refusal[0].get("error", "")
        )
        self.assertIn("not a recognised", form_refusal[0].get("error", "").lower())
        self.assertNotIn("not a recognised", other_refusal[0].get("error", "").lower())


class TestRefusalReachableFromTopLevelBody(unittest.TestCase):
    def test_path_form_refusal_is_reachable_from_the_workflow_top_level_body(
        self,
    ) -> None:
        # covers: BO-3900c
        # angle: reachability
        """The refusal is observed in a run of build-feature.js's own body
        through _workflow_engine_harness.py, not inferred from a helper's
        return value.
        """
        result, planner_prompts, halted = _run_batch(fx.DRIVE_RELATIVE)
        self.assertEqual(result.result and result.result.get("status"), "blocked")
        self.assertTrue(
            any(h.get("ticket_path") == fx.DRIVE_RELATIVE for h in halted), halted
        )
        self.assertTrue(planner_prompts, "no ticket-planner call observed at all")


if __name__ == "__main__":
    unittest.main()
