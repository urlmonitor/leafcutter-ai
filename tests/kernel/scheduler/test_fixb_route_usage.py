"""
MODULE: tests.kernel.scheduler.test_fixb_route_usage
GOAL: Prove Jev routing usage is accounted once per Jev call, across question chunks.
BUSINESS CONTEXT: The cost guard folds routing usage into the run budget; copying one call's
    usage onto every question of its chunk and truncating counted a call twice and lost another.
ARCHITECTURE: `route_semantic` over a Jev double whose calls report distinct costs, then the same
    flattening the route node applies; no scheduler graph is needed.
"""

from __future__ import annotations

import unittest

from kernel.contracts import CorrelationIds, Usage, schema_ids
from kernel.contracts.work import RequestBody
from kernel.providers.base import JevBatch, JevResult
from kernel.providers.fakes import ScriptedJev, choice_answer
from kernel.registry.eligibility import EligibilityReport
from kernel.scheduler.routing import RouteEntry, route_semantic
from tests.kernel.scheduler.support import Rig, descriptor


class CostedJev(ScriptedJev):
    """A Jev double whose n-th call reports a cost of n dollars."""

    async def assess(self, batch: JevBatch) -> JevResult:
        """Answer like the scripted double, with a per-call cost."""
        result = await super().assess(batch)
        cost = float(len(self.batches))
        return result.model_copy(update={"usage": Usage(
            provider="jev", calls=1, cost_usd=cost, cost_provenance="reported")})


def _entry(index: int, cap: object) -> RouteEntry:
    """Return a routing entry for one semantic request."""
    body = RequestBody(kind="capability", goal=f"decide {index}",
                       payload_schema=schema_ids.GOAL_REQUEST, payload={"goal": f"decide {index}"},
                       requested_output_schema=schema_ids.DECISION_REPORT)
    report = EligibilityReport(eligible=[cap], excluded=[], matched_ids=[],
                               outcome_hint="needs_semantic")
    return RouteEntry(f"wi-{index}", body, report)


class TestRouteUsage(unittest.IsolatedAsyncioTestCase):
    """One usage per Jev call."""

    async def test_five_questions_in_chunks_of_three_account_two_distinct_calls(self) -> None:
        cap = descriptor("decide.a", routing="semantic")
        jev = CostedJev().script("kernel.route", "route.*", choice_answer("decide.a"))
        base = Rig([cap]).config
        cfg = base.model_copy(update={"jev": base.jev.model_copy(
            update={"max_questions_per_call": 3})})
        routed, calls = await route_semantic(
            jev, [_entry(i, cap) for i in range(5)], goal="g", component_ids=[], cfg=cfg,
            calls_available=5, corr=CorrelationIds())
        self.assertEqual(calls, 2)
        usage = [u for r in routed.values() for u in r.usage]
        self.assertEqual(sorted(u.cost_usd for u in usage), [1.0, 2.0])
        self.assertEqual(sum(len(r.usage) for r in routed.values()), calls)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: Regression for review finding R1-4 (usage mis-accounted
#   across question chunks). (#KernelBootstrapV0/FIXB)
# ====================================================================
