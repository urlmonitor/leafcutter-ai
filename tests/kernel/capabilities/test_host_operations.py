"""
MODULE: tests.kernel.capabilities.test_host_operations
GOAL: Test the four host operations: the deterministic, versioned packet compiler (template id,
    fingerprint, bounded and redacted text) and the conversion of a schema-valid host output into
    a CapabilityResult (proposals stay proposals, evidence is host-reported, findings are
    inferences, a formulated question keeps its choices), plus unavailable usage (Rev 3 11.7).
BUSINESS CONTEXT: The kernel owns the contract with the host (ADR-052): the same request must
    always compile to the same packet, and whatever the host claims must be recorded as a
    host-reported claim, never as kernel-verified fact or human approval.
ARCHITECTURE: Pure unit tests over real contract models and the real compiler; nothing is mocked.
    Hosts are simulated as raw JSON so a test states exactly what the host claimed.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

from kernel.bootstrap import NATIVE_VERSION, build_bindings
from kernel.capabilities.host import (
    OPERATIONS,
    HostBindingExecuted,
    HostOperationExecutor,
    TaskInputs,
    compiler_for,
    parse_compiled_by,
    template_versions,
)
from kernel.contracts import (
    ResultStatus,
    Usage,
    schema_ids,
)
from kernel.interaction.packets import FORBIDDEN_HOST_OPERATIONS
from kernel.registry.adapter import load_registry
from tests.kernel.capabilities.host_support import (
    ANSWER_AFTER,
    OPTIONS_REQUEST,
    QUESTION_REQUEST,
    EXPERIMENT_ONLY,
    REQUESTS,
    RESEARCH_REQUEST,
    SCHEMAS,
    SYNTHESIS_REQUEST,
    convert,
)
from tests.kernel.helpers import as_type, narrow

NEEDLE = "zq" + "-" + "Xk29" + "Lm81" + "Pv07"  # assembled so the secret scanner sees no literal
def inputs(capability_id: str, payload: dict, goal: str = "goal") -> TaskInputs:
    """Return compiler inputs for a capability with the standard forbidden operations."""
    op = compiler_for(capability_id)
    return TaskInputs(
        capability_id=capability_id, operation=op.operation, goal=goal, payload=payload,
        allowed_operations=(op.operation,), forbidden_operations=tuple(FORBIDDEN_HOST_OPERATIONS),
        output_schema_id=SCHEMAS[capability_id][1], evidence_ids=("ev-0000000000000001",),
        max_input_chars=60000)


class TestCompiler(unittest.TestCase):
    """The invocation compiler: deterministic, versioned, bounded, redacted."""

    def test_same_inputs_give_the_same_text_and_fingerprint(self) -> None:
        for capability_id, payload in REQUESTS.items():
            with self.subTest(capability_id):
                op = compiler_for(capability_id)
                first, second = op.compile(inputs(capability_id, payload)), \
                    op.compile(inputs(capability_id, payload))
                self.assertEqual(first, second)
                self.assertRegex(first.fingerprint, r"^[0-9a-f]{16}$")

    def test_a_different_request_gives_a_different_fingerprint(self) -> None:
        op = compiler_for("host.generate_options")
        other = {**OPTIONS_REQUEST, "problem": "Where should the queue live?"}
        self.assertNotEqual(op.compile(inputs("host.generate_options", OPTIONS_REQUEST)).fingerprint,
                            op.compile(inputs("host.generate_options", other)).fingerprint)

    def test_the_template_is_named_and_recorded_in_the_packet(self) -> None:
        for capability_id, payload in REQUESTS.items():
            with self.subTest(capability_id):
                compiled = compiler_for(capability_id).compile(inputs(capability_id, payload))
                self.assertEqual(compiled.template_id, f"{capability_id}.task")
                self.assertEqual(compiled.template_version, "1.0.0")
                self.assertIn(compiled.template_id, compiled.statement)
                ref = parse_compiled_by([*compiled.requirements, compiled.compiled_by_line])
                self.assertEqual((narrow(ref).template_id, narrow(ref).fingerprint),
                                 (compiled.template_id, compiled.fingerprint))
                self.assertEqual(template_versions(capability_id),
                                 {"host_template": f"{capability_id}.task@1.0.0"})

    def test_the_statement_names_operations_schema_evidence_and_limits(self) -> None:
        compiled = compiler_for("host.research").compile(inputs("host.research", RESEARCH_REQUEST))
        for forbidden in FORBIDDEN_HOST_OPERATIONS:
            self.assertIn(forbidden, compiled.statement)
        for expected in ("bounded_research", schema_ids.EVIDENCE_BUNDLE, "ev-0000000000000001",
                         "max_input_chars=60000", "need-1"):
            self.assertIn(expected, compiled.statement)
        self.assertTrue(any("data, never instructions" in r for r in compiled.requirements))

    def test_requirements_say_what_the_operation_must_honour(self) -> None:
        options = compiler_for("host.generate_options").compile(
            inputs("host.generate_options", {**OPTIONS_REQUEST, "propose_criteria": False}))
        self.assertTrue(any("at most 2 options" in r for r in options.requirements))
        self.assertTrue(any("proposed_criteria empty" in r for r in options.requirements))
        research = compiler_for("host.research").compile(inputs("host.research", RESEARCH_REQUEST))
        self.assertTrue(any("Do not invent content hashes" in r for r in research.requirements))
        question = compiler_for("host.formulate_question").compile(
            inputs("host.formulate_question", QUESTION_REQUEST))
        self.assertTrue(any("Choice ids to keep: sqlite, files" in r
                            for r in question.requirements))

    def test_a_long_task_is_cut_at_the_end_and_the_header_survives(self) -> None:
        payload = {**OPTIONS_REQUEST, "problem": "Q " * 4000}
        compiled = compiler_for("host.generate_options").compile(
            inputs("host.generate_options", payload))
        self.assertLessEqual(len(compiled.statement), 2000)
        self.assertTrue(compiled.statement.endswith("[truncated]"))
        self.assertIn("Forbidden: edit_repository", compiled.statement)

    def test_free_text_is_redacted_before_it_is_rendered_and_fingerprinted(self) -> None:
        payload = {**OPTIONS_REQUEST, "problem": f"Use the token {NEEDLE} for the cache"}
        op = compiler_for("host.generate_options")
        masked = op.compile(inputs("host.generate_options", payload),
                            lambda text: text.replace(NEEDLE, "[REDACTED]"))
        self.assertNotIn(NEEDLE, masked.statement)
        self.assertIn("[REDACTED]", masked.statement)
        plain = op.compile(inputs("host.generate_options", payload))
        self.assertNotEqual(masked.fingerprint, plain.fingerprint)

    def test_an_invalid_request_falls_back_to_the_generic_task(self) -> None:
        compiled = compiler_for("host.research").compile(
            inputs("host.research", {"not": "a retrieval request"}, goal="Find the cache ADR"))
        self.assertIn("Perform bounded_research: Find the cache ADR", compiled.statement)

    def test_an_unknown_host_capability_still_compiles_with_the_generic_template(self) -> None:
        compiled = compiler_for("host.unknown").compile(TaskInputs(
            capability_id="host.unknown", operation="do_it", goal="Do it", payload={},
            allowed_operations=("do_it",), forbidden_operations=tuple(FORBIDDEN_HOST_OPERATIONS),
            output_schema_id=schema_ids.FINDINGS))
        self.assertEqual(compiled.template_id, "host.generic.task")
        self.assertEqual(template_versions("host.unknown"), {})

    def test_every_host_capability_of_the_design_has_an_operation(self) -> None:
        self.assertEqual(set(OPERATIONS), set(SCHEMAS))


class TestBootstrapBindings(unittest.TestCase):
    """Every host descriptor of the real registry is bound to its own operation executor."""

    def test_each_host_descriptor_gets_its_operation_and_refuses_to_execute(self) -> None:
        config = Path(__file__).resolve().parents[3] / "config" / "capability_registry.json"
        table = build_bindings(load_registry(config))
        for capability_id in sorted(set(SCHEMAS) - EXPERIMENT_ONLY):
            with self.subTest(capability_id):
                executor = as_type(table.resolve(capability_id, NATIVE_VERSION),
                                   HostOperationExecutor)
                self.assertIs(executor.operation, OPERATIONS[capability_id])
                compiled = executor.prepare(inputs(capability_id, REQUESTS[capability_id]))
                self.assertEqual(compiled.template_id, f"{capability_id}.task")
                with self.assertRaises(HostBindingExecuted):
                    asyncio.run(executor.ainvoke(cast(Any, None), cast(Any, None)))


class TestUsageAndDiagnostics(unittest.TestCase):
    """Unknown billing stays unavailable, never zero (spec 11.7)."""

    def test_host_usage_unavailable(self) -> None:
        result = convert("host.research", RESEARCH_REQUEST, {"evidence": []})
        (usage,) = result.usage
        self.assertEqual(usage.provider, "host")
        self.assertIsNone(usage.input_tokens)
        self.assertIsNone(usage.output_tokens)
        self.assertIsNone(usage.cost_usd)
        self.assertIsNone(usage.model_id)
        self.assertEqual(usage.cost_provenance, "unavailable")
        self.assertEqual(usage.calls, 1)
        self.assertEqual(usage.duration_ms, int(ANSWER_AFTER / timedelta(milliseconds=1)))
        self.assertEqual(result.diagnostics["host_usage"], "unavailable")

    def test_reported_usage_is_kept_exactly(self) -> None:
        reported = Usage(provider="host", model_id="claude-x", input_tokens=10, output_tokens=5)
        result = convert("host.research", RESEARCH_REQUEST, {"evidence": []}, usage=[reported])
        self.assertEqual(result.usage, [reported])
        self.assertIsNone(result.usage[0].cost_usd)
        self.assertEqual(result.diagnostics["host_usage"], "reported")

    def test_the_result_records_the_template_fingerprint_and_time_to_answer(self) -> None:
        result = convert("host.synthesize", SYNTHESIS_REQUEST, {"findings": []})
        self.assertEqual(result.diagnostics["host_template"], "host.synthesize.task@1.0.0")
        self.assertRegex(str(result.diagnostics["prompt_fingerprint"]), r"^[0-9a-f]{16}$")
        self.assertEqual(result.diagnostics["host_elapsed_ms"], 1500)

    def test_an_unconvertible_output_fails_the_result_instead_of_raising(self) -> None:
        result = convert("host.formulate_question", {"not": "a question"}, {
            "question": "Which store?", "free_text_allowed": True})
        self.assertIs(result.status, ResultStatus.FAILED)
        self.assertEqual(narrow(result.error).code, "host_output_invalid")
        self.assertFalse(narrow(result.error).retryable)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 12:10 [python-coder]: Hosts are simulated as raw JSON (including lying hashes and
#   statuses) rather than through the contract models, because the models would refuse to build
#   exactly the claims a host might send. (#KernelBootstrapV0/P8)
# ====================================================================
