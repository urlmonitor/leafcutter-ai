"""
MODULE: unit_tests/workflows/test_bo_400e_3_vii_gate.py
GOAL: RED tests for BO-400e-3-vii -- finalization closes nothing without the PERSON's own confirmation;
      a declined or unanswered one stops the run before the merge; an agent's 'yes' is no answer.

The gate's correctness is control flow across a pause and a resume, so each test drives the real
finalize-feature.js through the E2 harness twice (pause, then resume with a validated answer -- the
pattern of unit_tests/workflows/test_bo_2300_pause_resume.py) and asserts on which dispatches were and
were NOT recorded: above all the absence of the close and merge dispatches. Replies are the real
module's output for a real scratch repository. Dispatch contract: _bo400e3_finalize_harness.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo400e3_finalize_harness as H  # noqa: E402
from _bo400e3_support import epic_store  # noqa: E402

BRANCH = "EPIC-Alpha"


class _GateCase(unittest.TestCase):
    def setUp(self):
        self.store = epic_store(self)
        self.derived = self.store.derive(branch=BRANCH)
        self.closed = self.store.close(self.derived["set_file"])
        self.root = str(self.store.repo)

    def first(self):
        return H.first_run(BRANCH, self.root, derive=self.derived, close=self.closed)

    def resume(self, action, **kw):
        record, _prompt = H.closure_pause(self.first())
        return H.resume_run(BRANCH, self.root, record, action, derive=self.derived, close=self.closed,
                            commit=H.committed_answer(), **kw)

    def assert_nothing_written_and_halted(self, run, word):
        self.assertEqual(H.calls(run, H.CLOSE), [], H.labels(run))
        self.assertEqual(H.calls(run, H.COMMIT), [], H.labels(run))
        self.assertEqual(H.calls(run, H.MERGE), [], "the merge was dispatched")
        self.assertEqual((run.result or {}).get("status"), "halted", run.result)
        self.assertIn(word, H.report_text(run))


class TestPersonGate(_GateCase):
    def test_person_confirmation_closes_exactly_the_listed_records_and_continues(self):
        # covers: BO-400e-3-vii
        # angle: criterion
        """AC BO-400e-3-vii: a resume answer {gate_id, action confirm, channel person} against a matching
        pause record closes the listed set once and the run proceeds to the Step 4 dispatches."""
        first = self.first()
        self.assertEqual(H.calls(first, H.CLOSE), [], "closed before anyone confirmed")
        record, _prompt = H.closure_pause(first)
        run = H.resume_run(BRANCH, self.root, record, "confirm", derive=self.derived, close=self.closed,
                           commit=H.committed_answer())
        self.assertEqual(len(H.calls(run, H.CLOSE)), 1, H.labels(run))
        self.assertGreaterEqual(len(H.calls(run, H.MERGE)), 1, H.labels(run))
        self.assertEqual(H.calls(run, "pause-persist"), [], "the confirmed run paused again")

    def test_decline_closes_nothing_and_halts_before_merge(self):
        # covers: BO-400e-3-vii
        # angle: failure
        """A person's decline: no close, no commit, no merge dispatch; the halted result says declined,
        names alpha-02.md and BO-9100a-2 as left open and says a re-run shows the list again."""
        run = self.resume("decline")
        self.assert_nothing_written_and_halted(run, "declined")
        text = H.report_text(run)
        self.assertTrue(H.near(text, "alpha-02.md", "left open"), text[:800])
        self.assertTrue(H.near(text, "bo-9100a-2", "left open"), text[:800])
        self.assertTrue("again" in text and "list" in text, text[:800])
        self.assertNotIn("3.5", H.completed_steps(run))

    def test_no_answer_or_stale_record_is_unanswered_and_halts(self):
        # covers: BO-400e-3-vii
        # angle: boundary
        """A headless run (no resume answer) and a resume against a stale pause record both stop before
        the merge with no close dispatch; the stale one is reported as unanswered, not declined."""
        with self.subTest(case="headless"):
            run = self.first()
            self.assertEqual(H.calls(run, H.CLOSE), [])
            self.assertEqual(H.calls(run, H.MERGE), [], "the merge was dispatched")
            self.assertNotIn("declined", H.report_text(run))
            # CURRENT documented behaviour (review finding M-8): the headless run does not return a
            # 'halted' result; it PAUSES at the closure gate with a persisted record and returns
            # paused_awaiting_input naming that gate. (The AC text says 'reported as unanswered'; the
            # pause result does not use that word -- see the report to the caller.)
            self.assertEqual((run.result or {}).get("status"), "paused_awaiting_input", run.result)
            self.assertEqual((run.result or {}).get("gate_id"), "step-3.5-closure-gate", run.result)
            record, _prompt = H.closure_pause(run)
            self.assertEqual(record["gate_id"], "step-3.5-closure-gate")
            self.assertEqual(record["context"]["set_digest"], self.derived["set_digest"])
            self.assertNotIn("3.5", H.completed_steps(run))
        with self.subTest(case="stale record"):
            run = self.resume("confirm", stale=True)
            self.assert_nothing_written_and_halted(run, "unanswered")
            self.assertNotIn("declined", H.report_text(run))

    def test_agent_yes_is_treated_as_no_answer(self):
        # covers: BO-400e-3-vii
        # angle: discrimination
        """The live gate dispatch answered {status ok}/{action ok} by the stubbed agent, and a resume
        answer without channel person: in both runs nothing is closed and no merge is dispatched.
        NEGATIVE CONTROL: the same resume answer WITH channel person does close."""
        with self.subTest(case="live agent says ok"):
            # Stub every label a gate agent could be dispatched under with a STRONG yes (review finding
            # M-8: the old stub only had effect if the label was dispatched at all). Whether or not the
            # workflow dispatches it, the run must still reach the person-only gate and pause there.
            agent_yes = {"status": "ok", "action": "confirm", "choice": "confirm", "answer": "yes"}
            run = H.run_finalize(BRANCH, self.root, derive=self.derived, close=self.closed,
                                 extra={"step-3.5-closure-gate": agent_yes, "closure-gate": agent_yes},
                                 args={"run_id": "finalize-epic-x-20261012"})
            self.assertEqual(H.calls(run, H.CLOSE), [], H.labels(run))
            self.assertEqual(H.calls(run, H.MERGE), [], "an agent's yes let the run merge")
            self.assertEqual(H.calls(run, H.COMMIT), [], H.labels(run))
            self.assertEqual((run.result or {}).get("status"), "paused_awaiting_input", run.result)
            self.assertEqual(len(H.calls(run, "pause-persist")), 1,
                             "the gate was never reached, so the 'no close' result proves nothing")
            self.assertNotIn("3.5", H.completed_steps(run))
        with self.subTest(case="resume answer without channel person"):
            run = self.resume("confirm", channel=None)
            self.assertEqual(H.calls(run, H.CLOSE), [], H.labels(run))
            self.assertEqual(H.calls(run, H.MERGE), [], "an answer without provenance let the run merge")
        with self.subTest(case="control: the same answer from the person"):
            run = self.resume("confirm", channel="person")
            self.assertEqual(len(H.calls(run, H.CLOSE)), 1, H.labels(run))

    def test_resume_for_a_different_set_than_the_one_confirmed_is_unanswered(self):
        # covers: BO-400e-3-vii
        # angle: discrimination
        """AC BO-400e-3-vii (review finding M-2): the pause record's context holds the set_digest that
        was LISTED to the person. A resume whose stored digest differs from the digest the re-run just
        derived is an answer to a different list: no close, no commit, no merge, halted as unanswered.
        CONTROL: the same resume with the matching digest closes (test_person_confirmation_...).
        WRONG VERSION: the record's context is never compared with the freshly derived set."""
        record, _prompt = H.closure_pause(self.first())
        self.assertEqual(record["context"]["set_digest"], self.derived["set_digest"], "control row")
        stale = copy.deepcopy(record)
        stale["context"]["set_digest"] = "0" * len(self.derived["set_digest"])
        self.assertNotEqual(stale["context"]["set_digest"], self.derived["set_digest"])
        run = H.resume_run(BRANCH, self.root, stale, "confirm", derive=self.derived, close=self.closed,
                           commit=H.committed_answer())
        self.assert_nothing_written_and_halted(run, "unanswered")
        self.assertNotIn("declined", H.report_text(run))


if __name__ == "__main__":
    unittest.main()
