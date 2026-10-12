"""
Tests for TQ-600a-13-xiii (count half) -- the pass-on-retry count is read from the earlier runs' recorded verdicts, never from
the notice; an unreadable artifact is counted as zero and said so; timing never escalates; a superseded cancellation is not a run.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiii.yaml
Production contract: see test_tq_600a_13_xiii.py.
"""

from __future__ import annotations

from ._ending_harness import Cases
from ._flaky_harness import FLAKY_LABEL, Earlier, FlakyCase, lane_id
from ._hold_harness import make_run
from .test_tq_600a_13_xiii import earlier_runs

B, C = lane_id("b"), lane_id("c")


class TestTq600a13XiiiTheCountIgnoresTheNotice(FlakyCase):
    def _verdict(self, retried, earlier, number=6, lane="correctness"):
        self.svc.reset()
        self.seed(number, earlier)
        return self.run_verdict(retried, number, lane=lane)

    def test_tq600a_13_xiii_the_count_ignores_the_notice(self):
        # covers: TQ-600a-13-xiii
        # angle: discrimination
        """Wrong versions caught: the count read from the flaky notice (a never-written, hand-edited or closed notice
        changes the verdict); an unreadable earlier artifact taken for a clean run without saying so; a timing-lane
        test that escalates; a superseded cancellation that fills a window slot; the flaky notice changing the hold.
        """
        rows = Cases()
        with rows.case("two earlier occurrences and no flaky notice at all: red, and the issue API is never read"):
            verdict = self._verdict((B,), earlier_runs((B,), (B,), (), ()))
            self.assertEqual(("red", [B], {B: 3}), (verdict["verdict"], verdict["repeated_pass_on_retry"], verdict["pass_on_retry_window"]))
            self.assertEqual([], [p for p in self.svc.paths() if p.endswith("/issues")], "the count never depends on an issue")
        with rows.case("a hand-edited notice claiming a high count does not turn a clean history red"):
            self.svc.reset()
            self.seed(6, earlier_runs((), (), (), ()))
            self.svc.add_issue(9, title="Flaky", body=f"`{B}`: 5 of 5 runs\n", labels=[FLAKY_LABEL])
            verdict = self.run_verdict((B,), 6)
            self.assertEqual(("green", [], {B: 1}), (verdict["verdict"], verdict["repeated_pass_on_retry"], verdict["pass_on_retry_window"]))
        with rows.case("a closed notice does not reset the count"):
            self.svc.reset()
            self.seed(6, earlier_runs((B,), (), (), ()))
            self.svc.add_issue(9, labels=[FLAKY_LABEL], state="closed")
            self.assertEqual("red", self.run_verdict((B,), 6)["verdict"])
        with rows.case("one unreadable earlier artifact: the verdict says four runs were read, and it is not a clean run"):
            earlier = [Earlier(5, (), "corrupt"), Earlier(4, (B,)), Earlier(3, ()), Earlier(2, ())]
            verdict = self._verdict((), earlier)
            self.assertEqual(4, verdict["window_runs_read"])
            self.assertEqual({B: 1}, verdict["pass_on_retry_window"], "the readable runs are still counted")
        with rows.case("unreadable in each way (corrupt zip, bad json, no artifact): three runs read of five"):
            verdict = self._verdict((B,), [Earlier(5, (), "badjson"), Earlier(4, (), "missing"), Earlier(3, (B,)), Earlier(2, ())])
            self.assertEqual((3, "red"), (verdict["window_runs_read"], verdict["verdict"]))
        with rows.case("a first run ever: one run read, green"):
            verdict = self._verdict((B,), [])
            self.assertEqual((1, "green", {B: 1}), (verdict["window_runs_read"], verdict["verdict"], verdict["pass_on_retry_window"]))
        rows.check()

    def test_tq600a_13_xiii_timing_never_escalates_and_a_cancelled_slot_is_skipped(self):
        # covers: TQ-600a-13-xiii
        # angle: discrimination
        """Timing lane: two earlier occurrences, green. The same history on the correctness lane: red (the control).

        A superseded cancellation in the window is skipped, not a slot: B at runs 6 (current) and 1 is two of five only
        when run 3 (cancelled, superseded by 4) is passed over, and that run's artifact is never read.
        """
        history = earlier_runs((B,), (B,), (), ())
        rows = Cases()
        with rows.case("timing lane, two earlier occurrences plus the current one: green, nothing repeated"):
            verdict = self._verdict((B,), history, lane="timing")
            self.assertEqual(("green", "timing", []), (verdict["verdict"], verdict["lane"], verdict["repeated_pass_on_retry"]))
        with rows.case("control: the same history on the correctness lane is red"):
            self.assertEqual("red", self._verdict((B,), history)["verdict"])
        with rows.case("a superseded cancellation is skipped and the window reaches run 1"):
            earlier = [Earlier(5), Earlier(4), Earlier(3, (B,), conclusion="cancelled"), Earlier(2), Earlier(1, (B,))]
            verdict = self._verdict((B,), earlier)
            self.assertEqual(("red", [B], {B: 2}, 5), (verdict["verdict"], verdict["repeated_pass_on_retry"], verdict["pass_on_retry_window"], verdict["window_runs_read"]))
            self.assertEqual([], self.svc.artifact_reads(3), "the cancelled run is never read")
        with rows.case("a run that has not finished is not a slot either"):
            earlier = [Earlier(5, status="in_progress", conclusion=None), Earlier(4), Earlier(3), Earlier(2), Earlier(1, (B,))]
            verdict = self._verdict((B,), earlier)
            self.assertEqual(("red", 5), (verdict["verdict"], verdict["window_runs_read"]))
        rows.check()

    def test_tq600a_13_xiii_the_reads_are_bounded_and_the_flaky_notice_never_holds(self):
        # covers: TQ-600a-13-xiii
        # angle: failure
        """At most nine requests (one history page, four artifact lists, four downloads), and an open flaky notice leaves the hold as it was."""
        verdict = self._verdict((B,), earlier_runs((), (B,), (), ()))
        gets = self.svc.paths()
        self.assertEqual("red", verdict["verdict"])
        self.assertLessEqual(len(gets), 9, gets)
        self.assertEqual(1, len([p for p in gets if "/actions/workflows/" in p]), "one run-history page")
        self.svc.reset()
        self.serve([make_run(6, "success"), make_run(7, "success")])
        without = self.evaluate()
        self.svc.add_issue(9, title="Flaky", body="x", labels=[FLAKY_LABEL])
        with_notice = self.evaluate()
        self.assertEqual(("pass", "pass"), (without["state"], with_notice["state"]), "a flaky notice never holds a pull request")
        self.assertTrue(self.svc.issues[9]["state"] == "open")
