"""
MODULE: tests.kernel.scheduler.test_jev_call_accounting
GOAL: A Jev assessment sent as several provider calls (chunks) is counted identically by the
    budget, the envelope usage summary, the usage rows and the tracer, and the budget guard
    reserves every provider call.
BUSINESS CONTEXT: A live run reported `jev_calls: 18` with 18 Jev generations in the trace but a
    usage row of `calls: 20`: an assessment of 33 questions at 20 questions per call is two
    provider calls, yet it was reserved and traced as one (Kernel V0.1 fix C).
ARCHITECTURE: The real compiled graph runs an executor that reserves one call (as the decision
    capabilities do) and asks the real TypeSafeJevAdapter, over a fake transport, for a chunked
    assessment. Everything is asserted from the final graph state, the service's usage
    summary and the RecordingTracer.
"""

from __future__ import annotations

import unittest
from typing import Any

from kernel.contracts import RunStatus, schema_ids
from kernel.observability.tracer import RecordingTracer
from kernel.providers.base import JevBatch, JevResult
from kernel.providers.jev import TypeSafeJevAdapter
from kernel.providers.jev_errors import JevUnavailable
from kernel.providers.jev_wire import RawResponse
from kernel.service_envelope import _usage
from tests.kernel.providers import jevkit as kit
from tests.kernel.scheduler.support import Rig, completed, descriptor, failed

QUESTIONS = 33
PER_CALL = 20


class _Transport:
    """Fake provider transport answering every question; records one entry per request."""

    name = "fake"
    version = "0"

    def __init__(self) -> None:
        self.requests: list[int] = []

    async def send(self, state: dict[str, Any], questions: dict[str, dict[str, Any]],
                   *, purpose: str = "") -> RawResponse:
        self.requests.append(len(questions))
        answers = {q: {"type": "noul", "noul": 0.5} for q in questions}
        return RawResponse(model="jev-x", answers=answers, input_tokens=10, output_tokens=1)

    async def aclose(self) -> None:
        """Nothing to close."""


class _Assessor:
    """Executor that reserves one call, then asks Jev a chunked assessment (like ask_jev)."""

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.result: JevResult | None = None
        self.invocations: list = []

    async def ainvoke(self, invocation, ctx):
        self.invocations.append(invocation)
        if not ctx.budget.reserve("jev"):
            return failed(invocation, "budget_exhausted")
        batch = JevBatch(purpose="decision.assess", state={"s": 1},
                         questions=[kit.spec("noul", f"q{i}") for i in range(QUESTIONS)],
                         correlation=ctx.corr)
        try:
            self.result = await ctx.jev.assess(batch)
        except JevUnavailable as exc:
            self.error = exc
            return failed(invocation, "provider_unavailable")
        return completed(invocation, schema_ids.DECISION_REPORT, usage=[self.result.usage])


def _run_rig(max_jev_calls: int) -> tuple[Rig, _Transport, _Assessor, RecordingTracer]:
    rig = Rig([descriptor("decide.root")])
    assessor = rig.bind("decide.root", _Assessor())
    rig.config = rig.config.model_copy(update={
        "limits": rig.config.limits.model_copy(update={"max_jev_calls": max_jev_calls})})
    transport = _Transport()
    tracer = RecordingTracer()
    rig.tracer = tracer
    rig.jev = TypeSafeJevAdapter(  # type: ignore[assignment]
        transport, timeout_seconds=5.0, max_questions_per_call=PER_CALL, max_state_chars=10000,
        max_retries=0, retry_backoff_seconds=0.0, tracer=tracer, model_name="jev-x")
    return rig, transport, assessor, tracer


class TestChunkedAssessmentCounting(unittest.IsolatedAsyncioTestCase):
    """One chunked assessment: two provider calls, counted as two everywhere."""

    async def test_budget_envelope_usage_rows_and_trace_agree(self) -> None:
        rig, transport, assessor, tracer = _run_rig(max_jev_calls=5)
        _, _, state = await rig.start()
        self.assertEqual(transport.requests, [PER_CALL, QUESTIONS - PER_CALL])
        self.assertIsNotNone(assessor.result)
        budgets = state["budgets"]
        generations = [c for c in tracer.calls if c.kind == "generation"]
        summary = _usage(state)
        self.assertEqual(budgets.jev_calls, 2)
        self.assertEqual([row.calls for row in budgets.usage_rows], [2])
        self.assertEqual(summary.jev_calls, 2)
        self.assertEqual([u.calls for u in summary.usage], [2])
        self.assertEqual(len(generations), 2)
        self.assertEqual([g.data["usage"].calls for g in generations], [1, 1])
        self.assertEqual([(g.data["metadata"]["chunk_index"], g.data["metadata"]["chunk_count"])
                          for g in generations], [(0, 2), (1, 2)])
        self.assertEqual(summary.input_tokens, 20)

    async def test_a_budget_cap_hit_mid_chunk_stops_before_the_unreserved_call(self) -> None:
        rig, transport, assessor, tracer = _run_rig(max_jev_calls=1)
        _, _, state = await rig.start()
        self.assertEqual(transport.requests, [PER_CALL])  # the second chunk was never sent
        self.assertIsInstance(assessor.error, JevUnavailable)
        self.assertIn("budget exhausted", str(assessor.error))
        self.assertEqual(state["budgets"].jev_calls, 1)  # never above the cap
        generations = [c for c in tracer.calls if c.kind == "generation"]
        self.assertEqual(len(generations), 1)
        self.assertEqual(generations[0].data["metadata"]["status"], "ok")
        self.assertNotEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_a_retried_chunk_is_still_one_provider_call(self) -> None:
        rig, transport, _, tracer = _run_rig(max_jev_calls=5)
        original = transport.send
        failures = {"left": 1}

        async def flaky(state, questions, *, purpose=""):
            if failures["left"]:
                failures["left"] -= 1
                from kernel.providers.jev_errors import JevTransientError  # noqa: PLC0415
                raise JevTransientError("boom")
            return await original(state, questions, purpose=purpose)

        transport.send = flaky  # type: ignore[method-assign]
        adapter: Any = rig.jev
        adapter._max_retries = 1
        _, _, state = await rig.start()
        self.assertEqual(state["budgets"].jev_calls, 2)
        self.assertEqual([row.calls for row in state["budgets"].usage_rows], [2])
        generations = [c for c in tracer.calls if c.kind == "generation"]
        self.assertEqual([g.data["metadata"]["attempts"] for g in generations], [2, 1])


if __name__ == "__main__":
    unittest.main()
