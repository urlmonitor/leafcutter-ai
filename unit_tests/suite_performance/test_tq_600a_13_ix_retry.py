"""TQ-600a-13-ix: the one bounded retry of a verdict read, for transient failures only.

At most ONE retry, only for 429, 5xx, timeout and connection failure, after an injectable delay (``Retry-After`` honoured,
capped at a few seconds); never for 401, 403, 404 or a malformed body. The delay is injected as ``sleep=`` on
``post_merge_hold.evaluate`` (a ``Sleeps`` recorder: nothing really waits); ``main`` reads ``POST_MERGE_HOLD_RETRY_DELAY_SECONDS``.
Counting requests at the server (faulted ones included) shows how many attempts the real client really made.
"""

from __future__ import annotations

from ._ending_harness import CHECK, Cases
from ._ix_harness import (
    CAUSE, HANG, JSON_LIST, NOT_JSON, RUNS_PATH, WORKFLOW_PATH, FaultCase, Sleeps, closed_port_url, evaluate, http,
)

READS = {"workflow": WORKFLOW_PATH, "runs": RUNS_PATH}
CAP = 5.0  # "a few seconds": the delay never exceeds this
TRANSIENT = [("429", http(429)), ("500", http(500)), ("503", http(503)), ("timeout", HANG)]
PERMANENT = [("401", http(401)), ("403", http(403)), ("404", http(404)), ("non-JSON", NOT_JSON), ("list", JSON_LIST)]


class VerdictReadRetry(FaultCase):
    def _arm(self, read, fault, times=None):
        self.svc.reset()
        self.green()
        self.svc.fail("GET", READS[read], fault, times)

    def test_tq600a_13_ix_a_transient_failure_is_retried_once_and_a_second_answer_is_used(self):
        # covers: TQ-600a-13-ix
        # angle: criterion
        """AC TQ-600a-13-ix: a verdict read that fails once with 429, 5xx or a timeout and then answers gives the verdict, after one delay."""
        cases = Cases()
        for read, path in READS.items():
            for label, fault in TRANSIENT:
                with cases.case(f"{read}: {label} once"):
                    self._arm(read, fault, times=1)
                    sleeps = Sleeps()
                    verdict = evaluate(self.svc.url, sleeps=sleeps)
                    CHECK.assertEqual("pass", verdict["state"], str(verdict))
                    CHECK.assertEqual(2, self.svc.hits(path), "the read must be made twice: the failure and the one retry")
                    CHECK.assertEqual(1, len(sleeps), f"one delay before the retry, saw {list(sleeps)}")
                    CHECK.assertTrue(0 <= sleeps[0] <= CAP, f"delay {sleeps} is outside 0..{CAP} s")
        cases.check()

    def test_tq600a_13_ix_a_transient_failure_that_persists_stops_after_one_retry(self):
        # covers: TQ-600a-13-ix
        # angle: boundary
        """AC TQ-600a-13-ix: a read that keeps failing is attempted exactly twice (never three times) and then is could_not_read."""
        cases = Cases()
        for read, path in READS.items():
            for label, fault in TRANSIENT:
                with cases.case(f"{read}: {label} always"):
                    self._arm(read, fault)
                    sleeps = Sleeps()
                    verdict = evaluate(self.svc.url, sleeps=sleeps)
                    CHECK.assertEqual("could_not_read", verdict["state"], str(verdict))
                    CHECK.assertEqual(2, self.svc.hits(path), "exactly one retry")
                    CHECK.assertEqual(1, len(sleeps), list(sleeps))
        with cases.case("connection refused is transient too"):
            sleeps = Sleeps()
            verdict = evaluate(closed_port_url(), sleeps=sleeps)
            CHECK.assertEqual("could_not_read", verdict["state"], str(verdict))
            CHECK.assertRegex(f"{verdict['cause']} {verdict['reason']}", CAUSE["connection"])
            CHECK.assertEqual(1, len(sleeps), "a refused connection is retried once, after one delay")
        cases.check()

    def test_tq600a_13_ix_a_permanent_failure_is_never_retried(self):
        # covers: TQ-600a-13-ix
        # angle: discrimination
        """AC TQ-600a-13-ix: 401, 403, 404 and a malformed body are read once, with no delay (a retry that retried everything goes red)."""
        cases = Cases()
        for read, path in READS.items():
            for label, fault in PERMANENT:
                with cases.case(f"{read}: {label}"):
                    self._arm(read, fault)
                    sleeps = Sleeps()
                    verdict = evaluate(self.svc.url, sleeps=sleeps)
                    CHECK.assertEqual("could_not_read", verdict["state"], str(verdict))
                    CHECK.assertEqual(1, self.svc.hits(path), "not retried")
                    CHECK.assertEqual([], list(sleeps))
        cases.check()

    def test_tq600a_13_ix_retry_after_is_honoured_and_capped(self):
        # covers: TQ-600a-13-ix
        # angle: boundary
        """AC TQ-600a-13-ix: the delay is the server's ``Retry-After`` seconds when small, never more than a few seconds, and still a delay when unusable."""
        cases = Cases()
        for header, check in [("2", lambda d: d == 2), ("3600", lambda d: 0 < d <= CAP), ("soon", lambda d: 0 <= d <= CAP)]:
            with cases.case(f"Retry-After: {header}"):
                self._arm("runs", http(429, {"Retry-After": header}), times=1)
                sleeps = Sleeps()
                verdict = evaluate(self.svc.url, sleeps=sleeps)
                CHECK.assertEqual("pass", verdict["state"], str(verdict))
                CHECK.assertTrue(len(sleeps) == 1 and check(sleeps[0]), f"Retry-After {header!r} gave delays {list(sleeps)}")
        cases.check()

    def test_tq600a_13_ix_the_real_main_retries_once_with_the_delay_from_the_environment(self):
        # covers: TQ-600a-13-ix
        # angle: reachability
        """AC TQ-600a-13-ix: through ``main`` a read that fails once then answers passes (exit 0); one that keeps failing exits 1 after two attempts."""
        self._arm("runs", http(500), times=1)
        ran = self.ask()
        CHECK.assertEqual((0, 2), (ran.code, self.svc.hits(RUNS_PATH)), ran.out)
        self._arm("workflow", http(503))
        ran = self.ask()
        CHECK.assertEqual((1, 2), (ran.code, self.svc.hits(WORKFLOW_PATH)), ran.out)
