"""
MODULE: tests.kernel.providers.test_jev_adapter
GOAL: Verify TypeSafeJevAdapter over both transports with mocked HTTP: answer mapping,
    sentinels, retries, error mapping, size guard, timeout, chunking and usage.
BUSINESS CONTEXT: A provider outage must become JevUnavailable (never a fabricated answer or a
    capability gap) and malformed answers must never steer routing, on either transport.
ARCHITECTURE: One contract mixin run against the direct-HTTP transport (httpx) and the
    langchain-typesafe classifier transport (httpx2). No network, no real sleeping.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import TYPE_CHECKING, Any

from kernel.providers import JevBatch, JevInvalidResponse, JevPayloadTooLarge, JevUnavailable
from kernel.providers.jev_errors import JevInvalidRequest
from tests.kernel.providers import jevkit as kit

if TYPE_CHECKING:  # the mixin uses TestCase assertions; at runtime it stays a plain mixin
    _Base = unittest.TestCase
else:
    _Base = object


class AdapterContract(_Base):
    """Behaviour every transport must show; subclasses define make_transport."""

    make_transport: Any = None

    def setUp(self) -> None:
        """Reset recorded requests and delays."""
        self.requests: list[dict] = []
        self.sleeper = kit.Sleeper()

    def adapter(self, responder: Any, **overrides: Any) -> Any:
        """Return an adapter whose mocked server calls responder(lib, request, payload)."""
        holder: dict[str, Any] = {}

        def handler(request):
            payload = json.loads(request.content)
            self.requests.append({"payload": payload, "auth": request.headers["authorization"]})
            return responder(holder["lib"], request, payload)

        transport, holder["lib"] = type(self).make_transport(handler)
        return kit.make_adapter(transport, self.sleeper, **overrides)

    def ok(self, extra_headers: dict | None = None):
        """Return a responder that always answers with the mixed fixture body."""
        return lambda lib, _req, _payload: lib.Response(
            200, json=kit.body(), headers=extra_headers or {})

    def test_maps_all_answer_kinds(self) -> None:
        """Noul, choice and score map with raw distributions, confidence, model and usage."""
        adapter = self.adapter(self.ok({"x-typesafe-request-id": "req-1"}))
        batch = kit.mixed_batch()
        result = asyncio.run(adapter.assess(batch))
        self.assertEqual(result.noul("q.noul").probability, 0.83)
        self.assertIsNone(result.noul("q.noul").confidence)
        choice = result.choice("q.choice")
        self.assertEqual(choice.choice, "alpha")
        self.assertEqual(choice.probabilities, {"alpha": 0.7, "beta": 0.2, "__NONE__": 0.1})
        self.assertEqual(choice.confidence, 0.61)
        score = result.answers["q.score"]
        self.assertEqual(score.score, 1.4)
        self.assertEqual(score.probabilities, {"0": 0.1, "1": 0.4, "2": 0.5})
        self.assertEqual(result.model_id, "jev-test-2026-09")
        self.assertEqual(result.request_id, "req-1")
        self.assertEqual(result.input_fingerprint, batch.input_fingerprint())
        self.assertEqual((result.usage.input_tokens, result.usage.output_tokens), (1000, 12))
        self.assertEqual(result.usage.cost_provenance, "estimated")
        self.assertAlmostEqual(result.usage.cost_usd, 1000 * 4.2e-8)
        self.assertEqual(result.usage.calls, 1)
        self.assertEqual(result.usage.model_id, "jev-test-2026-09")

    def test_request_shape_and_explicit_key(self) -> None:
        """The wire request carries state, typed questions and the explicit bearer key."""
        asyncio.run(self.adapter(self.ok()).assess(kit.mixed_batch()))
        sent = self.requests[0]
        self.assertEqual(sent["auth"], f"Bearer {kit.FAKE_KEY}")
        self.assertEqual(sent["payload"]["state"], {"item": "synthetic"})
        questions = sent["payload"]["questions"]
        self.assertEqual(questions["q.choice"]["criteria"]["__NONE__"], "neither")
        self.assertEqual(questions["q.score"]["criteria"], ["low", "mid", "high"])
        self.assertEqual(questions["q.noul"]["type"], "noul")
        self.assertNotIn(kit.FAKE_KEY, json.dumps(sent["payload"]))

    def test_sentinel_choices_pass_through(self) -> None:
        """__NONE__ and __NEEDS_CONTEXT__ are ordinary labels the caller interprets."""
        criteria = {"cap.a": "a", "__NONE__": "none", "__NEEDS_CONTEXT__": "needs context"}
        question = kit.spec("choice", "route.w1").model_copy(update={"criteria": criteria})
        batch = JevBatch(purpose="route", state={"request": "x"}, questions=[question])
        for label in ("__NONE__", "__NEEDS_CONTEXT__"):
            probs = {"cap.a": 0.1, "__NONE__": 0.1, "__NEEDS_CONTEXT__": 0.1}
            probs[label] = 0.8
            body = {"model": "m", "answers": {"route.w1": {
                "type": "choice", "choice": label, "probabilities": probs, "confidence": 0.9}}}
            adapter = self.adapter(lambda lib, _r, _p, b=body: lib.Response(200, json=b))
            result = asyncio.run(adapter.assess(batch))
            self.assertEqual(result.choice("route.w1").choice, label)

    def test_retries_then_unavailable(self) -> None:
        """Persistent 503 is retried max_retries times with doubling backoff, then unavailable."""
        adapter = self.adapter(lambda lib, _r, _p: lib.Response(503, json={"error": "x"}))
        with self.assertRaises(JevUnavailable) as caught:
            asyncio.run(adapter.assess(kit.mixed_batch()))
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(self.sleeper.delays, [1.0, 2.0])
        self.assertIn("3 attempts", str(caught.exception))
        self.assertNotIn(kit.FAKE_KEY, str(caught.exception))

    def test_rate_limit_honours_retry_after_then_succeeds(self) -> None:
        """A 429 with retry-after is waited out, then the next attempt succeeds."""
        calls = {"n": 0}

        def responder(lib, _r, _p):
            calls["n"] += 1
            if calls["n"] == 1:
                return lib.Response(429, json={}, headers={"retry-after": "3"})
            return lib.Response(200, json=kit.body())

        result = asyncio.run(self.adapter(responder).assess(kit.mixed_batch()))
        self.assertEqual(self.sleeper.delays, [3.0])
        self.assertEqual(len(self.requests), 2)  # two attempts ...
        self.assertEqual(result.usage.calls, 1)  # ... but one provider call (#KernelV01/C)

    def test_authentication_error_is_not_retried(self) -> None:
        """401 maps to JevUnavailable immediately, without leaking the key."""
        adapter = self.adapter(lambda lib, _r, _p: lib.Response(401, json={"error": "no"}))
        with self.assertRaises(JevUnavailable) as caught:
            asyncio.run(adapter.assess(kit.mixed_batch()))
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.sleeper.delays, [])
        self.assertNotIn(kit.FAKE_KEY, str(caught.exception))

    def test_connection_timeout_is_retried_then_unavailable(self) -> None:
        """A transport timeout counts as transient."""
        def responder(lib, request, _p):
            raise lib.ReadTimeout("slow", request=request)

        with self.assertRaises(JevUnavailable):
            asyncio.run(self.adapter(responder).assess(kit.mixed_batch()))
        self.assertEqual(len(self.requests), 3)

    def test_hard_call_deadline(self) -> None:
        """A call exceeding timeout_seconds is abandoned and retried, then unavailable."""
        holder: dict = {}

        async def handler(request):
            self.requests.append({"payload": json.loads(request.content), "auth": ""})
            await asyncio.sleep(2)
            return holder["lib"].Response(200, json=kit.body())

        transport, holder["lib"] = type(self).make_transport(handler)
        adapter = kit.make_adapter(transport, self.sleeper, timeout_seconds=0.05, max_retries=1)
        with self.assertRaises(JevUnavailable) as caught:
            asyncio.run(adapter.assess(kit.mixed_batch()))
        self.assertEqual(len(self.requests), 2)
        self.assertIn("2 attempts", str(caught.exception))

    def test_missing_answer_id_is_invalid(self) -> None:
        """A response that omits a requested id raises JevInvalidResponse, not retried."""
        data = kit.body()
        del data["answers"]["q.score"]
        adapter = self.adapter(lambda lib, _r, _p: lib.Response(200, json=data))
        with self.assertRaises(JevInvalidResponse):
            asyncio.run(adapter.assess(kit.mixed_batch()))
        self.assertEqual(len(self.requests), 1)

    def test_choice_outside_criteria_is_invalid(self) -> None:
        """An unknown chosen label is rejected."""
        data = kit.body()
        data["answers"]["q.choice"]["choice"] = "gamma"
        adapter = self.adapter(lambda lib, _r, _p: lib.Response(200, json=data))
        with self.assertRaises(JevInvalidResponse):
            asyncio.run(adapter.assess(kit.mixed_batch()))

    def test_probabilities_not_summing_to_one_are_invalid(self) -> None:
        """Distributions outside 1 +- 0.02 are rejected."""
        data = kit.body()
        data["answers"]["q.choice"]["probabilities"] = {"alpha": 0.5, "beta": 0.2}
        adapter = self.adapter(lambda lib, _r, _p: lib.Response(200, json=data))
        with self.assertRaises(JevInvalidResponse):
            asyncio.run(adapter.assess(kit.mixed_batch()))

    def test_oversize_state_raises_before_any_call(self) -> None:
        """A state above max_state_chars raises JevPayloadTooLarge and sends nothing."""
        adapter = self.adapter(self.ok(), max_state_chars=50)
        batch = JevBatch(purpose="big", state={"blob": "x" * 200},
                         questions=[kit.spec("noul", "q.noul")])
        with self.assertRaises(JevPayloadTooLarge) as caught:
            asyncio.run(adapter.assess(batch))
        self.assertGreater(caught.exception.size, caught.exception.limit)
        self.assertEqual(self.requests, [])

    def test_chunks_large_batches_and_sums_usage(self) -> None:
        """Five questions with max 2 per call make three requests with merged answers."""
        ids = [f"n{i}" for i in range(5)]

        def responder(lib, _r, payload):
            answers = {q: {"type": "noul", "noul": 0.5} for q in payload["questions"]}
            return lib.Response(200, json={"model": "m", "answers": answers,
                                           "usage": {"input_tokens": 10, "output_tokens": 1}})

        batch = JevBatch(purpose="many", state={"s": 1},
                         questions=[kit.spec("noul", i) for i in ids])
        result = asyncio.run(self.adapter(responder, max_questions_per_call=2).assess(batch))
        self.assertEqual([len(r["payload"]["questions"]) for r in self.requests], [2, 2, 1])
        self.assertEqual(list(result.answers), ids)
        self.assertEqual((result.usage.input_tokens, result.usage.calls), (30, 3))

    def test_unknown_usage_stays_none(self) -> None:
        """Missing usage yields None token counts, never zero, and no cost."""
        data = {"model": "m", "answers": {"q.noul": {"type": "noul", "noul": 0.2}}}
        batch = JevBatch(purpose="p", state={}, questions=[kit.spec("noul", "q.noul")])
        adapter = self.adapter(lambda lib, _r, _p: lib.Response(200, json=data))
        result = asyncio.run(adapter.assess(batch))
        self.assertEqual(result.model_id, "m")
        self.assertIsNone(result.usage.input_tokens)
        self.assertIsNone(result.usage.output_tokens)
        self.assertIsNone(result.usage.cost_usd)
        self.assertEqual(result.usage.cost_provenance, "unavailable")

    def test_duplicate_question_ids_rejected(self) -> None:
        """Duplicate ids are a caller bug and fail before any call."""
        batch = JevBatch(purpose="p", state={},
                         questions=[kit.spec("noul", "a"), kit.spec("noul", "a")])
        with self.assertRaises(JevInvalidRequest):
            asyncio.run(self.adapter(self.ok()).assess(batch))
        self.assertEqual(self.requests, [])


class HttpTransportAdapterTests(AdapterContract, unittest.TestCase):
    """Adapter over the direct-HTTP fallback transport."""

    make_transport = staticmethod(kit.http_transport)

    def test_non_json_success_is_invalid_response(self) -> None:
        """A 200 with a non-JSON body raises JevInvalidResponse."""
        adapter = self.adapter(lambda lib, _r, _p: lib.Response(200, content=b"<html>"))
        with self.assertRaises(JevInvalidResponse):
            asyncio.run(adapter.assess(kit.mixed_batch()))

    def test_missing_model_and_usage_stay_none(self) -> None:
        """The HTTP path tolerates a body without model and usage; both stay None."""
        data = {"answers": {"q.noul": {"type": "noul", "noul": 0.2}}}
        batch = JevBatch(purpose="p", state={}, questions=[kit.spec("noul", "q.noul")])
        adapter = self.adapter(lambda lib, _r, _p: lib.Response(200, json=data))
        result = asyncio.run(adapter.assess(batch))
        self.assertIsNone(result.model_id)
        self.assertIsNone(result.usage.model_id)

    def test_adapter_version_names_transport(self) -> None:
        """adapter_version identifies the transport."""
        adapter = self.adapter(self.ok())
        self.assertEqual(adapter.adapter_version, "http-direct/1")


class ClassifierTransportAdapterTests(AdapterContract, unittest.TestCase):
    """Adapter over langchain-typesafe's TypeSafeClassifier."""

    make_transport = staticmethod(kit.classifier_transport)

    def test_adapter_version_names_package_version(self) -> None:
        """adapter_version carries the installed langchain-typesafe version."""
        import langchain_typesafe  # noqa: PLC0415

        adapter = self.adapter(self.ok())
        self.assertEqual(adapter.adapter_version,
                         f"typesafe-classifier/{langchain_typesafe.__version__}")

    def test_malformed_score_body_is_invalid_response(self) -> None:
        """The package's own response validation is mapped to JevInvalidResponse."""
        data = kit.body()
        del data["answers"]["q.score"]["legend"]
        adapter = self.adapter(lambda lib, _r, _p: lib.Response(200, json=data))
        with self.assertRaises(JevInvalidResponse):
            asyncio.run(adapter.assess(kit.mixed_batch()))
        self.assertEqual(len(self.requests), 1)


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Contract mixin runs on both transports so the fallback
#   cannot drift from the primary path. (#KernelBootstrapV0/P3)
# ====================================================================
