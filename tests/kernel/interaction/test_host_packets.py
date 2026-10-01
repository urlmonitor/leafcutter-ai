"""
MODULE: tests.kernel.interaction.test_host_packets
GOAL: Test the host-work packet contract (Rev 3 section 11.3): one operation, allowed and
    forbidden operations, a registered output schema, a bounded task statement, trace context,
    a redacted input artifact, and an options schema a host can satisfy (proposals only).
BUSINESS CONTEXT: The cooperative host is not sandboxed (section 11.5), so the packet is the whole
    contract: it must say what may be done and what may not, bound the text handed over, keep
    secrets out, and let an honest host produce output the kernel accepts.
ARCHITECTURE: Packets are produced by the real graph (open_interactions) over the scheduler Rig;
    the input artifact is read back from the artifact store the host would read.
"""

from __future__ import annotations

import json
import unittest

import jsonschema

from kernel.config import load_kernel_config
from kernel.contracts import content_hash, evidence_id, schema_ids
from kernel.contracts.payloads import OptionsPayload
from kernel.interaction.packets import MAX_TASK_STATEMENT_CHARS, bounded, tightened_schema
from kernel.contracts.schema_catalog import json_schema_for
from kernel.observability.redaction import Redactor
from tests.kernel.interaction.support import host_rig, start
from tests.kernel.scheduler.support import proposal, waiting

NEEDLE = "zq" + "-" + "Xk29" + "Lm81" + "Pv07"  # assembled so the secret scanner sees no literal
EXCERPT = "The cache must survive restarts."


class TestPacketContract(unittest.IsolatedAsyncioTestCase):
    """What the host receives."""

    async def test_operations_schema_and_limits_are_stated(self) -> None:
        run = await start(host_rig())
        packet = run.packet
        self.assertEqual(packet["operation"], "bounded_research")
        self.assertEqual(packet["allowed_operations"], ["bounded_research"])
        for forbidden in ("edit_repository", "approve_policy", "change_permissions"):
            self.assertIn(forbidden, packet["forbidden_operations"])
        self.assertIn(packet["output_schema_id"], schema_ids.KNOWN_SCHEMA_IDS)
        self.assertEqual(packet["output_json_schema"]["$id"], packet["output_schema_id"])
        self.assertEqual(packet["context_limits"]["max_input_chars"],
                         load_kernel_config().host.max_input_chars)
        self.assertIn("trace_context", packet)
        self.assertEqual(packet["work_item_id"], run.state["interactions"][packet["id"]].work_item_id)

    async def test_the_task_statement_is_bounded(self) -> None:
        rig = host_rig()
        rig.executors["decide.root"]._factory = lambda inv: waiting(
            inv, proposal(question="Q " * 5000))
        run = await start(rig)
        self.assertLessEqual(len(run.packet["goal"]), MAX_TASK_STATEMENT_CHARS)
        self.assertTrue(run.packet["goal"].endswith("[truncated]"))

    def test_bounded_leaves_short_text_alone(self) -> None:
        self.assertEqual(bounded("short"), "short")
        self.assertEqual(len(bounded("x" * 50, 30)), 30)


class TestInputArtifact(unittest.IsolatedAsyncioTestCase):
    """The redacted file the host may read."""

    async def start_with_evidence(self, excerpt: str, redactor: Redactor | None = None):
        rig = host_rig()
        locator = "docs/cache.md#L1"
        ref = evidence_id(locator, content_hash(excerpt))
        rig.executors["decide.root"]._factory = lambda inv: waiting(
            inv, proposal(context_refs=[ref]))
        note = {"title": "Cache note", "excerpt": excerpt, "locator": locator}
        return await start(rig, redactor=redactor, initial_evidence=[note])

    async def test_the_artifact_holds_the_request_and_the_cited_evidence(self) -> None:
        run = await self.start_with_evidence(EXCERPT)
        (ref,) = run.packet["input_artifact_refs"]
        name = ref.replace("\\", "/").rsplit("/", 1)[-1]
        body = json.loads(run.rig.artifacts.read_artifact(run.run_id, name))
        self.assertEqual(body["interaction_id"], run.packet["id"])
        self.assertEqual([e["excerpt"] for e in body["evidence"]], [EXCERPT])
        self.assertEqual(run.packet["input_evidence_ids"], [e["id"] for e in body["evidence"]])
        self.assertEqual(body["request_schema"], schema_ids.RETRIEVAL_REQUEST)

    async def test_secrets_in_evidence_and_goal_are_masked_in_the_packet_and_the_artifact(self) -> None:
        redactor = Redactor({"cache_key": NEEDLE}, load_kernel_config().data_policy)
        run = await self.start_with_evidence(f"Use {NEEDLE} for the cache.", redactor)
        (ref,) = run.packet["input_artifact_refs"]
        name = ref.replace("\\", "/").rsplit("/", 1)[-1]
        text = run.rig.artifacts.read_artifact(run.run_id, name).decode("utf-8")
        self.assertNotIn(NEEDLE, text)
        self.assertIn("[REDACTED:cache_key]", text)
        self.assertNotIn(NEEDLE, json.dumps(run.packet))


class TestOptionsSchema(unittest.TestCase):
    """The options packet states that generated options and criteria are proposals."""

    def setUp(self) -> None:
        """Build the tightened schema and two payloads."""
        self.schema = tightened_schema(schema_ids.OPTIONS, json_schema_for(schema_ids.OPTIONS))
        option = {"id": "A", "title": "Use sqlite", "proposal_status": "proposed",
                  "approval_status": "proposed", "proposed_by": "host"}
        self.good = {"options": [option], "proposed_criteria": []}
        self.approved = {"options": [{**option, "approval_status": "approved",
                                      "approved_by": "host"}], "proposed_criteria": []}

    def test_an_honest_payload_satisfies_the_schema_and_the_model(self) -> None:
        jsonschema.validate(self.good, self.schema)
        OptionsPayload.model_validate(self.good)

    def test_a_pre_approved_option_violates_the_schema(self) -> None:
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(self.approved, self.schema)

    def test_the_plain_catalog_schema_could_not_express_the_rule(self) -> None:
        jsonschema.validate(self.approved, json_schema_for(schema_ids.OPTIONS))

    def test_other_schemas_are_returned_unchanged(self) -> None:
        findings = json_schema_for(schema_ids.FINDINGS)
        self.assertEqual(tightened_schema(schema_ids.FINDINGS, findings), findings)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: The `other schemas unchanged` check uses findings.v1: the
#   evidence bundle schema is now relaxed for hosts on purpose. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:59 [python-coder]: The "catalog schema could not express the rule" test pins
#   why the packet tightens the schema: a plain options.v1 schema accepts a pre-approved option,
#   which the semantic check then rejects. (#KernelBootstrapV0/P6)
# ====================================================================
