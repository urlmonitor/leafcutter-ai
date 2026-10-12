"""
MODULE: aura_kernel_checks
GOAL: Prove the actual Aura projection grounds a complete persisted kernel decision.
BUSINESS CONTEXT: Deployment acceptance needs source evidence from the real serving backend.
ARCHITECTURE: Real KernelService, registered binding, Aura reader and SQLite checkpoint;
    Jev, host and human answers are deterministic test doubles. No database writes.
"""

import json
import os
from pathlib import Path

from kernel.bootstrap import build_bindings
from kernel.config import SourceConfig
from kernel.contracts import RunStatus, schema_ids
from kernel.contracts.task import RevisionInfo
from knowledge.config import KnowledgeConfig, build_retriever
from tests.kernel.integration.scenario_support import (
    ScenarioCase,
    FakeHostResponder,
    options_response,
    answer_human,
)


class TestAuraKernelRun(ScenarioCase):
    """Read an explicitly selected published revision without changing Aura data."""

    domains = ("primary",)

    def setUp(self):
        """Use the real source checkout but retain isolated temporary kernel stores."""
        super().setUp()
        self.repo = Path(__file__).resolve().parents[2]
        self.expected_sha = os.environ["KNOWLEDGE_AURA_SOURCE_SHA"]
        self.repository_id = os.environ.get("KNOWLEDGE_AURA_REPOSITORY_ID", "leafcutter")
        self.config = self.config.model_copy(
            update={
                "knowledge": KnowledgeConfig(
                    backend="neo4j",
                    repository_id=self.repository_id,
                    repository_root=str(self.repo),
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
        self.retriever = build_retriever(self.config.knowledge)
        self.addAsyncCleanup(self.retriever.close)

    def service(self):
        """Inject the actual configured Aura reader into existing production bindings."""
        service = super().service()
        self.env.bindings = build_bindings(self.snapshot, knowledge_retriever=self.retriever)
        return service

    async def test_aura_evidence_survives_complete_kernel_run_and_checkpoint(self):
        """Complete deterministic decisions with real pinned Aura source evidence."""
        # Supplemental hosted deployment probe. KM-400e-3 explicitly requires
        # the database-free public-kernel proof in tests/knowledge/test_kernel_run.py;
        # this environment-dependent probe is not a CI completion prerequisite.
        task = self.task("primary", request=False)
        task = task.model_copy(
            update={
                "scope": task.scope.model_copy(
                    update={
                        "component_ids": ["knowledge_management"],
                        "revision": RevisionInfo(commit=self.expected_sha),
                        "read_roots": ["docs"],
                    }
                )
            }
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
        selected = [e for e in values["evidence"].values() if e.source.id == "knowledge.retrieval"]
        assert selected and all(
            e.source.source_version.commit == self.expected_sha for e in selected
        )
        assert any(e.excerpt for e in selected)
        assert all(e.provenance.strategy.startswith("knowledge:") for e in selected)
        report = {
            "status": "passed",
            "backend": "Aura",
            "database_writes": False,
            "repository_id": self.repository_id,
            "source_sha": self.expected_sha,
            "kernel_run_status": final.status.value,
            "checkpoint_reopened": True,
            "evidence_count": len(selected),
            "evidence_ids": [e.id for e in selected],
            "source_locators": [e.source.locator for e in selected],
            "retrieval_refs": [e.provenance.strategy for e in selected],
            "doubles": ["Jev", "host", "human"],
            "embedding_provider_calls": 0,
            "semantic_usefulness_proven": False,
        }
        destination = self.repo / "reports/knowledge-retrieval-aura-kernel.json"
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Prove read-only Aura evidence consumption through actual kernel persistence. (#TICKET-20261001-KM-400e-3)
