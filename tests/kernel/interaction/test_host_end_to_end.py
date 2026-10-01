"""
MODULE: tests.kernel.interaction.test_host_end_to_end
GOAL: Drive each of the four host operations through the real compiled graph with a fake host
    responder: the packet carries the compiled statement and its fingerprint, the answer is
    validated, converted and integrated, and a `host.<operation>` telemetry event records the
    prompt fingerprint, time to answer and usage (known or unavailable).
BUSINESS CONTEXT: Conversion and compilation only matter if the graph really uses them: these
    tests prove the packet a client receives is the compiled one, that the integrated state holds
    the converted (not the raw) host output, and that telemetry names exactly what was sent.
ARCHITECTURE: The scheduler Rig binds a scripted root that waits on one host child of the
    capability under test; `start` runs to the interrupt and `Started.submit` answers through the
    ledgered entry point. The fake host is a function from packet to raw response.
"""

from __future__ import annotations

import unittest
from typing import Any

from kernel.capabilities.host import parse_compiled_by
from kernel.contracts import ResultStatus, RunStatus, Verification, schema_ids
from kernel.interaction import SubmitStatus
from tests.kernel.capabilities.host_support import SCHEMAS
from tests.kernel.interaction.host_rigs import (
    OPERATIONS,
    RESPONSES,
    host_result,
    host_rig,
)
from tests.kernel.interaction.support import Started, raw_submission, start


class TestEveryOperationThroughTheGraph(unittest.IsolatedAsyncioTestCase):
    """Packet out, answer in, converted result integrated, telemetry recorded."""

    async def run_operation(self, capability_id: str, **extra: Any
                            ) -> tuple[Started, dict, dict]:
        run = await start(host_rig(capability_id))
        submission = raw_submission(run.packet, run.run_id, response=RESPONSES[capability_id],
                                    **extra)
        outcome = await run.submit(submission)
        self.assertEqual(outcome.status, SubmitStatus.ACCEPTED)
        return run, run.packet, await run.values()

    async def test_each_operation_completes_with_its_converted_result(self) -> None:
        for capability_id in SCHEMAS:
            with self.subTest(capability_id):
                run, packet, state = await self.run_operation(capability_id)
                self.assertEqual(packet["operation"], OPERATIONS[capability_id])
                self.assertEqual(packet["output_schema_id"], SCHEMAS[capability_id][1])
                result = host_result(state, capability_id)
                self.assertIs(result.status, ResultStatus.COMPLETED)
                self.assertIs(state["outcome"].status, RunStatus.COMPLETED)
                self.assertEqual(result.diagnostics["host_template"],
                                 f"{capability_id}.task@1.0.0")

    async def test_the_packet_carries_the_compiled_statement_and_fingerprint(self) -> None:
        for capability_id in SCHEMAS:
            with self.subTest(capability_id):
                run = await start(host_rig(capability_id))
                packet = run.packet
                ref = parse_compiled_by(packet["output_requirements"])
                self.assertEqual(ref.template_id, f"{capability_id}.task")
                self.assertTrue(packet["goal"].startswith(f"[{capability_id}.task v1.0.0]"))
                self.assertIn(packet["output_schema_id"], packet["goal"])
                self.assertIn("edit_repository", packet["goal"])
                inv = next(i for i in run.state["invocations"].values()
                           if i.capability_id == capability_id)
                self.assertEqual(inv.versions["host_template"], f"{capability_id}.task@1.0.0")

    async def test_the_same_request_compiles_to_the_same_packet_text_in_two_runs(self) -> None:
        for capability_id in SCHEMAS:
            with self.subTest(capability_id):
                first, second = await start(host_rig(capability_id)), await start(
                    host_rig(capability_id))
                self.assertEqual(first.packet["goal"], second.packet["goal"])
                self.assertEqual(first.packet["output_requirements"],
                                 second.packet["output_requirements"])

    async def test_options_are_integrated_as_proposals_within_the_requested_maximum(self) -> None:
        _, _, state = await self.run_operation("host.generate_options")
        payload = host_result(state, "host.generate_options").output_payload
        self.assertEqual([o["id"] for o in payload["options"]], ["opt-a", "opt-b"])
        for item in (*payload["options"], *payload["proposed_criteria"]):
            self.assertEqual((item["proposal_status"], item["approval_status"]),
                             ("proposed", "proposed"))

    async def test_research_evidence_lands_in_state_as_host_reported(self) -> None:
        _, _, state = await self.run_operation("host.research")
        (evidence,) = [e for e in state["evidence"].values() if e.source.locator ==
                       "docs/cache.md#L1"]
        self.assertIs(evidence.verification, Verification.HOST_REPORTED)
        self.assertEqual(evidence.source.kind.value, "host_research")

    async def test_synthesis_findings_land_in_state_as_inferences(self) -> None:
        _, _, state = await self.run_operation("host.synthesize")
        (finding,) = state["findings"].values()
        self.assertEqual(finding.kind.value, "inference")

    async def test_the_question_result_keeps_the_kernel_choices(self) -> None:
        _, _, state = await self.run_operation("host.formulate_question")
        body = host_result(state, "host.formulate_question").output_payload
        self.assertEqual([c["id"] for c in body["choices"]], ["sqlite", "files"])
        self.assertEqual(body["schema_version"], "1.0")
        self.assertEqual(schema_ids.HUMAN_QUESTION_REQUEST, SCHEMAS["host.formulate_question"][1])


class TestHostTelemetry(unittest.IsolatedAsyncioTestCase):
    """One `host.<operation>` event per answer, with the fingerprint and honest usage."""

    async def answered(self, capability_id: str, **extra: Any) -> tuple[Started, dict]:
        run = await start(host_rig(capability_id))
        await run.submit(raw_submission(run.packet, run.run_id,
                                        response=RESPONSES[capability_id], **extra))
        (call,) = run.rig.tracer.named(f"host.{OPERATIONS[capability_id]}", "event")
        return run, call.data["payload"]

    async def test_each_operation_emits_its_event_with_the_packet_fingerprint(self) -> None:
        for capability_id in SCHEMAS:
            with self.subTest(capability_id):
                run, payload = await self.answered(capability_id)
                ref = parse_compiled_by(run.packet["output_requirements"])
                self.assertEqual(payload["prompt_fingerprint"], ref.fingerprint)
                self.assertEqual(payload["template"], f"{capability_id}.task@1.0.0")
                self.assertEqual(payload["prompt"], run.packet["goal"])
                self.assertEqual(payload["result_status"], "completed")
                self.assertGreaterEqual(payload["elapsed_ms"], 0)

    async def test_unreported_usage_is_unavailable_not_zero(self) -> None:
        _, payload = await self.answered("host.research")
        self.assertFalse(payload["usage_available"])
        self.assertIsNone(payload["usage"])

    async def test_reported_usage_is_recorded_as_given(self) -> None:
        usage = [{"provider": "host", "model_id": "claude-x", "input_tokens": 12}]
        _, payload = await self.answered("host.research", usage=usage)
        self.assertTrue(payload["usage_available"])
        self.assertEqual(payload["usage"][0]["input_tokens"], 12)
        self.assertIsNone(payload["usage"][0]["output_tokens"])
        self.assertIsNone(payload["usage"][0]["cost_usd"])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 12:30 [python-coder]: Rigs, payloads and canned answers live in `host_rigs` so the
#   security tests drive the same four operations. (#KernelBootstrapV0/P8)
# ====================================================================
