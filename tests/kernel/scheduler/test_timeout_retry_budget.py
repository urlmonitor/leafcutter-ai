"""
MODULE: tests.kernel.scheduler.test_timeout_retry_budget
GOAL: Prove that retries of a capability that times out on every attempt do not use up
    `limits.max_active_seconds` before the decision work starts, and that the run then ends
    with an honest partial outcome rather than a guard stop.
BUSINESS CONTEXT: Ticket KernelDecisionGoalRoutingAndRetrievalTimeout, AC-4. With the default
    limits (capability_timeout_seconds 120, max_retries 2, max_active_seconds 300) three timed-out
    retrievals cost 360 s: the active-time guard tripped and the decision step never ran
    (runs run-560b8dd4949c4000 and run-a51ddba49ea84482).
ARCHITECTURE: The real compiled graph with the scheduler Rig. The retrieval child is a stub that
    advances a fake monotonic clock by the capability timeout and returns the `timeout` failure
    `_run_executor` produces (retryable), so the scheduler's retry handling and the active-time
    accounting run for real without the test sleeping. The default limits are used unchanged.
"""

from __future__ import annotations

import unittest

from kernel.config import load_kernel_config
from kernel.contracts import CapabilityResult, ResultStatus, RunStatus
from tests.kernel.scheduler.support import (
    Rig,
    descriptor,
    failed,
    proposal,
    retrieval_descriptor,
    two_phase,
    waiting,
)

LIMITS = load_kernel_config().limits


class _Clock:
    """Fake monotonic clock the timing-out retrieval stub advances."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _TimingOutRetrieval:
    """Retrieval stub: every attempt burns the capability timeout, then fails as `timeout`."""

    def __init__(self, clock: _Clock) -> None:
        self.clock = clock
        self.invocations: list = []

    async def ainvoke(self, invocation, ctx):  # noqa: ANN001, ANN201
        self.invocations.append(invocation)
        self.clock.now += LIMITS.capability_timeout_seconds
        return failed(invocation, "timeout", retryable=True)


class _FlakyRetrieval:
    """Retrieval stub: fails fast with a retryable error that is not a timeout."""

    def __init__(self) -> None:
        self.invocations: list = []

    async def ainvoke(self, invocation, ctx):  # noqa: ANN001, ANN201
        self.invocations.append(invocation)
        return failed(invocation, "provider_unavailable", retryable=True)


def _decision_after_failed_retrieval(invocation) -> CapabilityResult:  # noqa: ANN001
    """The decision step on no evidence: an honest partial result, not a made-up decision."""
    return CapabilityResult(invocation_id=invocation.id, work_item_id=invocation.work_item_id,
                            status=ResultStatus.PARTIAL,
                            limitations=["insufficient evidence: retrieval timed out"])


def _rig(clock: _Clock) -> Rig:
    rig = Rig([descriptor("decide.root"), retrieval_descriptor("retrieve.repository")])
    rig.monotonic = clock
    rig.bind("decide.root", factory=two_phase(
        lambda inv: waiting(inv, proposal("task_context", "Which facts apply?",
                                          priority="supporting")),
        _decision_after_failed_retrieval))
    return rig


class TestRetrievalRetriesStayBelowTheActiveTimeBudget(unittest.IsolatedAsyncioTestCase):
    """AC-4: timeouts on every retrieval attempt leave time for the decision step."""

    async def _run(self):  # noqa: ANN202
        clock = _Clock()
        rig = _rig(clock)
        retrieval = rig.bind("retrieve.repository", _TimingOutRetrieval(clock))
        _, _, state = await rig.start()
        return rig, retrieval, state

    async def test_ac4_retrieval_retries_do_not_trip_max_active_seconds(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        """AC-4: with default limits the retries of a timing-out retrieval spend < the budget."""
        _, retrieval, state = await self._run()
        self.assertLess(state["budgets"].active_seconds, LIMITS.max_active_seconds,
                        f"{len(retrieval.invocations)} retrieval attempts of "
                        f"{LIMITS.capability_timeout_seconds}s used the whole active-time budget")
        self.assertNotIn("guard: max_active_seconds", state["outcome"].diagnostics)

    async def test_ac4_the_decision_step_still_runs_after_the_retrieval_retries(self) -> None:
        # covers: UNKNOWN
        # angle: reachability
        """AC-4: the parent is resumed (decision work starts) and ends with a partial outcome."""
        rig, retrieval, state = await self._run()
        self.assertGreaterEqual(len(retrieval.invocations), 1)
        self.assertEqual(len(rig.executors["decide.root"].invocations), 2,
                         "the decision step never ran after the retrieval retries")
        outcome = state["outcome"]
        self.assertEqual(outcome.status, RunStatus.PARTIAL)
        self.assertTrue(outcome.limitations, "a partial outcome must say what is missing")

    async def test_ac4_a_non_timeout_failure_keeps_its_configured_retries(self) -> None:
        # covers: UNKNOWN
        # angle: discrimination
        """AC-4 control: the fix bounds timeout retries; other retryable failures keep theirs.

        Catches the wrong version that sets the retry count to 0 for every retryable failure.
        """
        rig = _rig(_Clock())
        flaky = rig.bind("retrieve.repository", _FlakyRetrieval())
        await rig.start()
        self.assertEqual(len(flaky.invocations), 1 + LIMITS.max_retries)


class TestUnknownAttemptTime(unittest.TestCase):
    """A timeout result without its elapsed time never earns a retry the budget forbids."""

    def test_ac4_missing_elapsed_time_counts_as_a_full_timeout(self) -> None:
        # covers: UNKNOWN
        # angle: failure
        from kernel.contracts import ErrorInfo
        from kernel.scheduler.guards import retry_allowed
        from kernel.scheduler.state import Budgets
        limits = LIMITS.model_copy(update={"capability_timeout_seconds": 120.0,
                                           "max_active_seconds": 300, "max_retries": 2})
        error = ErrorInfo(code="timeout", message="x", retryable=True)
        charged = Budgets(active_seconds=120.0)
        self.assertFalse(retry_allowed(charged, "w", error, limits, None),
                         "an unknown attempt time must count as one full timeout")
        self.assertTrue(retry_allowed(charged, "w", error, limits, 10.0),
                        "a known short attempt still leaves room for a retry")


if __name__ == "__main__":
    unittest.main()
