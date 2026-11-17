"""
Tests for TQ-600a-13-xiv -- the hold fails, and says which, when the post-merge verdict is stale, the workflow is
disabled, or no run has ever completed.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiv.yaml
(the cost / discrimination half is test_tq_600a_13_xiv_cost.py; the tunables guard is test_tq_600a_13_xiv_tunables.py)

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

scripts/ci/post_merge_hold.py  evaluate(client, repo, *, now=...) -> dict   (EXISTS since -vi; only WORDING is new)
  state is unchanged: pass | red | did_not_complete | stale | disabled | never_run | could_not_read. -xiv adds the
  ``reason`` wording, which the check prints (and ``main`` prints) -- asserted here on ``verdict["reason"]``:
    HEADLINE     the text of ``reason`` before its first ":", "(", "." or ";" (URLs removed). The six headlines (red, did_not_complete,
                 stale, disabled, never_run, could_not_read) must be pairwise different and non-empty.
    NOT THE PR   every one of the six says "not caused by this pull request" (or "the pull request"), case-insensitive.
    RESTORE      every one of the six contains the phrase "to restore a verdict" followed by how; for the three
                 states this AC owns the how is named: stale -> "dispatch" the correctness workflow; disabled ->
                 "re-enable" it; never_run -> wait for "the first run" (or "dispatch" it).
    disabled     the reason contains the word "disabled" and the reported state verbatim (e.g. disabled_manually).
    never_run    the reason says "no post-merge run has ever completed" and "no verdict".
    stale        the reason says "stale", gives the run's ``run_started_at`` text and its age (e.g. "31 h").
    no settled   ``stale`` with "no settled run among the most recent <run_history_page>" (30 from the tunables).
  Unchanged from -ix: could_not_read still begins "Post-merge run history could not be read".
======================================================================
"""

from __future__ import annotations

import re

from ._ending_harness import CHECK, Cases
from ._hold_harness import DNC_JOBS, RED_JOBS, make_run, tunables
from ._xiv_support import NOT_THE_PR, RESTORE, RESTORE_HOW, XivTestCase, headline

DISABLED_STATES = ("disabled_inactivity", "disabled_manually", "deleted", "disabled_fork")


class TestTq600a13xivStates(XivTestCase):
    def _six(self):
        """The six held verdicts, each from its own double: red, did-not-complete, stale, disabled, never-run, could-not-read."""
        red, dnc = make_run(7, "failure"), make_run(8, "cancelled")
        return {
            "red": self.verdict([red], jobs={red["id"]: RED_JOBS}),
            "did_not_complete": self.verdict([dnc], jobs={dnc["id"]: DNC_JOBS}),
            "stale": self.verdict([make_run(7, "success", hours_ago=31)]),
            "disabled": self.verdict([make_run(7, "success", hours_ago=1)], workflow_state="disabled_manually"),
            "never_run": self.verdict([]),
            "could_not_read": self.verdict([make_run(7, "success")], failing=["/runs"]),
        }

    def test_tq600a_13_xiv_no_fresh_verdict_states_fail_distinctly(self):
        # covers: TQ-600a-13-xiv
        # angle: criterion
        """Every workflow state other than active is disabled, naming the state, whatever the runs say; an active
        workflow with no runs is never_run; a green run 31 h old is stale and 29 h old passes; thirty runs none
        settled is stale with the no-settled reason; six distinct headlines each say the cause is not the pull
        request's change and how to restore a verdict.

        Wrong versions caught: disabled folded into stale (or never_run); a stale green run passing; a fresh green run
        on an active workflow failing (fail on everything); two states sharing one headline; a state that omits the
        not-the-PR sentence or the way to restore a verdict.
        """
        cases = Cases()
        for state in DISABLED_STATES:
            for label, runs in (("a fresh green run", [make_run(7, "success", hours_ago=1)]), ("a red run", [make_run(7, "failure")]), ("no runs", [])):
                with cases.case(f"workflow {state} with {label}"):
                    verdict = self.verdict(runs, workflow_state=state)
                    CHECK.assertEqual(("disabled", state), (verdict["state"], verdict["workflow_state"]))
                    CHECK.assertIn("disabled", verdict["reason"].replace(state, "").lower(), "the word, apart from the state's own name")
                    CHECK.assertIn(state, verdict["reason"], "the output must name the state the workflow reported")
        with cases.case("active, no run has ever settled"):
            verdict = self.verdict([])
            CHECK.assertEqual("never_run", verdict["state"])
            CHECK.assertIn("no post-merge run has ever completed", verdict["reason"].lower())
            CHECK.assertIn("no verdict", verdict["reason"].lower())
        with cases.case("active, green run 31 h old (the committed bound is 30)"):
            CHECK.assertEqual("stale", self.verdict([make_run(7, "success", hours_ago=31)])["state"])
        with cases.case("active, green run 29 h old"):
            verdict = self.verdict([make_run(7, "success", hours_ago=29)])
            CHECK.assertEqual("pass", verdict["state"], verdict["reason"])
        with cases.case("active, thirty runs none settled"):
            verdict = self.verdict([make_run(n, status="in_progress", hours_ago=1) for n in range(1, 31)])
            CHECK.assertEqual("stale", verdict["state"])
        cases.check()

    def test_tq600a_13_xiv_six_headlines_are_distinct_and_say_what_to_do(self):
        # covers: TQ-600a-13-xiv
        # angle: criterion
        """The six held outputs (red, did_not_complete, stale, disabled, never_run, could_not_read): headlines pairwise
        different; each says the cause is not the pull request's change and carries "to restore a verdict"; the three
        states of this AC name their way (dispatch / re-enable / the first run); could_not_read keeps the -ix headline.

        Wrong versions caught: red and did-not-complete sharing "Post-merge suite is not green"; any state omitting the
        not-the-PR sentence; a restore sentence that does not say how.
        """
        verdicts = self._six()
        cases = Cases()
        with cases.case("states"):
            CHECK.assertEqual(sorted(verdicts), sorted(v["state"] for v in verdicts.values()), "each double must give its own state")
        heads = {name: headline(v["reason"]) for name, v in verdicts.items()}
        with cases.case("six headlines, pairwise different and non-empty"):
            CHECK.assertEqual(6, len(set(heads.values())), f"headlines: {heads}")
            CHECK.assertNotIn("", heads.values())
        for name, verdict in verdicts.items():
            with cases.case(f"{name} says the cause is not the pull request's change"):
                CHECK.assertRegex(verdict["reason"], NOT_THE_PR)
            with cases.case(f"{name} says how to restore a verdict"):
                CHECK.assertRegex(verdict["reason"], RESTORE)
        for name, how in RESTORE_HOW.items():
            with cases.case(f"{name} names its way to restore"):
                tail = RESTORE.split(verdicts[name]["reason"], maxsplit=1)[-1]
                CHECK.assertRegex(tail, re.compile(how, re.IGNORECASE))
        with cases.case("could_not_read keeps the -ix headline"):
            CHECK.assertTrue(verdicts["could_not_read"]["reason"].startswith("Post-merge run history could not be read"))
        cases.check()

    def test_tq600a_13_xiv_stale_output_gives_the_start_time_and_the_age(self):
        # covers: TQ-600a-13-xiv
        # angle: boundary
        """A green run that started 31 h before the injected clock is stale and the output says so, giving the run's
        own ``run_started_at`` text and its age; at 29 h and at exactly the bound it passes (the rule is "more than").

        Wrong versions caught: the stale output omitting the start time or the age; a bound off by one (`>=`).
        """
        bound = tunables()["staleness_hours"]
        cases = Cases()
        with cases.case("31 h old"):
            run = make_run(7, "success", hours_ago=bound + 1)
            verdict = self.verdict([run])
            CHECK.assertEqual("stale", verdict["state"])
            CHECK.assertIn("stale", verdict["reason"].lower())
            CHECK.assertIn(run["run_started_at"], verdict["reason"])
            CHECK.assertRegex(verdict["reason"], rf"\b{bound + 1}(\.0)?\s*(h|hours)\b")
        with cases.case("exactly at the bound"):
            CHECK.assertEqual("pass", self.verdict([make_run(7, "success", hours_ago=bound)])["state"])
        with cases.case("the committed value moves the line"):
            CHECK.assertEqual("pass", self.verdict([make_run(7, "success", hours_ago=bound - 1)])["state"])
        cases.check()

    def test_tq600a_13_xiv_no_settled_run_in_the_page_is_stale_with_its_reason(self):
        # covers: TQ-600a-13-xiv
        # angle: boundary
        """Thirty runs, none settled (the page size is `run_history_page` of the tunables): stale, and the reason says
        "no settled run among the most recent 30" -- not a seventh wording, not never_run.

        Wrong versions caught: no-settled-in-page reported as never_run; the page size hard-coded in the sentence;
        the reason left generic.
        """
        pages = tunables()["run_history_page"]
        verdict = self.verdict([make_run(n, status="in_progress", hours_ago=1) for n in range(1, pages + 1)])
        CHECK.assertEqual("stale", verdict["state"])
        CHECK.assertIn(f"no settled run among the most recent {pages}", verdict["reason"].lower())
