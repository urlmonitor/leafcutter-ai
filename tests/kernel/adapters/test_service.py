"""
MODULE: tests.kernel.adapters.test_service
GOAL: Test KernelService (start, resume, get, cancel) over the real graph, the real sqlite
    checkpointer and the real file stores, with scripted executors and a recording tracer.
BUSINESS CONTEXT: The service owns run.json status and state_revision, the event flush after the
    finish node, rejection handling, the recursion-limit guard and per-call trace segments; a
    client must never see a status the kernel did not durably record.
ARCHITECTURE: Every test builds a temporary run root. Two services over the same root model two
    processes (one checkpoint database, one run store directory).
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.contracts import Actor, ActorKind, RunStatus
from kernel.contracts.enums import ObservabilityStatus
from kernel.interaction import RejectionCode, SubmissionRejected
from kernel.observability.tracer import RecordingTracer
from kernel.service import (
    KernelService,
    ProviderUnavailable,
    RegistryChanged,
    RunIdTaken,
    RunNotFound,
)
from tests.kernel.adapters.support import SegmentTracer, answer, rig_environment
from tests.kernel.interaction.support import host_rig, human_rig, human_submission

HUMAN = Actor(id="human:tester", kind=ActorKind.HUMAN)


class BrokenTracer(SegmentTracer):
    """A tracer whose segment calls fail the way a dead telemetry backend would."""

    def open_segment(self, *args: Any) -> Any:
        """Fail to open."""
        raise RuntimeError("telemetry_down")

    def close_segment(self) -> Any:
        """Fail to close."""
        raise OSError("flush_failed")


class ServiceCase(unittest.IsolatedAsyncioTestCase):
    """A service over a temporary run root and a host-pause rig."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.rig = host_rig()

    def service(self, **kwargs: Any) -> KernelService:
        """Return a service over a fresh environment (one 'process') on the shared root."""
        self.env = rig_environment(self.root, self.rig, **kwargs)
        return KernelService(self.env)

    async def paused(self) -> Any:
        """Start a run that pauses at its host handoff and return its envelope."""
        return await self.service().start_run(self.rig.task_input())


class TestStartAndResume(ServiceCase):
    async def test_start_returns_waiting_host_and_records_run_json(self) -> None:
        env = await self.paused()
        self.assertEqual(env.status, RunStatus.WAITING_HOST)
        packet = env.pending_interaction
        self.assertEqual(packet.operation, "bounded_research")
        self.assertEqual(packet.state_revision, env.state_revision)
        record = self.env.run_store.get_run(env.run_id)
        self.assertEqual(record.status, RunStatus.WAITING_HOST)
        self.assertEqual(record.state_revision, env.state_revision)
        self.assertEqual(record.root_task_id, env.root_task_id)
        self.assertNotEqual(record.root_task_id, "pending")
        self.assertEqual(record.trace.root_observation_id, "seg-1-start")
        self.assertEqual(env.trace_refs.trace_id, record.trace.trace_id)
        self.assertTrue(env.trace_refs.trace_url.startswith("https://trace.example/"))
        self.assertEqual(self.env.tracer.segments[0][2], "start")
        self.assertEqual(self.env.tracer.closed_segments, 1)

    async def test_resume_completes_and_flushes_run_finished(self) -> None:
        paused = await self.paused()
        final = await self.service().resume_run(paused.run_id, answer(paused))
        self.assertEqual(final.status, RunStatus.COMPLETED)
        self.assertIsNotNone(final.output)
        self.assertIsNone(final.pending_interaction)
        kinds = [e.kind for e in self.env.run_store.read_events(paused.run_id)]
        self.assertEqual(kinds[-1], "run.finished")  # the finish node cannot flush its own event
        self.assertEqual(kinds.count("run.finished"), 1)
        record = self.env.run_store.get_run(paused.run_id)
        self.assertEqual(record.status, RunStatus.COMPLETED)
        self.assertGreater(record.state_revision, paused.state_revision)
        report = Path(final.report_ref)
        self.assertTrue(report.is_absolute() and report.name == "report.md" and report.is_file())

    async def test_resume_accepts_a_raw_json_mapping(self) -> None:
        paused = await self.paused()
        raw = answer(paused).model_dump(mode="json")
        final = await self.service().resume_run(paused.run_id, raw)
        self.assertEqual(final.status, RunStatus.COMPLETED)

    async def test_every_call_opens_one_segment_of_its_kind(self) -> None:
        paused = await self.paused()
        service = self.service()
        await service.get_run(paused.run_id)
        await service.resume_run(paused.run_id, answer(paused))
        self.assertEqual([s[2] for s in self.env.tracer.segments], ["status", "resume"])
        self.assertEqual(self.env.tracer.closed_segments, 2)

    async def test_duplicate_run_id_is_refused_without_touching_the_first(self) -> None:
        env = await self.service().start_run(self.rig.task_input(), run_id="run-fixed-1")
        with self.assertRaises(RunIdTaken):
            await self.service().start_run(self.rig.task_input(), run_id="run-fixed-1")
        self.assertEqual(self.env.run_store.get_run("run-fixed-1").status, env.status)


class TestHumanQuestion(ServiceCase):
    def setUp(self) -> None:
        super().setUp()
        self.rig = human_rig()

    async def test_a_human_question_is_delivered_and_answered_with_relay_attribution(self) -> None:
        paused = await self.paused()
        self.assertEqual(paused.status, RunStatus.WAITING_HUMAN)
        question = paused.pending_interaction
        self.assertEqual([c.id for c in question.choices], ["sqlite", "files"])
        self.assertTrue(question.why_research_cannot_settle)
        raw = human_submission(question.model_dump(mode="json"), paused.run_id,
                               {"choice_id": "sqlite"}, relayed_by="claude_code")
        final = await self.service().resume_run(paused.run_id, raw)
        self.assertEqual(final.status, RunStatus.COMPLETED)
        stored = self.env.run_store.get_submission(paused.run_id, question.id)
        self.assertEqual(stored.submission.relayed_by, "claude_code")

    async def test_a_host_cannot_answer_a_human_question(self) -> None:
        paused = await self.paused()
        raw = human_submission(paused.pending_interaction.model_dump(mode="json"),
                               paused.run_id, {"choice_id": "sqlite"})
        raw["actor"] = {"id": "claude_code", "kind": "host"}
        with self.assertRaises(SubmissionRejected):
            await self.service().resume_run(paused.run_id, raw)
        self.assertEqual((await self.service().get_run(paused.run_id)).status,
                         RunStatus.WAITING_HUMAN)


class TestGetAndCancel(ServiceCase):
    async def test_get_run_is_read_only(self) -> None:
        paused = await self.paused()
        before = self.env.run_store.get_run(paused.run_id)
        seen = await self.service().get_run(paused.run_id)
        self.assertEqual(seen.status, RunStatus.WAITING_HOST)
        self.assertEqual(seen.pending_interaction.id, paused.pending_interaction.id)
        self.assertEqual(self.env.run_store.get_run(paused.run_id), before)

    async def test_unknown_run_raises_run_not_found(self) -> None:
        service = self.service()
        with self.assertRaises(RunNotFound):
            await service.get_run("run-nope")
        with self.assertRaises(RunNotFound):
            await service.resume_run("run-nope", {})
        with self.assertRaises(RunNotFound):
            await service.cancel_run("run-nope", HUMAN)

    async def test_cancel_marks_cancelled_and_refuses_later_submissions(self) -> None:
        paused = await self.paused()
        cancelled = await self.service().cancel_run(paused.run_id, HUMAN)
        self.assertEqual(cancelled.status, RunStatus.CANCELLED)
        self.assertIsNone(cancelled.pending_interaction)
        record = self.env.run_store.get_run(paused.run_id)
        self.assertEqual(record.cancel.by, "human:tester")
        with self.assertRaises(SubmissionRejected) as caught:
            await self.service().resume_run(paused.run_id, answer(paused))
        self.assertEqual(caught.exception.code, RejectionCode.CANCELLED_OR_SUPERSEDED)
        self.assertEqual(caught.exception.envelope.status, RunStatus.CANCELLED)

    async def test_cancel_is_idempotent_and_keeps_the_first_actor(self) -> None:
        paused = await self.paused()
        await self.service().cancel_run(paused.run_id, HUMAN)
        first = self.env.run_store.get_run(paused.run_id).cancel
        other = Actor(id="human:other", kind=ActorKind.HUMAN)
        again = await self.service().cancel_run(paused.run_id, other)
        self.assertEqual(again.status, RunStatus.CANCELLED)
        self.assertEqual(self.env.run_store.get_run(paused.run_id).cancel, first)

    async def test_cancelling_a_finished_run_leaves_it_finished(self) -> None:
        paused = await self.paused()
        await self.service().resume_run(paused.run_id, answer(paused))
        env = await self.service().cancel_run(paused.run_id, HUMAN)
        self.assertEqual(env.status, RunStatus.COMPLETED)
        self.assertIsNone(self.env.run_store.get_run(paused.run_id).cancel)


class TestRejections(ServiceCase):
    async def test_rejection_carries_the_current_envelope_and_changes_nothing(self) -> None:
        paused = await self.paused()
        before = self.env.run_store.get_run(paused.run_id)
        stale = answer(paused, revision=paused.state_revision + 5)
        with self.assertRaises(SubmissionRejected) as caught:
            await self.service().resume_run(paused.run_id, stale)
        exc = caught.exception
        self.assertEqual(exc.code, RejectionCode.STALE_REVISION)
        self.assertEqual(exc.envelope.status, RunStatus.WAITING_HOST)
        self.assertEqual(exc.envelope.pending_interaction.id, paused.pending_interaction.id)
        self.assertEqual(self.env.run_store.get_run(paused.run_id).state_revision,
                         before.state_revision)
        final = await self.service().resume_run(paused.run_id, answer(paused))  # still resumable
        self.assertEqual(final.status, RunStatus.COMPLETED)

    async def test_invalid_host_output_is_rejected_with_the_packet_to_repair(self) -> None:
        paused = await self.paused()
        bad = answer(paused, response={"evidence": "not a list"})
        with self.assertRaises(SubmissionRejected) as caught:
            await self.service().resume_run(paused.run_id, bad)
        exc = caught.exception
        self.assertIn(exc.code, (RejectionCode.SCHEMA_INVALID, RejectionCode.SEMANTIC_INVALID))
        self.assertEqual(exc.details["pending_interaction"]["id"], paused.pending_interaction.id)
        self.assertEqual(exc.envelope.status, RunStatus.WAITING_HOST)

    async def test_a_changed_registry_refuses_to_continue_a_pinned_run(self) -> None:
        paused = await self.paused()
        service = self.service()
        self.env.snapshot = self.env.snapshot.model_copy(update={"content_hash": "x" * 16})
        with self.assertRaises(RegistryChanged):
            await service.resume_run(paused.run_id, answer(paused))
        self.assertEqual(self.env.run_store.get_run(paused.run_id).status,
                         RunStatus.WAITING_HOST)


class TestProviderAndObservability(ServiceCase):
    async def test_without_a_jev_credential_start_fails_before_creating_a_run(self) -> None:
        with self.assertRaises(ProviderUnavailable):
            await self.service(with_jev=False).start_run(self.rig.task_input())
        self.assertEqual(self.env.run_store.list_run_ids(), [])

    async def test_status_and_cancel_need_no_jev(self) -> None:
        paused = await self.paused()
        service = self.service(with_jev=False)
        self.assertEqual((await service.get_run(paused.run_id)).status, RunStatus.WAITING_HOST)
        self.assertEqual((await service.cancel_run(paused.run_id, HUMAN)).status,
                         RunStatus.CANCELLED)

    async def test_degraded_observability_is_reported_and_does_not_break_the_run(self) -> None:
        tracer = RecordingTracer(status=ObservabilityStatus.DEGRADED)
        paused = await self.service(tracer=tracer).start_run(self.rig.task_input())
        self.assertEqual(paused.status, RunStatus.WAITING_HOST)
        self.assertEqual(paused.trace_refs.observability, ObservabilityStatus.DEGRADED)
        second = RecordingTracer(status=ObservabilityStatus.DEGRADED)
        final = await self.service(tracer=second).resume_run(paused.run_id, answer(paused))
        self.assertEqual(final.status, RunStatus.COMPLETED)

    async def test_a_tracer_that_cannot_open_or_close_a_segment_keeps_the_run_going(self) -> None:
        env = await self.service(tracer=BrokenTracer()).start_run(self.rig.task_input())
        self.assertEqual(env.status, RunStatus.WAITING_HOST)
        self.assertEqual(env.trace_refs.observability, ObservabilityStatus.DEGRADED)
        self.assertEqual(len(env.trace_refs.trace_id), 32)

    async def test_jev_is_built_and_closed_in_the_running_loop_only_when_routing(self) -> None:
        events: list[tuple[str, Any]] = []

        class Closing:
            async def aclose(self) -> None:
                events.append(("closed", asyncio.get_running_loop()))

        def factory() -> Closing:
            events.append(("built", asyncio.get_running_loop()))
            return Closing()

        loop = asyncio.get_running_loop()
        service = self.service()
        self.env.jev_factory = factory
        paused = await service.start_run(self.rig.task_input())
        await service.get_run(paused.run_id)  # a status segment must not build an adapter
        self.assertEqual([name for name, _ in events], ["built", "closed"])
        self.assertTrue(all(lp is loop for _, lp in events))


class TestRecursionLimit(ServiceCase):
    async def test_a_tripped_recursion_limit_is_blocked_with_diagnostics(self) -> None:
        service = self.service(langgraph_recursion_limit=3)
        env = await service.start_run(self.rig.task_input())
        self.assertEqual(env.status, RunStatus.BLOCKED)
        self.assertTrue(any("langgraph_recursion_limit" in text for text in env.limitations))
        self.assertIsNone(env.pending_interaction)
        record = self.env.run_store.get_run(env.run_id)
        self.assertEqual(record.status, RunStatus.BLOCKED)
        again = await self.service(langgraph_recursion_limit=3).get_run(env.run_id)
        self.assertEqual(again.status, RunStatus.BLOCKED)  # the record, not the checkpoint, wins


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 13:20 [python-coder]: The recursion-limit test sets a real limit of 3 instead of
#   patching LangGraph, so it proves the mapping of the genuine GraphRecursionError.
#   (#KernelBootstrapV0/P7)
# ====================================================================
