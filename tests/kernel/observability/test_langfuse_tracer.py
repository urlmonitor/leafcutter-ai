"""
MODULE: tests.kernel.observability.test_langfuse_tracer
GOAL: Test LangfuseTracer against the real Langfuse 4.x SDK with an in-memory OpenTelemetry
    exporter: one deterministic trace per run, segment continuity across restarts, nesting,
    correlation ids, redaction before export, error marking, and degraded mode with spooling.
BUSINESS CONTEXT: Traces are the audit trail; they must be inspectable, survive process restarts,
    never leak secrets, and never fail or erase a run when Langfuse is unavailable.
ARCHITECTURE: unittest. Each test uses a unique public key because the SDK keeps one client per
    key. The exporter is injected, so nothing touches the network (auth_check and URL lookup are
    disabled or patched). Keys are built at runtime to keep the secret scanner quiet.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest import mock

from langfuse import Langfuse
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import SecretStr

from kernel.config import load_kernel_config
from kernel.contracts.base import CorrelationIds
from kernel.contracts.capability import Usage
from kernel.contracts.enums import ObservabilityStatus
from kernel.observability import Tracer, deterministic_trace_id
from kernel.observability.langfuse_tracer import LangfuseTracer
from kernel.secrets import SecretSettings
from tests.kernel.helpers import narrow


class _BoomError(ValueError):
    """Error raised inside a span body."""

    def __init__(self) -> None:
        super().__init__("bad input")


RUN = "run-0123456789abcdef"
TASK = "task-0123456789abcdef"
CONFIG = load_kernel_config()


class _Harness(unittest.TestCase):
    """Builds tracers that export to an in-memory exporter and spool into a temp dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.exporter = InMemorySpanExporter()
        self.public = "pk-" + uuid.uuid4().hex[:12]
        self.secret = "sk-" + uuid.uuid4().hex[:12]
        self.corr = CorrelationIds(run_id=RUN, root_task_id=TASK, work_item_id="work-1",
                                   invocation_id="inv-1", capability_id="retrieve.repository")

    def make(self, *, with_keys: bool = True, enabled: bool = True, verify_auth: bool = False,
             public: str | None = None) -> LangfuseTracer:
        fields: dict = {"langfuse_base_url": "http://127.0.0.1:9"}
        if with_keys:
            fields["langfuse_public_key"] = SecretStr(public or self.public)
            fields["langfuse_secret_key"] = SecretStr(self.secret)
        config = CONFIG.langfuse.model_copy(update={"enabled": enabled})
        return LangfuseTracer(
            secrets=SecretSettings(**fields), config=config, policy=CONFIG.data_policy,
            deny_globs=CONFIG.retrieval.deny_globs, spool_path=self.dir / "spool.jsonl",
            span_exporter=self.exporter, verify_auth=verify_auth, resolve_url=False)

    def spans(self) -> dict[str, list]:
        by_name: dict[str, list] = {}
        for span in self.exporter.get_finished_spans():
            by_name.setdefault(span.name, []).append(span)
        return by_name

    @staticmethod
    def attrs(span: Any) -> dict:
        return dict(span.attributes)

    @staticmethod
    def meta(span: Any) -> dict:
        prefix = "langfuse.observation.metadata."
        return {k[len(prefix):]: v for k, v in dict(span.attributes).items()
                if k.startswith(prefix)}


class TestTraceStructure(_Harness):
    """Real SDK spans: identity, nesting, correlation."""

    def test_satisfies_the_port(self) -> None:
        self.assertIsInstance(self.make(), Tracer)

    def test_segment_uses_the_deterministic_trace_id_and_reports_ok(self) -> None:
        tracer = self.make()
        state = tracer.open_segment(RUN, TASK, "start")
        self.assertEqual(state.trace_id, deterministic_trace_id(RUN))
        self.assertEqual(state.trace_id, Langfuse.create_trace_id(seed=RUN))
        self.assertIsNotNone(state.root_observation_id)
        self.assertEqual(tracer.close_segment(), ObservabilityStatus.OK)
        (root,) = self.spans()["leafcutter.run"]
        self.assertEqual(format(root.context.trace_id, "032x"), state.trace_id)
        self.assertEqual(format(root.context.span_id, "016x"), state.root_observation_id)
        attrs = self.attrs(root)
        self.assertEqual(attrs["session.id"], RUN)
        self.assertEqual(attrs["langfuse.trace.name"], CONFIG.langfuse.trace_name)
        self.assertIn("leafcutter-kernel", attrs["langfuse.trace.tags"])
        self.assertEqual(attrs["langfuse.observation.type"], "agent")

    def test_restart_appends_a_new_segment_to_the_same_trace(self) -> None:
        first = self.make()
        first.open_segment(RUN, TASK, "start")
        first.close_segment()
        second = self.make()
        state = second.open_segment(RUN, TASK, "resume")
        second.close_segment()
        start, resume = self.spans()["leafcutter.run"][0], self.spans()["leafcutter.run.resume"][0]
        self.assertEqual(start.context.trace_id, resume.context.trace_id)
        self.assertNotEqual(start.context.span_id, resume.context.span_id)
        self.assertEqual(state.trace_id, format(resume.context.trace_id, "032x"))

    def test_spans_nest_and_carry_non_null_correlation_ids_only(self) -> None:
        tracer = self.make()
        state = tracer.open_segment(RUN, TASK, "start")
        with tracer.span("kernel.route", "chain", self.corr, input={"q": 1}) as outer:
            outer.update(output={"ok": True})
            with tracer.span("capability.retrieve.repository", "tool", self.corr):
                tracer.event("gap.recorded", self.corr, level="WARNING", payload={"n": 1})
        tracer.close_segment()
        spans = self.spans()
        route = spans["kernel.route"][0]
        cap = spans["capability.retrieve.repository"][0]
        event = spans["gap.recorded"][0]
        root_id = int(narrow(state.root_observation_id), 16)
        self.assertEqual(route.parent.span_id, root_id)
        self.assertEqual(cap.parent.span_id, route.context.span_id)
        self.assertEqual(event.parent.span_id, cap.context.span_id)
        meta = self.meta(route)
        self.assertEqual(meta["run_id"], RUN)
        self.assertEqual(meta["invocation_id"], "inv-1")
        self.assertEqual(meta["capability_id"], "retrieve.repository")
        self.assertNotIn("decision_id", meta)
        self.assertEqual(json.loads(self.attrs(route)["langfuse.observation.output"]),
                         {"ok": True})
        self.assertEqual(self.attrs(event)["langfuse.observation.level"], "WARNING")

    def test_generation_records_model_usage_and_cost_provenance(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        usage = Usage(provider="jev", input_tokens=3, output_tokens=4, cost_usd=0.5,
                      cost_provenance="estimated")
        tracer.generation("jev.routing", self.corr, model="jev-latest", input="in",
                          output="out", usage=usage)
        tracer.generation("jev.unknown", self.corr, model="jev-latest", input="in",
                          output="out", usage=None)
        tracer.close_segment()
        known = self.attrs(self.spans()["jev.routing"][0])
        self.assertEqual(known["langfuse.observation.model.name"], "jev-latest")
        self.assertEqual(json.loads(known["langfuse.observation.usage_details"]),
                         {"input": 3, "output": 4})
        self.assertEqual(json.loads(known["langfuse.observation.cost_details"]), {"total": 0.5})
        self.assertEqual(self.meta(self.spans()["jev.routing"][0])["cost_provenance"],
                         "estimated")
        unknown = self.attrs(self.spans()["jev.unknown"][0])
        self.assertNotIn("langfuse.observation.usage_details", unknown)

    def test_concurrent_tasks_parent_to_their_own_span(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")

        async def worker(name: str) -> None:
            with tracer.span(f"worker.{name}", "chain", self.corr):
                await asyncio.sleep(0)
                tracer.event(f"event.{name}", self.corr)
                await asyncio.sleep(0)

        async def main() -> None:
            await asyncio.gather(worker("a"), worker("b"))

        asyncio.run(main())
        tracer.close_segment()
        spans = self.spans()
        for name in ("a", "b"):
            self.assertEqual(spans[f"event.{name}"][0].parent.span_id,
                             spans[f"worker.{name}"][0].context.span_id)

    def test_exception_in_span_marks_error_and_propagates(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        with self.assertRaises(_BoomError), tracer.span("kernel.boom", "chain", self.corr):
            raise _BoomError
        self.assertEqual(tracer.close_segment(), ObservabilityStatus.OK)
        attrs = self.attrs(self.spans()["kernel.boom"][0])
        self.assertEqual(attrs["langfuse.observation.level"], "ERROR")
        self.assertIn("bad input", attrs["langfuse.observation.status_message"])

    def test_trace_context_points_at_the_current_span(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        with tracer.span("kernel.route", "chain", self.corr):
            context = tracer.trace_context(self.corr)
        tracer.close_segment()
        self.assertEqual(context.trace_id, deterministic_trace_id(RUN))
        self.assertEqual(context.parent_observation_id,
                         format(self.spans()["kernel.route"][0].context.span_id, "016x"))

    def test_langchain_callbacks_bind_to_the_trace(self) -> None:
        tracer = self.make()
        self.assertEqual(tracer.langchain_callbacks(self.corr), [])
        tracer.open_segment(RUN, TASK, "start")
        handlers = tracer.langchain_callbacks(self.corr)
        tracer.close_segment()
        self.assertEqual(len(handlers), 1)

    def test_disabled_config_exports_nothing_and_reports_ok(self) -> None:
        tracer = self.make(enabled=False)
        state = tracer.open_segment(RUN, TASK, "start")
        with tracer.span("kernel.route", "chain", self.corr):
            tracer.event("e", self.corr)
        self.assertEqual(tracer.close_segment(), ObservabilityStatus.OK)
        self.assertEqual(state.trace_id, deterministic_trace_id(RUN))
        self.assertEqual(self.exporter.get_finished_spans(), ())
        self.assertFalse(tracer.spool.path.exists())


class TestRedactionBeforeExport(_Harness):
    """Nothing secret reaches the exporter."""

    def test_secret_values_and_denied_excerpts_never_reach_spans(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        leaked = f"header {self.secret} and {self.public}"
        with tracer.span("kernel.route", "chain", self.corr, input={"text": leaked}) as span:
            span.update(output={"items": [{"locator": ".env", "excerpt": "DB=prod-creds"}]},
                        metadata={"note": leaked})
            tracer.event("e", self.corr, payload={"text": leaked})
        tracer.generation("jev.x", self.corr, model="m", input=leaked, output=leaked, usage=None)
        tracer.close_segment()
        exported = json.dumps([dict(narrow(s.attributes))
                              for s in self.exporter.get_finished_spans()])
        self.assertNotIn(self.secret, exported)
        self.assertNotIn(self.public, exported)
        self.assertNotIn("DB=prod-creds", exported)
        self.assertIn("REDACTED", exported)


class TestDegradedMode(_Harness):
    """Telemetry failures degrade to a local spool and never fail the run."""

    def test_missing_credentials_spool_and_report_degraded(self) -> None:
        tracer = self.make(with_keys=False)
        state = tracer.open_segment(RUN, TASK, "start")
        with tracer.span("kernel.route", "chain", self.corr, input={"q": 1}):
            tracer.event("routing.assessed", self.corr, payload={"p": 0.9})
        tracer.generation("jev.x", self.corr, model="m", input="i", output="o", usage=None)
        self.assertEqual(tracer.close_segment(), ObservabilityStatus.DEGRADED)
        self.assertEqual(state.trace_id, deterministic_trace_id(RUN))
        self.assertEqual(tracer.degraded_reason, "missing_credentials")
        records = tracer.spool.read()
        self.assertEqual({r["name"] for r in records},
                         {"leafcutter.run", "routing.assessed", "kernel.route", "jev.x"})
        self.assertTrue(all(r["reason"] == "missing_credentials" for r in records))
        self.assertEqual(self.exporter.get_finished_spans(), ())

    def test_auth_check_failure_degrades(self) -> None:
        tracer = self.make(verify_auth=True)
        with mock.patch.object(Langfuse, "auth_check", return_value=False):
            tracer.open_segment(RUN, TASK, "start")
        self.assertEqual(tracer.degraded_reason, "auth_check_failed")
        self.assertEqual(tracer.close_segment(), ObservabilityStatus.DEGRADED)

    def test_sdk_failure_mid_run_spools_later_observations_and_keeps_the_body_running(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        ran: list[str] = []
        with mock.patch.object(narrow(tracer._segment).obs, "start_observation",
                               side_effect=RuntimeError("otel exploded")):
            with tracer.span("kernel.route", "chain", self.corr, input={"q": 1}) as span:
                ran.append("body")
                span.update(output={"ok": True})
            tracer.event("after", self.corr)
        self.assertEqual(ran, ["body"])
        self.assertEqual(tracer.close_segment(), ObservabilityStatus.DEGRADED)
        self.assertIn("RuntimeError", narrow(tracer.degraded_reason))
        by_name = {r["name"]: r for r in tracer.spool.read()}
        self.assertEqual(by_name["kernel.route"]["data"]["output"], {"ok": True})
        self.assertIn("after", by_name)

    def test_flush_failure_degrades_without_raising(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        with mock.patch.object(tracer.client, "flush", side_effect=OSError("disk")):
            self.assertEqual(tracer.close_segment(), ObservabilityStatus.DEGRADED)

    def test_spool_is_redacted_and_survives_unwritable_path(self) -> None:
        tracer = self.make()
        tracer.spool.write("event", "e", {"text": f"see {self.secret}"})
        self.assertNotIn(self.secret, tracer.spool.path.read_text(encoding="utf-8"))
        broken = self.make(with_keys=False)
        broken.spool.path = self.dir  # a directory cannot be opened for append
        broken.open_segment(RUN, TASK, "start")
        self.assertEqual(broken.close_segment(), ObservabilityStatus.DEGRADED)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Unique public key per test because the SDK caches one client per key.
#   (#KernelBootstrapV0/P2)
# ====================================================================
