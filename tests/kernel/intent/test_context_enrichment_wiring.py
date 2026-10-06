"""Fresh-run scenarios migrated from lexical DK-200 to entity DK-300 semantics.

The source-independent DK-200 gather/projection tests remain unchanged. Reuse the
new behavioral scenarios here so the historical service entry points stay tested
without retaining a hidden lexical fallback or duplicating their assertions.
"""

import asyncio
import unittest

from kernel.contracts import CallerContext
from tests.kernel.entity_context.conftest import EntityServiceRig
from tests.kernel.entity_context.test_continuation import (
    test_downstream_judgments_and_host_artifacts_keep_meanings_separate as _host,
    test_human_and_host_resume_reuse_original_entity_checkpoint as _resume,
    test_routed_capability_consumes_canonical_hints_after_intent as _retrieval,
)
from tests.kernel.entity_context.test_permissions import (
    test_data_policy_withholds_all_repository_meaning_metadata as _policy,
)
from tests.kernel.entity_context.test_wiring import (
    test_explicit_output_contract_retains_routing_with_entity_context as _explicit,
    test_service_checkpoints_entity_context_before_classifier_consumes_it as _consume,
)


class TestContextEnrichmentWiring(unittest.TestCase):
    """Migration classification: test_drift under the user-authorized DK-300 contract."""

    def setUp(self):
        self.rig = EntityServiceRig()
        self.rig.setUp()
        self.addCleanup(self.rig.doCleanups)

    def test_repository_context_reaches_intent_before_any_human_question(self):
        # covers: DK-300d-1
        # covers: DK-200a-1
        # angle: reachability
        _consume(self.rig)

    def test_resume_reuses_checkpointed_context_instead_of_reading_changed_files(self):
        # covers: DK-300d-3-i
        # covers: DK-200a-2
        # angle: reachability
        _resume(self.rig, "human")

    def test_explicit_contract_still_gets_enriched_without_intent_classification(self):
        # covers: DK-300d-1
        # covers: DK-200a-1-i
        # angle: criterion
        _explicit(self.rig)

    def test_data_policy_withholds_repository_context_from_intent(self):
        # covers: DK-300c-3
        # angle: boundary
        _policy(self.rig)

    def test_conversation_referent_reaches_downstream_research_and_retrieval(self):
        # covers: DK-300d-3
        # covers: DK-200a-4
        # angle: reachability
        _retrieval(self.rig)

    def test_host_artifact_and_host_resume_retain_the_saved_context(self):
        # covers: DK-300d-3-i
        # covers: DK-300d-3
        # covers: DK-200a-2
        # covers: DK-200a-4
        # angle: seam
        _host(self.rig)
        _resume(self.rig, "host")

    def test_native_decision_judgments_receive_the_saved_context(self):
        # covers: DK-300d-3
        # covers: DK-200a-4
        # angle: seam
        rig = self.rig.prepare()
        rig.params["satisfies"] = {("c1", "A"): .95, ("c2", "A"): .9}
        task = rig.task("primary", known_basis=True, context=CallerContext(conversation=["Zephyr"]))
        envelope = asyncio.run(rig.service().start_run(task))
        saved = rig.values(envelope.run_id)["entity_context"]
        self.assertTrue(saved.entities)
        batches = [b for b in rig.jev.batches if b.purpose == "decision.assess"]
        self.assertTrue(batches)
        for batch in batches:
            self.assertIn("entity_context", batch.state)
            self.assertNotIn("evidence", batch.state["entity_context"])
            self.assertIn("zephyr", str(batch.state["entity_context"]))
