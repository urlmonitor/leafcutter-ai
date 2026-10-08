"""
MODULE: tests.kernel.providers.test_jev_wire_and_config
GOAL: Test the pure wire mapping, the re-exported error identities, and building the adapter
    from the kernel config for both transports.
BUSINESS CONTEXT: The adapter must reject malformed questions before any call, keep the error
    types identical to ScriptedJev's, and honour the configured limits and transport choice.
ARCHITECTURE: Pure functions plus from_config with an injected mock HTTP client; offline.
"""

from __future__ import annotations

import asyncio
import unittest

import httpx
import httpx2

from kernel.config import load_kernel_config
from kernel.providers import base
from kernel.providers import jev_errors as errors
from kernel.providers.jev import TypeSafeJevAdapter
from kernel.providers.jev_wire import map_answers, parse_body, question_to_wire
from tests.kernel.providers import jevkit as kit


class ErrorReExportTests(unittest.TestCase):
    """jev_errors must re-export, not redefine, the port errors."""

    def test_identity_with_base(self) -> None:
        """The same class objects are visible from both modules."""
        self.assertIs(errors.JevUnavailable, base.JevUnavailable)
        self.assertIs(errors.JevInvalidResponse, base.JevInvalidResponse)
        self.assertIs(errors.JevPayloadTooLarge, base.JevPayloadTooLarge)

    def test_transient_is_not_unavailable(self) -> None:
        """A transient error is not JevUnavailable until retries are exhausted."""
        self.assertFalse(issubclass(errors.JevTransientError, base.JevUnavailable))
        self.assertTrue(issubclass(errors.JevInvalidRequest, ValueError))


class QuestionWireTests(unittest.TestCase):
    """question_to_wire validates criteria per kind."""

    def test_choice_requires_mapping(self) -> None:
        """A choice without criteria is a caller error."""
        bad = kit.spec("choice", "c").model_copy(update={"criteria": None})
        with self.assertRaises(errors.JevInvalidRequest):
            question_to_wire(bad)

    def test_score_needs_two_levels(self) -> None:
        """A score with one level is rejected; a dict is flattened in order."""
        one = kit.spec("score", "s").model_copy(update={"criteria": ["only"]})
        with self.assertRaises(errors.JevInvalidRequest):
            question_to_wire(one)
        two = kit.spec("score", "s").model_copy(update={"criteria": {"a": "x", "b": "y"}})
        self.assertEqual(question_to_wire(two)["criteria"], ["x", "y"])

    def test_noul_criteria_keys(self) -> None:
        """Noul criteria may only use true/false."""
        good = kit.spec("noul", "n").model_copy(update={"criteria": {"true": "yes"}})
        self.assertEqual(question_to_wire(good)["criteria"], {"true": "yes"})
        bad = kit.spec("noul", "n").model_copy(update={"criteria": {"maybe": "?"}})
        with self.assertRaises(errors.JevInvalidRequest):
            question_to_wire(bad)


class AnswerMappingTests(unittest.TestCase):
    """map_answers rejects every malformed shape."""

    def test_type_mismatch(self) -> None:
        """An answer of the wrong type for its question is invalid."""
        with self.assertRaises(base.JevInvalidResponse):
            map_answers({"q.noul": {"type": "choice"}}, [kit.spec("noul", "q.noul")])

    def test_noul_out_of_range(self) -> None:
        """A noul probability above one is invalid."""
        with self.assertRaises(base.JevInvalidResponse):
            map_answers({"n": {"type": "noul", "noul": 1.4}}, [kit.spec("noul", "n")])

    def test_score_out_of_range_and_level_keys(self) -> None:
        """A score beyond the last level or an unknown level key is invalid."""
        spec = kit.spec("score", "s")
        with self.assertRaises(base.JevInvalidResponse):
            map_answers({"s": {"type": "score", "score": 3.0,
                               "probabilities": {"0": 1.0}}}, [spec])
        with self.assertRaises(base.JevInvalidResponse):
            map_answers({"s": {"type": "score", "score": 1.0,
                               "probabilities": {"7": 1.0}}}, [spec])

    def test_missing_confidence_is_none(self) -> None:
        """No provider confidence stays None rather than becoming zero."""
        spec = kit.spec("choice", "c")
        raw = {"c": {"type": "choice", "choice": "alpha",
                     "probabilities": {"alpha": 0.9, "beta": 0.1}}}
        self.assertIsNone(map_answers(raw, [spec])["c"].confidence)

    def test_parse_body_rejects_non_objects(self) -> None:
        """A body without an answers object is invalid; bad token counts become None."""
        with self.assertRaises(base.JevInvalidResponse):
            parse_body([], None)
        raw = parse_body({"answers": {}, "usage": {"input_tokens": -1, "output_tokens": True}},
                         None)
        self.assertIsNone(raw.input_tokens)
        self.assertIsNone(raw.output_tokens)


class FromConfigTests(unittest.TestCase):
    """from_config applies the configured limits and selects the transport."""

    def test_limits_and_http_transport(self) -> None:
        """Config values reach the adapter; the http transport uses the injected client."""
        cfg = load_kernel_config(env={})
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(200, json=kit.body())

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = TypeSafeJevAdapter.from_config(cfg, kit.FAKE_KEY, transport="http",
                                                 client=client)
        result = asyncio.run(adapter.assess(kit.mixed_batch()))
        self.assertEqual(seen, ["https://api.typesafe.ai/v1/systemone"])
        self.assertEqual(result.model_id, "jev-test-2026-09")
        self.assertEqual(adapter.adapter_version, "http-direct/1")
        self.assertEqual(adapter._max_retries, cfg.limits.max_retries)  # noqa: SLF001
        self.assertEqual(adapter._chunk, cfg.jev.max_questions_per_call)  # noqa: SLF001

    def test_classifier_transport_is_default(self) -> None:
        """Without a transport argument the classifier transport is used."""
        cfg = load_kernel_config(env={})
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(
            lambda _request: httpx2.Response(200, json=kit.body())))
        adapter = TypeSafeJevAdapter.from_config(cfg, kit.FAKE_KEY, client=client)
        self.assertTrue(adapter.adapter_version.startswith("typesafe-classifier/"))
        result = asyncio.run(adapter.assess(kit.mixed_batch()))
        self.assertEqual(result.choice("q.choice").choice, "alpha")


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Identity test guards the re-export rule from the P3 brief.
#   (#KernelBootstrapV0/P3)
# ====================================================================
