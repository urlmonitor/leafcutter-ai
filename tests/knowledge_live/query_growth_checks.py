"""Repeatable local Neo4j query-growth proof and an explicit hosted Aura probe.

The required proof publishes a tiny committed fixture to the disposable loopback
service. The Aura probe is supplemental historical-environment validation; it
requires an explicit opt-in and never writes the hosted database.
"""
import json
import os
import unittest
from pathlib import Path
from uuid import uuid4

import yaml

from kernel.bootstrap import build_bindings
from kernel.config import SourceConfig
from kernel.contracts import TaskInput, Actor, ActorKind, RunStatus, schema_ids
from kernel.contracts.payloads import ResearchRequestPayload
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.task import RevisionInfo
from kernel.providers.fakes import choice_answer, noul_answer
from knowledge.config import KnowledgeConfig, build_retriever
from knowledge.query_catalog import QueryCatalog
from knowledge.query_admission import QueryAdmission, build_query_admission
from tests.knowledge import test_projection
from tests.knowledge.test_query_admission import candidate
from tests.kernel.helpers import make_scope
from tests.kernel.integration.scenario_support import ScenarioCase, answer_human
from tests.kernel.interaction.support import raw_submission

repository = test_projection.repository


class QueryGrowthScenario(ScenarioCase):
    """Real graph/verifier/catalog/kernel; Jev and human/host delivery are scripted."""
    __test__ = False

    def configure(self):
        self.catalog_root = self.run_root / "query-catalog"
        self.config = self.config.model_copy(update={
            "knowledge": KnowledgeConfig(
                backend="neo4j", repository_id=self.repository_id,
                repository_root=str(self.repo), query_catalog_root=str(self.catalog_root)),
            "sources": [SourceConfig(id="graph", kind="graph_query", categories=["task_context"])],
            # This proof ends at the evidence bundle. Separate linked research
            # tests exercise the optional host-synthesis continuation.
            "research": self.config.research.model_copy(update={"allow_synthesis": False}),
        })
        self.catalog = QueryCatalog(self.catalog_root)
        self.route_choice = "research"
        self.jev.script("knowledge.answer_contract", "field.*", lambda q, b:
                        noul_answer(0.99 if q.id == "field.canonical_id" else 0.01))
        self.jev.script("knowledge.answer_contract", "population", choice_answer("returned_entities"))
        self.jev.script("knowledge.answer_contract", "inclusion", choice_answer("clarify"))
        self.jev.script("knowledge.answer_contract", "root", choice_answer("clarify"))
        self.jev.script("knowledge.answer_contract", "level.*", noul_answer(0.01))
        self.jev.script("knowledge.query_readiness", "readiness", choice_answer("ready"))
        self.jev.script("knowledge.query_target", "kind", choice_answer("Test"))
        self.jev.script("knowledge.query_select", "query", lambda q, b: choice_answer(
            "get_component_tests" if any(d["operation"] == "get_component_tests"
                                        for d in self.catalog.descriptors()) else "build"))

    def service(self):
        service = super().service()
        self.env.bindings = build_bindings(
            self.snapshot, knowledge_retriever=self.port,
            query_catalog=self.catalog, query_admission=self.admission)
        return service

    async def exercise_query_growth(self):
        """Execute compiled Cypher through the paused/resumed public kernel service."""
        question = "Which directly declared test files cover acceptance criteria belonging to the project component?"
        need = EvidenceNeed(id="need.tests", category="task_context", priority="required", question=question)
        payload = ResearchRequestPayload(question=question, evidence_needs=[need], evidence_needs_only=True)
        task = TaskInput(
            goal=question, caller=Actor(id="authorized-query-demo", kind=ActorKind.HOST),
            scope=make_scope(self.repo, revision=RevisionInfo(commit=self.sha)),
            permissions=["read_repo", "write_query_catalog"], input_payload_schema=schema_ids.RESEARCH_REQUEST,
            input_payload=payload.model_dump(mode="json"), requested_output_schema=schema_ids.EVIDENCE_BUNDLE)
        first = await self.service().start_run(task)
        assert first.status == RunStatus.WAITING_HUMAN, first.model_dump_json()
        second = await self.service().resume_run(first.run_id, answer_human(first, {"free_text": self.component_id}))
        assert second.run_id == first.run_id
        assert second.status == RunStatus.WAITING_HOST, second.model_dump_json()
        assert second.pending_interaction.operation == "build_query"
        second = await self.service().resume_run(second.run_id, raw_submission(
            second.pending_interaction.model_dump(mode="json"), second.run_id,
            response={"candidate": self.query_candidate}))
        values = await self.checkpoint_values(second.run_id)
        selected = [r for r in values["results"].values() if r.diagnostics.get("query_operation")]
        assert selected, second.model_dump_json()
        assert selected[-1].diagnostics["query_operation"] == "get_component_tests"
        assert second.run_id == first.run_id
        assert second.status in {RunStatus.COMPLETED, RunStatus.PARTIAL}, second.model_dump_json()
        assert "knowledge.activate_query" in self.capabilities_used(values)
        assert selected[-1].evidence
        assert all(e.source.source_version and e.source.source_version.commit == self.sha
                   for e in selected[-1].evidence)
        assert selected[-1].limitations, "bounded graph evidence must retain completeness limits"
        assert second.status == RunStatus.PARTIAL
        assert values["task"].original_goal == need.question
        assert "need.tests" in selected[-1].output_payload.get("coverage", {})
        self.catalog = QueryCatalog(self.catalog_root)
        fresh = await self.service().start_run(task.model_copy(update={"scope": task.scope.model_copy(
            update={"component_ids": [self.component_id]})}))
        assert fresh.status in {RunStatus.COMPLETED, RunStatus.PARTIAL}, fresh.model_dump_json()
        assert fresh.run_id != second.run_id and fresh.evidence_ids
        fresh_values = await self.checkpoint_values(fresh.run_id)
        assert "host.query_build" not in self.capabilities_used(fresh_values)
        self.proof = {
            "status": "passed", "source_sha": self.sha, "repository_id": self.repository_id,
            "backend": self.backend_label, "jev": "scripted; no external provider calls",
            "host_candidate": self.query_candidate["reviewer"], "built_this_run": True,
            "selected_operation": "get_component_tests", "persistent_catalog": str(self.catalog_root),
            "evidence_count": len(selected[-1].evidence), "checkpoint_reopened": True,
            "fresh_run_reused": True, "query_database_writes": False,
            "fixture_publication": self.backend_label == "local Neo4j",
            "external_provider_calls": 0, "embedding_calls": 0, "allow_synthesis": False,
            "first_run_status": second.status.value, "fresh_run_status": fresh.status.value,
        }


class LocalQueryGrowth(QueryGrowthScenario):
    """Use real committed fixture files and only the disposable local database."""

    def setUp(self):
        super().setUp()
        self.repo, self.sha, self.repository_id, self.query_candidate = self.fixture
        self.component_id = "knowledge_management"
        self.backend_label = "local Neo4j"
        self.configure()

    async def asyncSetUp(self):
        from knowledge.adapters.git_source import GitSourceResolver
        from knowledge.adapters.neo4j_backend import Neo4jBackend
        from knowledge.projection.canonical_loader import load_snapshot
        from knowledge.service import KnowledgeService

        db = Neo4jBackend("bolt://127.0.0.1:17687", "neo4j", "leafcutter-local-tests")
        self.addAsyncCleanup(db.close)
        await db.setup()
        snapshot = load_snapshot(self.repo, self.repository_id, self.sha)
        assert await db.publish(snapshot)
        self.port = KnowledgeService(
            db, source_resolver=GitSourceResolver(self.repo, self.repository_id), query_catalog=self.catalog)
        self.admission = QueryAdmission(self.catalog, db, self.repository_id)


class AuraQueryGrowth(QueryGrowthScenario):
    """Supplemental read-only probe against the explicitly configured Aura snapshot."""

    def setUp(self):
        super().setUp()
        assert os.environ.get("LEAFCUTTER_RUN_AURA_QUERY_LIVE") == "1", "explicit Aura read opt-in required"
        self.repo = Path(__file__).resolve().parents[2]
        self.sha = "9f70de80ebcafe59ff55cce6732deb92069f9541"
        self.repository_id = "leafcutter"
        self.component_id = "git_vcs_operations"
        self.backend_label = "Aura"
        self.query_candidate = json.loads((self.repo / "knowledge/examples/component_tests_candidate.json").read_text())
        self.configure()
        self.port = build_retriever(self.config.knowledge)
        self.addAsyncCleanup(self.port.close)
        self.admission = build_query_admission(self.config.knowledge, self.port)


def _run_case(case):
    result = unittest.TestResult()
    case.run(result)
    assert result.testsRun == 1
    assert not result.skipped
    if not result.wasSuccessful():
        raise AssertionError("\n".join(detail for _, detail in result.errors + result.failures))
    return case.proof


def test_local_query_growth_public_proof(repository):
    """Repeatable real Neo4j/Git/kernel proof, with an isolated synthetic source corpus."""
    # covers: KM-500b-2
    # covers: KM-500b-3
    # covers: KM-500c-1
    # covers: KM-500c-2
    # angle: real_artifact
    root, _ = repository
    test_path = root / "tests/test_contract.py"
    test_path.parent.mkdir()
    test_path.write_text("def test_contract():\n    assert True\n", encoding="utf-8")
    ac_path = root / "docs/acs/criterion.yaml"
    ac = yaml.safe_load(ac_path.read_text(encoding="utf-8"))
    ac["covered_by"] = ["tests/test_contract.py::test_contract"]
    ac_path.write_text(yaml.safe_dump(ac), encoding="utf-8")
    sha = test_projection.commit(root)
    proposal = candidate()
    proposal["cases"][0]["arguments"]["component_ids"] = ["knowledge_management"]
    proposal["cases"][0]["expected_ids"] = ["tests/test_contract.py"]
    case = LocalQueryGrowth("exercise_query_growth")
    case.fixture = (root, sha, "query-growth-" + uuid4().hex, proposal)
    proof = _run_case(case)
    assert proof["backend"] == "local Neo4j"
    assert proof["source_sha"] == sha
    assert proof["built_this_run"] and proof["fresh_run_reused"]


def run_aura_query_growth_public_proof():
    """Manual opt-in hosted probe; not a CI prerequisite or a local-result claim.

    Invoke with python -c after setting LEAFCUTTER_RUN_AURA_QUERY_LIVE=1.
    Earlier recorded results retain their original test name and source SHA.
    """
    proof = _run_case(AuraQueryGrowth("exercise_query_growth"))
    report = Path(__file__).resolve().parents[2] / "reports/knowledge-query-growth-aura.json"
    report.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return proof
