"""
MODULE: unit_tests/workflows/test_bo3900b_containment_boundaries.py
GOAL: Behavioral tests for BO-3900b — a path counts as inside the worktree
    only at a whole-segment boundary, with Windows letter case and trailing
    separators ignored and POSIX case respected.
BUSINESS CONTEXT: the cheapest fix for BO-3900's incident swaps "/" for
    either separator in a prefix check, dropping the segment boundary; the
    next cheapest lower-cases everything, breaking POSIX. Both pass BO-3900's
    own cases (whose worktree and ticket share a real segment boundary and a
    single letter case), so these boundaries need their own inputs.
ARCHITECTURE: Drives templates/workflows-js/build-feature.js's own top-level
    body through unit_tests/_workflow_engine_harness.py, asserting on the
    path actually embedded in the captured 'ticket-planner' agent prompt.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows import _bo3900_fixtures as fx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"


def _drive_root_count(text: str) -> int:
    """How many drive-lettered roots ("X:\\" or "X:/") occur in `text`."""
    return len(re.findall(r"[A-Za-z]:[\\/]", text))


def _ticket_planner_prompt(worktree: str, ticket_path: str) -> str:
    label_responses = fx.base_epic_label_responses(
        epic_path="EPIC-TruthfulProjectRecord",
        worktree_path=worktree,
        ticket_paths=[ticket_path],
    )
    result = run_workflow_under_e2(
        _BUILD_FEATURE_JS,
        label_responses=label_responses,
        args={"target": "EPIC-TruthfulProjectRecord"},
    )
    calls = [c for c in result.agent_calls if c.label == "ticket-planner"]
    assert calls, f"no ticket-planner call captured; stderr={result.stderr!r}"
    return calls[0].prompt or ""


class TestSiblingDirectorySharingNamePrefix(unittest.TestCase):
    def test_sibling_directory_sharing_a_name_prefix_is_not_inside_the_worktree(
        self,
    ) -> None:
        # covers: BO-3900b
        # angle: boundary
        """C:\\wt\\foo-bar\\... is judged outside worktree C:\\wt\\foo: it
        reaches the phase agent naming that same sibling path, never rewritten
        as though "foo-bar" were a subdirectory of "foo".
        """
        prompt = _ticket_planner_prompt(fx.SIBLING_WORKTREE, fx.SIBLING_TICKET_OUTSIDE)
        self.assertIn("foo-bar", prompt)
        self.assertIn("07_TICKET-x.md", prompt)
        # An absolute input is never joined onto anything — one drive root,
        # not the worktree's own root prefixed onto the sibling's.
        self.assertLessEqual(_drive_root_count(prompt), 1, prompt)


class TestWorktreeSpellingVariantsAgreeOnTheSameTicket(unittest.TestCase):
    def test_windows_worktree_spelling_variants_contain_the_same_ticket(self) -> None:
        # covers: BO-3900b
        # angle: boundary
        """Trailing-separator, backslash, and different-case spellings of one
        Windows worktree all contain the same ticket path and dispatch it as
        ONE identical path in all three cases.
        """
        prompts = [
            _ticket_planner_prompt(worktree, fx.SIBLING_TICKET_INSIDE)
            for worktree in (
                fx.CASE_WORKTREE_TRAILING,
                fx.CASE_WORKTREE_BACKSLASH,
                fx.CASE_WORKTREE_DIFFERENT_CASE,
            )
        ]
        # All three dispatch the identical path string.
        self.assertEqual(len(set(prompts)), 1, f"dispatched paths differ: {prompts!r}")


class TestPosixContainmentIsCaseSensitive(unittest.TestCase):
    def test_posix_containment_is_case_sensitive(self) -> None:
        # covers: BO-3900b
        # angle: boundary
        """A POSIX path differing from the worktree only by letter case is
        judged OUTSIDE it: it reaches the phase agent unchanged, never
        lower-cased or rewritten to match the worktree's own case.
        """
        prompt = _ticket_planner_prompt(
            fx.POSIX_CASE_WORKTREE, fx.POSIX_CASE_TICKET_DIFFERENT_CASE
        )
        self.assertIn(fx.POSIX_CASE_TICKET_DIFFERENT_CASE, prompt)


class TestWorktreeRootItselfIsNotJoined(unittest.TestCase):
    def test_worktree_root_itself_is_not_joined(self) -> None:
        # covers: BO-3900b
        # angle: boundary
        """A path equal to the worktree root, with or without a trailing
        separator, is recognised as the root and never joined onto itself.
        """
        for root_spelling in (fx.CASE_WORKTREE_BACKSLASH, fx.CASE_WORKTREE_TRAILING):
            prompt = _ticket_planner_prompt(fx.CASE_WORKTREE_BACKSLASH, root_spelling)
            # A doubled root (the root joined onto itself) never appears: one
            # drive root only, and "wt" (the root's own distinguishing
            # segment) occurs exactly once.
            self.assertLessEqual(_drive_root_count(prompt), 1, prompt)
            self.assertLessEqual(prompt.lower().count("wt"), 1, prompt)


class TestDotDotSegmentsAppliedBeforeContainment(unittest.TestCase):
    def test_dot_dot_segments_are_applied_before_containment(self) -> None:
        # covers: BO-3900b
        # angle: failure
        """A path that escapes the worktree through .. segments dispatches
        naming the ESCAPED location (never silently corrected back inside),
        and one that uses a harmless . segment dispatches naming the location
        the . resolves to, inside the worktree.
        """
        escaped_prompt = _ticket_planner_prompt(fx.SIBLING_WORKTREE, fx.DOTDOT_ESCAPES)
        self.assertIn("other", escaped_prompt)
        self.assertNotIn("tickets", escaped_prompt.split("other")[-1])

        inside_prompt = _ticket_planner_prompt(fx.SIBLING_WORKTREE, fx.DOTDOT_STAYS_INSIDE)
        dispatched_path = inside_prompt.split('Read the ticket at "')[1].split('"')[0]
        self.assertEqual(dispatched_path, "C:/wt/foo/tickets/07_TICKET-x.md")


class TestContainmentBoundariesReachableFromTopLevelBody(unittest.TestCase):
    def test_containment_boundaries_are_reachable_from_the_workflow_top_level_body(
        self,
    ) -> None:
        # covers: BO-3900b
        # angle: reachability
        """At least the prefix-sibling and case-variant cases are driven
        through _workflow_engine_harness.py running build-feature.js's own
        body — the same run this whole file already performs, restated here
        as its own named entry per BO-3900b's test_spec.
        """
        sibling_prompt = _ticket_planner_prompt(
            fx.SIBLING_WORKTREE, fx.SIBLING_TICKET_OUTSIDE
        )
        self.assertIn("foo-bar", sibling_prompt)

        case_prompts = [
            _ticket_planner_prompt(worktree, fx.SIBLING_TICKET_INSIDE)
            for worktree in (fx.CASE_WORKTREE_TRAILING, fx.CASE_WORKTREE_DIFFERENT_CASE)
        ]
        self.assertEqual(len(set(case_prompts)), 1, case_prompts)


if __name__ == "__main__":
    unittest.main()
