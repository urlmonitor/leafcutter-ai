"""
MODULE: tests.kernel.scheduler.test_lifecycle
GOAL: Test the run bookends and the ports the scheduler writes to: intake normalisation, event
    persistence, tracer spans, capability timeout and best-effort report and gap writes.
BUSINESS CONTEXT: A run must be reconstructable from its events, traceable, and must survive a
    failing report or gap store without losing its outcome (Rev 3 sections 13 and 14).
ARCHITECTURE: Drives the compiled graph with the P1 doubles; failing ports are small subclasses
    of the memory stores that raise OSError.
"""

from __future__ import annotations

import asyncio
import types
import unittest

from kernel.contracts import (
    EvidenceCategory,
    RequestKind,
    RunStatus,
    SourceKind,
    schema_ids,
)
from kernel.persistence.memory import MemoryArtifactStore, MemoryGapStore
from kernel.providers.fakes import choice_answer
from kernel.service import new_envelope
from kernel.scheduler.nodes_lifecycle import intake
from tests.kernel.scheduler.test_interaction_basic import _host_rig
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    event_kinds,
    proposal,
    retrieval_descriptor,
    root_item,
    two_phase,
    waiting,
    with_limits,
)


class _DiskFull(OSError):
    """Simulated storage failure."""

    def __init__(self) -> None:
        super().__init__("disk full")


class _FailingArtifacts(MemoryArtifactStore):
    def write_artifact(self, run_id, name, content):
        raise _DiskFull


class _FailingGapStore(MemoryGapStore):
    def record(self, gap):
        raise _DiskFull


class _Slow:
    """Executor that never answers within the timeout."""

    def __init__(self) -> None:
        self.invocations: list = []

    async def ainvoke(self, invocation, ctx):
        self.invocations.append(invocation)
        await asyncio.sleep(5)
        return completed(invocation)


def _simple() -> Rig:
    rig = Rig([descriptor("decide.root")])
    rig.bind("decide.root")
    return rig


class TestIntake(unittest.IsolatedAsyncioTestCase):
    """TaskInput becomes a task, a root request, a root work item and initial evidence."""

    async def test_initial_evidence_and_root_request(self) -> None:
        rig = _simple()
        _, _, state = await rig.start(initial_evidence=[
            {"title": "Note", "excerpt": "Sqlite is already used.", "locator": "notes.md#L1"}])
        (evidence,) = state["evidence"].values()
        self.assertEqual(evidence.category, EvidenceCategory.TASK_CONTEXT)
        self.assertEqual(evidence.source.kind, SourceKind.TASK_INPUT)
        root = root_item(state)
        request = state["requests"][root.request_id]
        self.assertEqual((root.depth, root.status.value), (0, "completed"))
        self.assertEqual(request.kind, RequestKind.CAPABILITY)
        self.assertEqual(request.payload_schema, schema_ids.GOAL_REQUEST)
        self.assertEqual(request.context_refs, [evidence.id])
        self.assertEqual(state["task"].requested_output_schema, schema_ids.DECISION_REPORT)
        self.assertEqual(state["budgets"].work_items_created, 1)

    async def test_supplied_input_payload_becomes_the_root_request_payload(self) -> None:
        rig = Rig([descriptor("decide.root", accepts=schema_ids.DECISION_REQUEST)])
        rig.bind("decide.root")
        payload = {"question": "Which store?", "criteria_missing": True}
        _, _, state = await rig.start(input_payload_schema=schema_ids.DECISION_REQUEST,
                                      input_payload=payload)
        request = state["requests"][root_item(state).request_id]
        self.assertEqual(request.payload_schema, schema_ids.DECISION_REQUEST)
        self.assertEqual(request.payload["question"], "Which store?")

    async def test_intake_does_nothing_when_the_task_exists(self) -> None:
        rig = _simple()
        _, _, state = await rig.start()
        runtime = types.SimpleNamespace(context=rig.runtime())
        update = await intake(state, runtime)
        self.assertEqual(set(update), {"budgets"})
        self.assertEqual(update["budgets"].work_items_created, 1)


class TestPortsAndTrace(unittest.IsolatedAsyncioTestCase):
    """Events, spans and best-effort writes."""

    async def test_events_are_persisted_with_increasing_sequence(self) -> None:
        rig = _simple()
        _, _, state = await rig.start()
        stored = rig.run_store.read_events(state["run_id"])
        self.assertEqual([e.seq for e in state["events"]], list(range(len(state["events"]))))
        self.assertEqual([e.kind for e in stored], event_kinds(state)[:len(stored)])
        self.assertGreaterEqual(len(stored), len(state["events"]) - 1)
        self.assertEqual(state["events"][-1].kind, "run.finished")

    async def test_kernel_nodes_are_traced_and_time_is_accounted(self) -> None:
        rig = _simple()
        _, _, state = await rig.start()
        for name in ("kernel.intake", "kernel.schedule", "kernel.route", "kernel.integrate",
                     "kernel.finalize", "capability.decide.root"):
            spans = rig.tracer.named(name, "span")
            self.assertTrue(spans and all(s.closed for s in spans), name)
        self.assertGreater(state["budgets"].active_seconds, 0)

    async def test_report_write_failure_is_a_limitation_not_a_crash(self) -> None:
        rig = _simple()
        rig.artifacts = _FailingArtifacts()
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        self.assertIsNone(state["outcome"].report_ref)
        self.assertIn("report_not_written", state["outcome"].limitations)

    async def test_gap_store_failure_still_blocks_the_item(self) -> None:
        rig = Rig([descriptor("decide.other", kinds=("options",))])
        rig.bind("decide.other")
        rig.gap_store = _FailingGapStore()
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertIn("gap.record_failed", event_kinds(state))


def _envelope(state: dict):
    """Build a RunEnvelope from graph state the way the P7 service will."""
    outcome = state.get("outcome")
    queue = state.get("interaction_queue", [])
    pending = None if outcome or not queue else state["interactions"][queue[0]]
    return new_envelope(
        state["run_id"], state["root_task_id"], state["state_revision"],
        outcome.status if outcome else state["status"], output=outcome.output if outcome else None,
        pending_interaction=pending, limitations=outcome.limitations if outcome else [],
        errors=outcome.errors if outcome else [])


class TestEnvelopeSeam(unittest.IsolatedAsyncioTestCase):
    """The final or paused state maps onto a valid RunEnvelope without further computation."""

    async def test_completed_blocked_and_paused_states_build_valid_envelopes(self) -> None:
        done = _simple()
        blocked = Rig([descriptor("decide.other", kinds=("options",))])
        blocked.bind("decide.other")
        paused = _host_rig()
        envelopes = [_envelope((await done.start())[2]), _envelope((await blocked.start())[2]),
                     _envelope((await paused.start())[2])]
        self.assertEqual([e.status for e in envelopes],
                         [RunStatus.COMPLETED, RunStatus.BLOCKED, RunStatus.WAITING_HOST])
        self.assertIsNotNone(envelopes[0].output)
        self.assertIsNotNone(envelopes[2].pending_interaction)
        self.assertEqual(envelopes[2].pending_interaction.state_revision,
                         envelopes[2].state_revision)


class TestTimeoutAndBatching(unittest.IsolatedAsyncioTestCase):
    """Capability timeout is transient; semantic routing shares one Jev call."""

    async def test_capability_timeout_is_retried_then_fails(self) -> None:
        rig = Rig([descriptor("decide.root")])
        slow = rig.bind("decide.root", _Slow())
        rig.config = with_limits(rig.config, capability_timeout_seconds=0.05, max_retries=1)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.FAILED)
        self.assertEqual(state["outcome"].errors[0].code, "timeout")
        self.assertEqual(len(slow.invocations), 2)

    async def test_semantic_routing_of_siblings_shares_one_jev_call(self) -> None:
        rig = Rig([descriptor("decide.root"), retrieval_descriptor("retrieve.a", "semantic"),
                   retrieval_descriptor("retrieve.b", "semantic")])
        rig.bind("decide.root", factory=two_phase(lambda inv: waiting(
            inv, proposal("prior_decisions", "Which store does the cache use?"),
            proposal("internal_principles", "Which principles apply?")), completed))
        rig.bind("retrieve.a", factory=lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE))
        rig.bind("retrieve.b", factory=lambda inv: completed(inv, schema_ids.EVIDENCE_BUNDLE))
        rig.jev.script("kernel.route", "route.*", choice_answer("retrieve.a", 0.95, 0.9))
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        routing_batches = [b for b in rig.jev.batches if b.purpose == "kernel.route"]
        self.assertEqual(len(routing_batches), 1, "the root is routed fixed, without Jev")
        self.assertEqual(len(routing_batches[0].questions), 2)
        self.assertEqual(state["budgets"].jev_calls, 1)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:40 [python-coder]: Port failures are simulated by subclassing the memory
#   stores so the real nodes hit a real OSError path. (#KernelBootstrapV0/P4)
# ====================================================================
