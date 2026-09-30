"""
MODULE: tests.kernel.contracts.test_ports_and_fakes
GOAL: Test the port test doubles P2-P9 rely on: ScriptedJev, the in-memory run/gap/artifact
    stores, gap aggregation, the execution context/budget, the scripted executor and the
    service helpers.
BUSINESS CONTEXT: Later phases substitute these doubles for real providers and stores, so their
    behaviour (failures, ordering, idempotency, name validation) must be dependable.
ARCHITECTURE: asyncio.run drives async ports; everything is offline.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from kernel.capabilities import CapabilityExecutor, UnlimitedBudget
from kernel.contracts import CapabilityGap, RunEvent
from kernel.contracts.base import new_id
from kernel.contracts.enums import RunStatus
from kernel.persistence import (
    InvalidArtifactName,
    MemoryArtifactStore,
    MemoryGapStore,
    MemoryRunStore,
    RunAlreadyExists,
    RunNotFound,
    RunRecord,
    aggregate_gaps,
)
from kernel.providers import (
    JevBatch,
    JevInvalidResponse,
    JevPort,
    JevUnavailable,
    QuestionSpec,
    ScriptedJev,
    choice_answer,
    noul_answer,
)
from kernel.service import error_payload, new_envelope
from tests.kernel.helpers import (
    ScriptedExecutor,
    completed_result,
    make_context,
    make_evidence,
    make_invocation,
)


def _batch(purpose: str = "route", *ids: str) -> JevBatch:
    questions = [QuestionSpec(id=i, kind="noul", template_id="t", template_version="1",
                              instructions="Is x true?") for i in (ids or ("q1",))]
    return JevBatch(purpose=purpose, state={"x": 1}, questions=questions)


class TestScriptedJev(unittest.TestCase):
    """ScriptedJev as a JevPort."""

    def test_answers_by_globs_and_fills_question_ids(self) -> None:
        jev = ScriptedJev().script("route", "route.*", choice_answer("decision"))
        jev.script("assess", "sufficient.*", noul_answer(0.9))
        result = asyncio.run(jev.assess(_batch("route", "route.work-1")))
        self.assertEqual(result.choice("route.work-1").choice, "decision")
        self.assertEqual(result.answers["route.work-1"].question_id, "route.work-1")
        again = asyncio.run(jev.assess(_batch("assess", "sufficient.c1")))
        self.assertEqual(again.noul("sufficient.c1").probability, 0.9)

    def test_port_conformance_and_recording(self) -> None:
        jev = ScriptedJev().script("*", "*", noul_answer(0.1))
        self.assertIsInstance(jev, JevPort)
        asyncio.run(jev.assess(_batch("p1", "a", "b")))
        asyncio.run(jev.assess(_batch("p2", "c")))
        self.assertEqual(jev.call_count, 2)
        self.assertEqual(jev.questions_asked(), ["a", "b", "c"])
        self.assertEqual(jev.questions_asked("p2"), ["c"])

    def test_unscripted_question_fails_loudly(self) -> None:
        with self.assertRaises(JevInvalidResponse):
            asyncio.run(ScriptedJev().assess(_batch()))

    def test_fail_next_raises_then_recovers_and_still_records(self) -> None:
        jev = ScriptedJev().script("*", "*", noul_answer(0.5))
        jev.fail_next(JevUnavailable("down"), times=2)
        for _ in range(2):
            with self.assertRaises(JevUnavailable):
                asyncio.run(jev.assess(_batch()))
        self.assertEqual(asyncio.run(jev.assess(_batch())).noul("q1").probability, 0.5)
        self.assertEqual(jev.call_count, 3)

    def test_callable_answers_see_the_question(self) -> None:
        jev = ScriptedJev().script("*", "*", lambda q, b: noul_answer(0.7 if q.id == "hi" else 0.2))
        result = asyncio.run(jev.assess(_batch("p", "hi", "lo")))
        self.assertEqual((result.noul("hi").probability, result.noul("lo").probability),
                         (0.7, 0.2))

    def test_unknown_usage_stays_none(self) -> None:
        usage = asyncio.run(ScriptedJev().script("*", "*", noul_answer(1.0)).assess(_batch())
                            ).usage
        self.assertIsNone(usage.input_tokens)
        self.assertIsNone(usage.cost_usd)

    def test_input_fingerprint_is_stable_and_state_sensitive(self) -> None:
        a, b = _batch(), _batch().model_copy(update={"state": {"x": 2}})
        self.assertEqual(a.input_fingerprint(), _batch().input_fingerprint())
        self.assertNotEqual(a.input_fingerprint(), b.input_fingerprint())


def _record(run_id: str) -> RunRecord:
    return RunRecord(run_id=run_id, root_task_id=new_id("task"))


class TestMemoryRunStore(unittest.TestCase):
    """MemoryRunStore semantics the file store must share."""

    def test_create_get_update_and_errors(self) -> None:
        store = MemoryRunStore()
        store.create_run(_record("run-1"))
        with self.assertRaises(RunAlreadyExists):
            store.create_run(_record("run-1"))
        updated = store.get_run("run-1").model_copy(update={"status": RunStatus.WAITING_HOST})
        store.update_run(updated)
        self.assertEqual(store.get_run("run-1").status, RunStatus.WAITING_HOST)
        with self.assertRaises(RunNotFound):
            store.get_run("nope")
        with self.assertRaises(RunNotFound):
            store.update_run(_record("nope"))
        self.assertEqual(store.list_run_ids(), ["run-1"])

    def test_cancel_flag(self) -> None:
        store = MemoryRunStore()
        store.create_run(_record("run-1"))
        self.assertFalse(store.is_cancelled("run-1"))
        cancelled = store.get_run("run-1").model_copy(update={
            "cancel": {"by": "human:u", "at": datetime.now(UTC)}})
        store.update_run(cancelled)
        self.assertTrue(store.is_cancelled("run-1"))

    def test_events_are_ordered_and_filtered(self) -> None:
        store = MemoryRunStore()
        for seq in (2, 0, 1):
            store.append_event(RunEvent(seq=seq, run_id="run-1", kind="k", at=datetime.now(UTC)))
        self.assertEqual([e.seq for e in store.read_events("run-1")], [0, 1, 2])
        self.assertEqual([e.seq for e in store.read_events("run-1", after_seq=0)], [1, 2])
        self.assertEqual(store.read_events("other"), [])


class TestGapAggregation(unittest.TestCase):
    """aggregate_gaps and MemoryGapStore."""

    def _gap(self, key: str, run: str, when: datetime, count: int = 1) -> CapabilityGap:
        return CapabilityGap(
            id=new_id("gap"), gap_key=key * 8, gap_type="unsupported", goal="g",
            normalized_need="n", request_kind="capability", input_schema="i.v1",
            output_schema="o.v1", occurrence_count=count, example_run_ids=[run],
            first_seen=when, last_seen=when)

    def test_merges_by_key_sums_counts_and_bounds_examples(self) -> None:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        obs = [self._gap("a", f"run-{i}", t0 + timedelta(hours=i)) for i in range(7)]
        obs.append(self._gap("b", "run-x", t0, count=3))
        merged = {g.gap_key: g for g in aggregate_gaps(obs)}
        a = merged["a" * 8]
        self.assertEqual(a.occurrence_count, 7)
        self.assertEqual(a.example_run_ids, [f"run-{i}" for i in range(5)])
        self.assertEqual((a.first_seen, a.last_seen), (t0, t0 + timedelta(hours=6)))
        self.assertEqual(merged["b" * 8].occurrence_count, 3)
        self.assertEqual(sorted(merged), ["a" * 8, "b" * 8])

    def test_store_records_and_aggregates_and_writes_drafts(self) -> None:
        store = MemoryGapStore()
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        store.record(self._gap("a", "run-1", t0))
        store.record(self._gap("a", "run-2", t0))
        (gap,) = store.load_gaps()
        self.assertEqual(gap.occurrence_count, 2)
        ref = store.write_draft(gap, "# draft")
        self.assertEqual(store.drafts[ref], "# draft")


class TestArtifactsAndContext(unittest.TestCase):
    """Artifact names, execution context and budget."""

    def test_artifact_roundtrip_and_name_validation(self) -> None:
        store = MemoryArtifactStore()
        ref = store.write_artifact("run-1", "report.md", "hello")
        self.assertEqual(store.read_artifact("run-1", ref.ref), b"hello")
        self.assertEqual(ref.size_bytes, 5)
        self.assertIsNone(store.absolute_path("run-1", ref.ref))
        for bad in ("../x", "a/b", "", ".hidden", "x" * 200):
            with self.subTest(name=bad), self.assertRaises(InvalidArtifactName):
                store.write_artifact("run-1", bad, "x")
        with self.assertRaises(KeyError):
            store.read_artifact("run-1", "missing.md")

    def test_context_resolves_evidence_in_order_and_skips_unknown(self) -> None:
        one, two = make_evidence("a.md#L1", "one"), make_evidence("b.md#L1", "two")
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(Path(tmp), evidence=[one, two])
            got = ctx.evidence([two.id, "ev-ffffffffffffffff", one.id])
            self.assertEqual([e.id for e in got], [two.id, one.id])
            self.assertFalse(ctx.cancelled())
            self.assertTrue(make_context(Path(tmp), cancelled=True).cancelled())

    def test_unlimited_budget_counts(self) -> None:
        budget = UnlimitedBudget()
        self.assertTrue(budget.reserve("jev"))
        self.assertTrue(budget.reserve("jev"))
        self.assertEqual(budget.reserved["jev"], 2)

    def test_scripted_executor_returns_scripted_then_factory_results(self) -> None:
        invocation = make_invocation()
        first = completed_result(invocation)
        executor = ScriptedExecutor([first])
        self.assertIsInstance(executor, CapabilityExecutor)
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(Path(tmp))
            self.assertIs(asyncio.run(executor.ainvoke(invocation, ctx)), first)
            second = asyncio.run(executor.ainvoke(invocation, ctx))
        self.assertEqual(second.invocation_id, invocation.id)
        self.assertEqual(len(executor.invocations), 2)


class TestServiceHelpers(unittest.TestCase):
    """Envelope builder and CLI error payload."""

    def test_new_envelope_enforces_invariants(self) -> None:
        env = new_envelope("run-1", "task-1", 4, RunStatus.PARTIAL, limitations=["x"])
        self.assertEqual((env.state_revision, env.limitations), (4, ["x"]))
        with self.assertRaises(ValueError):
            new_envelope("run-1", "task-1", 4, RunStatus.WAITING_HOST)

    def test_error_payload_shape(self) -> None:
        payload = error_payload("stale_submission", "old", {"expected": "3"})
        self.assertEqual(payload["error"], {"code": "stale_submission", "message": "old",
                                            "details": {"expected": "3"}})
        self.assertIsNone(payload["envelope"])
        env = new_envelope("run-1", "task-1", 1, RunStatus.RUNNING)
        self.assertEqual(error_payload("x", "y", envelope=env)["envelope"]["run_id"], "run-1")


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Doubles are tested for failure semantics (unscripted
#   questions raise, queued failures still record the batch) because later tests depend on them.
#   (#KernelBootstrapV0/P1)
# ====================================================================
