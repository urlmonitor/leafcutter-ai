"""
MODULE: tests.kernel.observability.test_observation_types
GOAL: Verify real Langfuse SDK spans carry the observation types of the design's map, and that a
    Jev adapter call exports as a GENERATION with model, usage and estimated cost.
BUSINESS CONTEXT: Langfuse dashboards filter by observation type; nodes must be chains, native
    capabilities agents, the retrieval adapter a tool, sources retrievers and Jev calls
    generations (design part 5).
ARCHITECTURE: LangfuseTracer over an in-memory OpenTelemetry exporter (no network); the
    callers keep passing "node"/"capability" kinds and the tracer maps them.
"""

from __future__ import annotations

import asyncio
import json
import unittest

from kernel.observability.observation_map import observation_type
from kernel.providers.jev import TypeSafeJevAdapter
from tests.kernel.observability.test_langfuse_tracer import RUN, TASK, _Harness
from tests.kernel.providers import jevkit as kit

TYPE_ATTR = "langfuse.observation.type"


class TestObservationTypeMap(unittest.TestCase):
    """The pure mapping function."""

    def test_design_map(self) -> None:
        cases = {("kernel.route", "node"): "chain",
                 ("capability.decision", "capability"): "agent",
                 ("capability.retrieve.repository", "capability"): "tool",
                 ("retrieval.repo.decisions", "retriever"): "retriever",
                 ("x", "chain"): "chain", ("x", "weird"): "span"}
        for (name, kind), expected in cases.items():
            with self.subTest(name=name, kind=kind):
                self.assertEqual(observation_type(name, kind), expected)


class TestExportedTypes(_Harness):
    """Real SDK spans."""

    def test_kernel_spans_export_with_design_types(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        with tracer.span("kernel.route", "node", self.corr):
            with tracer.span("capability.decision", "capability", self.corr):
                pass
            with tracer.span("capability.retrieve.repository", "capability", self.corr):
                with tracer.span("retrieval.repo.decisions", "retriever", self.corr):
                    pass
        tracer.close_segment()
        types = {name: self.attrs(spans[0])[TYPE_ATTR] for name, spans in self.spans().items()}
        self.assertEqual(types["kernel.route"], "chain")
        self.assertEqual(types["capability.decision"], "agent")
        self.assertEqual(types["capability.retrieve.repository"], "tool")
        self.assertEqual(types["retrieval.repo.decisions"], "retriever")

    def test_jev_call_exports_a_generation_with_model_usage_and_estimated_cost(self) -> None:
        tracer = self.make()
        tracer.open_segment(RUN, TASK, "start")
        holder: list = []
        transport, lib = kit.http_transport(lambda req: holder[0].Response(200, json=kit.body()))
        holder.append(lib)
        adapter = TypeSafeJevAdapter(
            transport, timeout_seconds=5.0, max_questions_per_call=20, max_state_chars=10000,
            max_retries=0, retry_backoff_seconds=0.0, price_per_input_token_usd=4.2e-8,
            tracer=tracer, model_name="jev-cfg")
        batch = kit.mixed_batch("kernel.route").model_copy(update={"correlation": self.corr})
        with tracer.span("capability.decision", "capability", self.corr):
            asyncio.run(adapter.assess(batch))
        tracer.close_segment()
        gen = self.spans()["jev.kernel.route"][0]
        attrs = self.attrs(gen)
        self.assertEqual(attrs[TYPE_ATTR], "generation")
        self.assertEqual(attrs["langfuse.observation.model.name"], "jev-test-2026-09")
        self.assertEqual(json.loads(attrs["langfuse.observation.usage_details"]),
                         {"input": 1000, "output": 12})
        self.assertAlmostEqual(
            json.loads(attrs["langfuse.observation.cost_details"])["total"], 4.2e-5)
        meta = self.meta(gen)
        self.assertEqual(meta["cost_provenance"], "estimated")
        self.assertEqual(meta["purpose"], "kernel.route")
        self.assertEqual(meta["work_item_id"], "work-1")
        parent = self.spans()["capability.decision"][0]
        self.assertEqual(gen.parent.span_id, parent.context.span_id)
        output = json.loads(attrs["langfuse.observation.output"])
        self.assertIn("probabilities", output["answers"]["q.choice"])


if __name__ == "__main__":
    unittest.main()
