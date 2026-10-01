"""
MODULE: tests.kernel.providers.test_jev_generation
GOAL: Verify the Jev adapter emits one GENERATION per assess call through the Tracer port, and
    that the LangChain callback path does not add a duplicate usage-less CHAIN when it does.
BUSINESS CONTEXT: A live demo showed Jev calls in Langfuse as CHAIN observations with no model,
    usage or cost; generations are the only observation type that carries them (design part 5).
ARCHITECTURE: Mocked HTTP (httpx for the direct transport, httpx2 for the classifier) and a
    RecordingTracer; callback suppression is checked with a LangChain handler installed on an
    enclosing runnable, exactly how the graph-level Langfuse handler reaches the classifier.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import TYPE_CHECKING, Any, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableLambda

from kernel.contracts.base import CorrelationIds
from kernel.observability.tracer import RecordingTracer
from kernel.providers import JevBatch, JevUnavailable
from kernel.providers.jev import ClassifierTransport
from tests.kernel.providers import jevkit as kit

CORR = CorrelationIds(run_id="run-1", root_task_id="task-1", work_item_id="work-1")


def _batch() -> JevBatch:
    return kit.mixed_batch("kernel.route").model_copy(update={"correlation": CORR})


def _ok(lib, _req):
    return lib.Response(200, json=kit.body(), headers={"x-typesafe-request-id": "req-9"})


class _Chains(BaseCallbackHandler):
    """Collects the names of every chain the callback system starts."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def on_chain_start(self, serialized, inputs, **kwargs) -> None:
        self.names.append(kwargs.get("name") or "")


if TYPE_CHECKING:  # the mixin uses TestCase assertions; at runtime it stays a plain mixin
    _Base = unittest.TestCase
else:
    _Base = object


class GenerationContract(_Base):
    """Behaviour shared by both transports; subclasses define make_transport."""

    make_transport: Any = None

    def adapter(self, handler, tracer, **overrides):
        transport, lib = type(self).make_transport(lambda req: handler(lib_holder[0], req))
        lib_holder.append(lib)
        return kit.make_adapter(transport, kit.Sleeper(), tracer=tracer, model_name="jev-cfg",
                                **overrides)

    def test_success_emits_one_generation_with_usage_and_distributions(self) -> None:
        tracer = RecordingTracer()
        lib_holder.clear()
        adapter = self.adapter(lambda lib, req: _ok(lib, req), tracer)
        result = asyncio.run(adapter.assess(_batch()))
        (gen,) = [c for c in tracer.calls if c.kind == "generation"]
        self.assertEqual(gen.name, "jev.kernel.route")
        self.assertEqual(gen.corr, CORR)
        self.assertEqual(gen.data["model"], result.model_id)
        self.assertIs(gen.data["usage"], result.usage)
        self.assertEqual(gen.data["usage"].cost_provenance, "estimated")
        meta = gen.data["metadata"]
        self.assertEqual(meta["purpose"], "kernel.route")
        self.assertEqual(meta["adapter_version"], adapter.adapter_version)
        self.assertEqual(meta["status"], "ok")
        self.assertEqual(meta["request_id"], "req-9")
        self.assertIn("latency_ms", meta)
        answers = gen.data["output"]["answers"]
        self.assertEqual(answers["q.choice"]["probabilities"],
                         {"alpha": 0.7, "beta": 0.2, "__NONE__": 0.1})
        self.assertEqual(gen.data["input"]["questions"][0]["template_id"], "t.noul")
        self.assertNotIn("state", gen.data["input"])

    def test_unknown_usage_stays_none_not_zero(self) -> None:
        tracer = RecordingTracer()
        lib_holder.clear()
        payload = kit.body()
        payload.pop("usage", None)
        for key in ("input_tokens", "output_tokens"):
            payload.pop(key, None)
        adapter = self.adapter(lambda lib, req: lib.Response(200, json=payload), tracer,
                               price_per_input_token_usd=None)
        result = asyncio.run(adapter.assess(_batch()))
        usage = tracer.calls[-1].data["usage"]
        self.assertIsNone(usage.cost_usd)
        self.assertEqual(usage.cost_provenance, "unavailable")
        self.assertIsNone(result.usage.input_tokens)
        self.assertIsNone(usage.input_tokens)
        self.assertIsNone(usage.output_tokens)

    def test_failure_emits_an_error_generation_and_still_raises(self) -> None:
        tracer = RecordingTracer()
        lib_holder.clear()
        adapter = self.adapter(lambda lib, req: lib.Response(401, json={"error": "no"}), tracer)
        with self.assertRaises(JevUnavailable):
            asyncio.run(adapter.assess(_batch()))
        (gen,) = [c for c in tracer.calls if c.kind == "generation"]
        self.assertEqual(gen.data["metadata"]["status"], "error")
        self.assertIn("JevUnavailable", gen.data["metadata"]["error"])
        self.assertIsNone(gen.data["output"])
        self.assertIsNone(gen.data["usage"])
        self.assertEqual(gen.data["model"], "jev-cfg")

    def test_without_a_tracer_nothing_is_emitted_and_results_are_unchanged(self) -> None:
        lib_holder.clear()
        adapter = self.adapter(lambda lib, req: _ok(lib, req), None)
        result = asyncio.run(adapter.assess(_batch()))
        self.assertEqual(result.noul("q.noul").probability, 0.83)


lib_holder: list = []


class TestHttpTransportGenerations(GenerationContract, unittest.TestCase):
    make_transport = staticmethod(kit.http_transport)


class TestClassifierTransportGenerations(GenerationContract, unittest.TestCase):
    make_transport = staticmethod(kit.classifier_transport)


class TestCallbackDeduplication(unittest.TestCase):
    """The inherited graph-level handler must not record the Jev call as a second CHAIN."""

    def _chains(self, detach: bool) -> list[str]:
        import httpx2

        client = httpx2.AsyncClient(transport=httpx2.MockTransport(
            lambda req: httpx2.Response(200, json=kit.body())))
        transport = ClassifierTransport(api_key=kit.FAKE_KEY, model="jev-test",
                                        timeout_seconds=5.0, async_client=client,
                                        detach_callbacks=detach)
        adapter = kit.make_adapter(transport, kit.Sleeper())
        handler = _Chains()

        async def outer(_value):
            return await adapter.assess(_batch())

        asyncio.run(RunnableLambda(outer, name="kernel.node").ainvoke(
            1, config={"callbacks": [handler]}))
        return handler.names

    def test_inherited_callbacks_see_the_jev_chain_unless_detached(self) -> None:
        self.assertIn("jev.kernel.route", self._chains(detach=False))
        names = self._chains(detach=True)
        self.assertNotIn("jev.kernel.route", names)
        self.assertIn("kernel.node", names)

    def test_from_config_with_tracer_detaches_callbacks(self) -> None:
        from kernel.config import load_kernel_config
        from kernel.providers.jev import TypeSafeJevAdapter

        cfg = load_kernel_config()
        with_tracer = TypeSafeJevAdapter.from_config(cfg, kit.FAKE_KEY, transport="classifier",
                                                     tracer=RecordingTracer())
        without = TypeSafeJevAdapter.from_config(cfg, kit.FAKE_KEY, transport="classifier")
        self.assertTrue(cast(Any, with_tracer._transport)._detach_callbacks)
        self.assertFalse(cast(Any, without._transport)._detach_callbacks)


if __name__ == "__main__":
    unittest.main()
