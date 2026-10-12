"""
Tests for TQ-600a-13-xiv, review-fix half -- the pull request comment carries the restore line for every held state,
the age is shown to one decimal, a run with no start time names its run, and the red action survives the output split.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiv.yaml

======================================================================
CONTRACT UNDER TEST (already in production; these tests were written after the fixes, so each one is shown red
against a temporary revert of the matching fix -- see the sign-off report)

M-2  ``scripts.ci._hold_comment.render_comment`` adds "To restore a verdict: `<action>`." to every held body, the action
     being ``scripts.ci._hold_wording.RESTORE_ACTIONS[state]``, inside a code span (the red action carries a ``<notice>``
     placeholder, and a bare ``<`` would stop ``_is_rendered_held`` recognising the body, so a lift would lose it).
     ``HELD_HEADLINES`` values are unchanged: published comments are recognised by them.
L-1  the stale reason shows the age to one decimal ("30.4 h ago, limit 30 h").
L-2  a green run with no usable ``run_started_at`` is could_not_read and its reason carries the run URL.
L-5  the red action is "fix main ... (Fixes #<notice>)"; splitting a reason at "To restore a verdict" isolates it.
======================================================================
"""

from __future__ import annotations

from ._ending_harness import CHECK, Cases
from ._hold_harness import DNC_JOBS, NOW, RED_JOBS, make_run, tunables
from ._notice_fakes import import_production
from ._xiv_support import RESTORE, XivTestCase

HEAD = "9" * 40
EXPECTED_HEADLINES = {  # the values published comments are recognised by: pinned here, never edited with the wording
    "red": "This pull request is held: the post-merge suite on main is red.",
    "did_not_complete": "This pull request is held: the latest post-merge suite run on main did not complete.",
    "stale": "This pull request is held: the post-merge suite has no fresh verdict.",
    "disabled": "This pull request is held: the post-merge suite workflow is not active.",
    "never_run": "This pull request is held: the post-merge suite has never run on main.",
    "could_not_read": "This pull request is held: the post-merge suite status could not be read.",
}


class TestTq600a13xivReview(XivTestCase):
    def _six(self):
        """The six held verdicts, each produced by the real evaluation."""
        red, dnc = make_run(7, "failure"), make_run(8, "cancelled")
        return {
            "red": self.verdict([red], jobs={red["id"]: RED_JOBS}),
            "did_not_complete": self.verdict([dnc], jobs={dnc["id"]: DNC_JOBS}),
            "stale": self.verdict([make_run(7, "success", hours_ago=31)]),
            "disabled": self.verdict([make_run(7, "success")], workflow_state="disabled_manually"),
            "never_run": self.verdict([]),
            "could_not_read": self.verdict([make_run(7, "success")], failing=["/runs"]),
        }

    def test_tq600a_13_xiv_every_held_comment_says_how_to_restore_a_verdict(self):
        # covers: TQ-600a-13-xiv
        # angle: seam
        """Each of the six held verdicts, produced by the real evaluation and rendered by the real comment renderer,
        carries "To restore a verdict:" and the action of ``RESTORE_ACTIONS[state]``; the headlines are the pinned
        ones; and a held body still folds into the lifted comment that follows it (its restore line is still there
        and the body was not replaced by the edited-body summary), which proves the code span keeps it recognised.

        Wrong versions caught: a state without a restore line; the red action outside a code span (its `<notice>`
        makes the body unrecognisable, so the lift drops the details); a changed headline.
        """
        comment = import_production("scripts.ci._hold_comment")
        wording = import_production("scripts.ci._hold_wording")
        passing = self.verdict([make_run(7, "success", hours_ago=1)])
        cases = Cases()
        with cases.case("the headlines are unchanged"):
            CHECK.assertEqual(EXPECTED_HEADLINES, dict(comment.HELD_HEADLINES))
        for state, verdict in self._six().items():
            with cases.case(f"{state} comment"):
                body = comment.render_comment(verdict, NOW, None, head_sha=HEAD)
                CHECK.assertEqual(state, verdict["state"])
                CHECK.assertIn("To restore a verdict:", body)
                CHECK.assertIn(wording.RESTORE_ACTIONS[state], body)
                CHECK.assertTrue(comment._is_rendered_held(body), "the body must stay recognisable as this check's own")  # noqa: SLF001
            with cases.case(f"{state} comment folds on a lift"):
                lifted = comment.render_comment(passing, NOW, comment.render_comment(verdict, NOW, None, head_sha=HEAD), head_sha=HEAD)
                CHECK.assertIn(wording.RESTORE_ACTIONS[state], lifted, "the held details must be folded into the lifted comment")
                CHECK.assertNotIn(comment.EDITED_SUMMARY, lifted)
        cases.check()

    def test_tq600a_13_xiv_the_red_action_is_isolated_by_the_restore_split(self):
        # covers: TQ-600a-13-xiv
        # angle: boundary
        """The red reason's action contains parentheses and a `#`; splitting at "To restore a verdict" leaves exactly
        that action as the tail, and it names both ways (fix main, declare the fix with `Fixes #<notice>`).

        Wrong version caught: a red action reduced to a bare "fix main" (the declared-fix route lost).
        """
        red = make_run(7, "failure")
        reason = self.verdict([red], jobs={red["id"]: RED_JOBS})["reason"]
        tail = RESTORE.split(reason, maxsplit=1)[-1]
        CHECK.assertEqual(2, len(RESTORE.split(reason)), "one restore sentence, no more")
        CHECK.assertRegex(tail, r"^: fix main so the suite is green again")
        CHECK.assertIn("(Fixes #<notice>)", tail)

    def test_tq600a_13_xiv_age_is_shown_to_one_decimal(self):
        # covers: TQ-600a-13-xiv
        # angle: boundary
        """A green run 30.4 h old against the committed 30 h bound is stale and the reason reads "30.4 h ago, limit 30
        h" -- never "30 h ago", which would look equal to the limit it exceeds.

        Wrong version caught: the age rounded to whole hours (`:.0f`).
        """
        bound = tunables()["staleness_hours"]
        verdict = self.verdict([make_run(7, "success", hours_ago=bound + 0.4)])
        CHECK.assertEqual("stale", verdict["state"])
        CHECK.assertIn(f"{bound + 0.4:.1f} h ago", verdict["reason"])
        CHECK.assertNotIn(f"({bound} h ago", verdict["reason"])

    def test_tq600a_13_xiv_a_run_without_a_start_time_is_named_in_the_reason(self):
        # covers: TQ-600a-13-xiv
        # angle: failure
        """A green run with no `run_started_at` is could_not_read, never a pass, and the reason carries that run's URL.

        Wrong version caught: the reason reduced to a generic sentence that does not say which run lacks the time.
        """
        run = make_run(7, "success", hours_ago=1)
        del run["run_started_at"]
        verdict = self.verdict([run])
        CHECK.assertEqual("could_not_read", verdict["state"])
        CHECK.assertIn(run["html_url"], verdict["reason"])
