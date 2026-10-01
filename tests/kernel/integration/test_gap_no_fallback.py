"""
MODULE: tests.kernel.integration.test_gap_no_fallback
GOAL: Test the gap scenarios that must end blocked: fallback disabled or impossible, a denied
    native action that must not be rerouted through a host fallback, and a known capability that
    is merely unavailable (never a gap).
BUSINESS CONTEXT: A missing capability is product evidence, but a denied or unavailable one is
    not: routing those through a permissive host path would turn a policy decision into a
    workaround, and filing them as "build this" gaps would mislead the backlog (Rev 3 section 14).
ARCHITECTURE: Real compiled graph over the scheduler Rig. Every rig also registers the approved
    `host.research` operation, so each test proves the fallback was *available* and still not
    used (no interaction is ever opened).
"""

from __future__ import annotations

import unittest

from kernel.config import load_kernel_config
from kernel.contracts import (
    FallbackOutcome,
    GapType,
    RoutingOutcome,
    RunStatus,
    WorkItemStatus,
    schema_ids,
)
from kernel.persistence.gap_store import is_build_opportunity
from kernel.providers.fakes import choice_answer
from tests.kernel.helpers import make_descriptor
from tests.kernel.integration.test_gap_fallback import fallback_rig, host_research
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    proposal,
    two_phase,
    waiting,
    with_limits,
)


def set_host(rig: Rig, **changes: object) -> None:
    """Replace host config values on the rig."""
    rig.config = rig.config.model_copy(update={
        "host": rig.config.host.model_copy(update=changes)})


def native_evidence(cap_id: str, **overrides: object):
    """Return a native `retrieve` capability for evidence requests (overrides applied)."""
    fields = {"id": cap_id, "binding": cap_id, "name": cap_id, "description": "Retrieves evidence.",
              "request_kinds": ["evidence"], "accepts_schemas": [schema_ids.RETRIEVAL_REQUEST],
              "produces_schemas": [schema_ids.EVIDENCE_BUNDLE], "operations": ["retrieve"],
              "routing": "fixed", "permissions_required": [], **overrides}
    return make_descriptor(**fields)


def evidence_rig(*natives) -> Rig:
    """Return a rig whose root asks for `retrieve` evidence; the host fallback is approved."""
    rig = Rig([descriptor("decide.root"), host_research(), *natives])
    rig.bind("decide.root", factory=two_phase(
        lambda inv: waiting(inv, proposal(operation="retrieve")), completed))
    rig.bind("host.research")
    for native in natives:
        rig.bind(native.id)
    return rig


def child(state: dict):
    """Return the only non-root work item."""
    (item,) = [i for i in state["work_items"].values()
               if i.id != state["task"].root_work_item_id]
    return item


class TestFallbackDisabled(unittest.IsolatedAsyncioTestCase):
    """With fallback off, or nothing approved to fall back to, the item ends blocked."""

    async def assert_blocked_with_gap(self, rig: Rig, reason: str) -> dict:
        _, _, state = await rig.start()
        self.assertEqual(child(state).status, WorkItemStatus.BLOCKED)
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertEqual(state.get("interaction_queue"), [])
        text = " | ".join(state["outcome"].limitations)
        self.assertIn("no_capability", text)
        self.assertIn(reason, text)
        (gap,) = rig.gap_store.observations
        self.assertEqual((gap.gap_type, gap.fallback_outcome),
                         (GapType.UNSUPPORTED, FallbackOutcome.BLOCKED))
        self.assertEqual(state["budgets"].host_operations, 0)
        return state

    async def test_fallback_disabled_blocks_the_item_with_the_gap_and_a_draft(self) -> None:
        rig = fallback_rig()
        set_host(rig, fallback_on_no_match=False)
        await self.assert_blocked_with_gap(rig, "host fallback is disabled")
        (gap,) = rig.gap_store.observations
        self.assertTrue(is_build_opportunity(gap))
        self.assertIn("Author: template", rig.gap_store.drafts[gap.proposal.draft_ref])

    async def test_host_disabled_blocks_too(self) -> None:
        rig = fallback_rig()
        set_host(rig, enabled=False)
        await self.assert_blocked_with_gap(rig, "host fallback is disabled")

    async def test_no_approved_host_operation_for_the_output_blocks(self) -> None:
        # the host operation produces findings, the request wants an evidence bundle
        rig = Rig([descriptor("decide.root"),
                   descriptor("host.synthesize", kinds=("synthesis",), mode="host_handoff",
                              accepts=schema_ids.SYNTHESIS_REQUEST, produces=schema_ids.FINDINGS,
                              operations=("synthesize_evidence",))])
        rig.bind("decide.root", factory=two_phase(
            lambda inv: waiting(inv, proposal(operation="retrieve")), completed))
        rig.bind("host.synthesize")
        await self.assert_blocked_with_gap(rig, "no approved host operation")

    async def test_an_exhausted_host_budget_blocks(self) -> None:
        rig = fallback_rig()
        rig.config = with_limits(rig.config, max_host_operations=0)
        await self.assert_blocked_with_gap(rig, "no approved host operation")

    async def test_a_disabled_host_capability_is_not_used_as_fallback(self) -> None:
        rig = Rig([descriptor("decide.root"), host_research(enabled=False)])
        rig.bind("decide.root", factory=two_phase(
            lambda inv: waiting(inv, proposal(operation="retrieve")), completed))
        rig.bind("host.research")
        await self.assert_blocked_with_gap(rig, "no approved host operation")

    async def test_a_root_request_nothing_can_serve_is_blocked_not_faked(self) -> None:
        rig = Rig([descriptor("decide.other", kinds=("options",)), host_research()])
        rig.bind("decide.other")
        rig.bind("host.research")
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertIsNone(state["outcome"].output)
        (gap,) = rig.gap_store.observations
        self.assertEqual(gap.fallback_outcome, FallbackOutcome.BLOCKED)


class TestDeniedIsNotRerouted(unittest.IsolatedAsyncioTestCase):
    """A native capability the run may not use is a permission restriction, not a gap to fill."""

    def rig(self) -> Rig:
        denied = native_evidence("retrieve.denied", permissions_required=["write_repo"])
        elsewhere = native_evidence("retrieve.elsewhere", components=["other-component"])
        return evidence_rig(denied, elsewhere)

    async def test_permission_denial_is_blocked_without_a_host_fallback(self) -> None:
        rig = self.rig()
        _, _, state = await rig.start()
        assessment = next(a for a in state["routing"].values()
                          if a.work_item_id == child(state).id)
        self.assertEqual(assessment.outcome, RoutingOutcome.NO_MATCH)
        self.assertIn(("retrieve.denied", "permission_denied"),
                      [(e.capability_id, e.reason_code) for e in assessment.excluded])
        self.assertEqual(child(state).status, WorkItemStatus.BLOCKED)
        self.assertEqual(state.get("interaction_queue"), [])
        self.assertEqual(state["budgets"].host_operations, 0)
        self.assertEqual(rig.executors["host.research"].invocations, [])
        self.assertIn("denied, not missing: retrieve.denied",
                      " | ".join(state["outcome"].limitations))

    async def test_the_denial_is_a_permission_gap_and_never_a_build_opportunity(self) -> None:
        rig = self.rig()
        await rig.start()
        (gap,) = rig.gap_store.observations
        self.assertEqual((gap.gap_type, gap.fallback_outcome),
                         (GapType.PERMISSION, FallbackOutcome.BLOCKED))
        self.assertFalse(is_build_opportunity(gap))
        self.assertIsNone(gap.proposal)
        self.assertEqual(rig.gap_store.drafts, {})

    async def test_a_side_effect_forbidden_candidate_is_denied_too(self) -> None:
        writer = native_evidence("retrieve.writer", side_effect_class="repo_write")
        rig = evidence_rig(writer, native_evidence("retrieve.elsewhere",
                                                   components=["other-component"]))
        _, _, state = await rig.start()
        self.assertEqual(child(state).status, WorkItemStatus.BLOCKED)
        (gap,) = rig.gap_store.observations
        self.assertEqual(gap.gap_type, GapType.PERMISSION)
        self.assertEqual(state["budgets"].host_operations, 0)


class TestUnavailableIsNotAGap(unittest.IsolatedAsyncioTestCase):
    """A capability that exists but cannot run is blocked with its reason, never a gap."""

    async def test_unavailable_native_capability_is_not_recorded_or_rerouted(self) -> None:
        down = native_evidence("retrieve.down",
                               availability={"status": "unavailable", "reason": "maintenance"})
        rig = evidence_rig(down)
        _, _, state = await rig.start()
        assessment = next(a for a in state["routing"].values()
                          if a.work_item_id == child(state).id)
        self.assertEqual(assessment.outcome, RoutingOutcome.UNAVAILABLE)
        self.assertEqual(child(state).status, WorkItemStatus.BLOCKED)
        self.assertEqual(rig.gap_store.observations, [])
        self.assertEqual(rig.gap_store.drafts, {})
        self.assertEqual(state.get("interaction_queue"), [])
        self.assertEqual(rig.executors["host.research"].invocations, [])
        self.assertTrue(any("unavailable" in t for t in state["outcome"].limitations))

    async def test_denied_plus_unavailable_only_is_unavailable_and_still_no_fallback(self) -> None:
        down = native_evidence("retrieve.down",
                               availability={"status": "unavailable", "reason": "maintenance"})
        denied = native_evidence("retrieve.denied", permissions_required=["write_repo"])
        rig = evidence_rig(down, denied)
        _, _, state = await rig.start()
        self.assertEqual(child(state).status, WorkItemStatus.BLOCKED)
        self.assertEqual(rig.gap_store.observations, [])
        self.assertEqual(state["budgets"].host_operations, 0)


class TestAmbiguousDoesNotFallBack(unittest.IsolatedAsyncioTestCase):
    """Insufficient context is an `ambiguous` observation, never a host fallback."""

    async def test_ambiguous_is_recorded_without_a_draft_and_without_fallback(self) -> None:
        rig = Rig([descriptor("decide.a", routing="semantic", text="Decides caching."),
                   descriptor("decide.b", routing="semantic", text="Decides queues."),
                   host_research()])
        rig.bind("decide.a")
        rig.bind("decide.b")
        rig.bind("host.research")
        rig.config = rig.config.model_copy(update={
            "routing": rig.config.routing.model_copy(update={"on_insufficient_context": "block"})})
        rig.jev.script("kernel.route", "route.*", choice_answer("__NEEDS_CONTEXT__"))
        _, _, state = await rig.start()
        (gap,) = rig.gap_store.observations
        self.assertEqual(gap.gap_type, GapType.AMBIGUOUS)
        self.assertFalse(is_build_opportunity(gap))
        self.assertEqual(rig.gap_store.drafts, {})
        self.assertEqual(state["budgets"].host_operations, 0)
        self.assertEqual(load_kernel_config().host.fallback_on_no_match, True)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:30 [python-coder]: Denial is reproduced with one candidate excluded for
#   permission and another for scope: routing then reports no_match (not unavailable), which is
#   exactly the case where a careless fallback would turn a denial into a missing capability.
#   (#KernelBootstrapV0/P9)
# ====================================================================
