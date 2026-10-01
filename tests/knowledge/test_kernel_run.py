"""
MODULE: test_kernel_run
GOAL: Prove optional graph evidence survives the full kernel run and checkpoint.
BUSINESS CONTEXT: Retrieval must ground actual decisions rather than only helper outputs.
ARCHITECTURE: Existing ScenarioCase real service/stores/checkpoint with an offline knowledge port.
"""

from kernel.bootstrap import build_bindings
from kernel.config import SourceConfig
from kernel.contracts import RunStatus, schema_ids
from knowledge.config import KnowledgeConfig
from knowledge.contracts import Entity, KnowledgeEvidence, KnowledgeRetrievalResult, SourceReference
from tests.kernel.integration.scenario_support import (
    ScenarioCase,
    FakeHostResponder,
    options_response,
    answer_human,
)


class TestKnowledgeRun(ScenarioCase):
    """Complete a grounded decision and reopen its persisted checkpoint."""

    domains = ("primary",)

    def setUp(self):
        """Bind the trusted fixture repository to a graph source without network setup."""
        super().setUp()
        self.config = self.config.model_copy(
            update={
                "knowledge": KnowledgeConfig(
                    backend="neo4j", repository_id="fixture", repository_root=str(self.repo)
                ),
                "sources": [
                    SourceConfig(
                        id="knowledge.graph",
                        kind="graph_query",
                        categories=[
                            "prior_decisions",
                            "task_context",
                            "existing_patterns",
                            "internal_principles",
                        ],
                    )
                ],
            }
        )
        self.calls = []

    def service(self):
        """Inject the fake port through the real production binding builder."""
        service = super().service()
        owner = self

        class Port:
            """Return attributable fixture evidence at the selected disclosure."""

            async def capabilities(self):
                """Advertise graph only so no semantic service is needed."""
                return {"graph": True}

            async def retrieve(self, request):
                """Record the actual request and return the declared fixture source."""
                owner.calls.append(request)
                return KnowledgeRetrievalResult(
                    request_id=request.request_id,
                    retrieval_id="run-retrieval",
                    status="ok",
                    requested_mode=request.mode,
                    executed_mode=request.mode,
                    source_sha="a" * 40,
                    generation_id="fixture-generation",
                    evidence=[
                        KnowledgeEvidence(
                            entity=Entity(
                                canonical_id="ADR-900",
                                kind="ADR",
                                title="Capability shape",
                                source=SourceReference(
                                    repository_id="fixture",
                                    source_sha="a" * 40,
                                    path="docs/architecture/adrs/ADR-900-capability-shape.md",
                                ),
                            ),
                            content="Use an encapsulated subgraph for isolated state."
                            if request.disclosure_level
                            else None,
                            disclosure_level=request.disclosure_level,
                        )
                    ],
                )

        self.env.bindings = build_bindings(self.snapshot, knowledge_retriever=Port())
        return service

    async def test_full_run_persists_attributable_knowledge_evidence(self):
        """A host sees the evidence, the run completes, and fresh checkpoint reads retain it."""
        # angle: criterion
        # angle: reachability
        # covers: KM-400e-3
        task = self.task("primary", request=False)
        task = task.model_copy(
            update={"scope": task.scope.model_copy(update={"component_ids": ["decision_kernel"]})}
        )
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        paused = await self.service().start_run(task)
        assert paused.status == RunStatus.WAITING_HOST
        assert paused.pending_interaction.input_evidence_ids
        responder = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
        approval = await self.service().resume_run(paused.run_id, responder.answer(paused))
        assert approval.status == RunStatus.WAITING_HUMAN
        final = await self.service().resume_run(
            paused.run_id, answer_human(approval, {"choice_id": "approve"})
        )
        assert final.status == RunStatus.COMPLETED
        values = await self.checkpoint_values(final.run_id)
        assert "retrieve.repository" in self.capabilities_used(values)
        evidence = list(values["evidence"].values())
        selected = [e for e in evidence if e.source.id == "knowledge.retrieval"]
        assert selected and all(e.source.source_version.commit == "a" * 40 for e in selected)
        assert all("run-retrieval" in e.provenance.strategy for e in selected)
        assert any(e.excerpt and "subgraph" in e.excerpt for e in selected)
        assert self.calls


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Verify integration through persisted full decision flow. (#TICKET-20261001-KM-400e-3)
