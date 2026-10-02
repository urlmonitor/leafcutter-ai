"""MODULE: query_growth_local_checks
GOAL: Repeatable real-Neo4j query growth through the public kernel API.
BUSINESS CONTEXT: CI must prove query growth without implicit hosted-service consent.
ARCHITECTURE: Public kernel over immutable Git and the local CI database.

The database is the fixed loopback CI fixture, never .env/Aura. Each scenario
owns a unique repository namespace and removes only that namespace. Git,
projection, Cypher, admission, catalog files and checkpoints are real; Jev,
the human answer and the coding/synthesis host are explicitly controlled.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from uuid import uuid4

import pytest
import yaml

from kernel.bootstrap import build_bindings
from kernel.config import SourceConfig
from kernel.contracts import Actor, ActorKind, RunStatus, TaskInput, schema_ids
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import ResearchRequestPayload
from kernel.contracts.task import RevisionInfo
from kernel.providers.fakes import choice_answer
from knowledge.adapters.git_source import GitSourceResolver
from knowledge.adapters.neo4j_backend import Neo4jBackend
from knowledge.config import KnowledgeConfig
from knowledge.projection.canonical_loader import load_snapshot
from knowledge.query_admission import QueryAdmission
from knowledge.query_catalog import QueryCatalog
from knowledge.query_compile import digest_data
from knowledge.service import KnowledgeService
from tests.kernel.helpers import make_scope
from tests.kernel.integration.scenario_support import ScenarioCase, answer_human
from tests.kernel.interaction.support import raw_submission
from tests.knowledge.query_answer_contract_acceptance_research_support import complete_requested_synthesis
from tests.knowledge.test_projection import commit, repository


class LocalQueryGrowthCase(ScenarioCase):
    """Exercise a tiny immutable canonical store in the existing local CI service."""

    __test__ = False

    def setUp(self):
        """Build immutable source and bind only the isolated loopback database."""
        super().setUp()
        self.repository_id = "query-proof-" + uuid4().hex
        self.repo, _ = repository.__wrapped__(self.repo)
        component_path = self.repo / "docs/components.json"
        components = json.loads(component_path.read_text())
        components["components"]["release_manager"] = {"name": "Empty component"}
        component_path.write_text(json.dumps(components), encoding="utf-8")
        self.test_id = "tests/test_declared.py"
        test_path = self.repo / self.test_id
        test_path.parent.mkdir()
        test_path.write_text("def test_declared():\n    assert 1 + 1 == 2\n", encoding="utf-8")
        ac_path = self.repo / "docs/acs/criterion.yaml"
        ac = yaml.safe_load(ac_path.read_text())
        ac["covered_by"] = [self.test_id]
        ac_path.write_text(yaml.safe_dump(ac), encoding="utf-8")
        self.sha = commit(self.repo)
        self.projection = load_snapshot(self.repo, self.repository_id, self.sha)
        self.db = Neo4jBackend("bolt://127.0.0.1:17687", "neo4j", "leafcutter-local-tests")
        self.addAsyncCleanup(self.db.close)
        self.addAsyncCleanup(self.clean_namespace)
        self.catalog_root = self.run_root / "query-catalog"
        self.reopen_catalog()
        self.config = self.config.model_copy(update={
            "knowledge": KnowledgeConfig(backend="neo4j", repository_id=self.repository_id,
                repository_root=str(self.repo), query_catalog_root=str(self.catalog_root)),
            "sources": [SourceConfig(id="graph", kind="graph_query", categories=["task_context"])],
        })
        self.route_choice = "research"
        self.jev.script("knowledge.query_readiness", "readiness", choice_answer("ready"))
        self.jev.script("knowledge.query_target", "kind", choice_answer("Test"))
        self.jev.script("knowledge.query_select", "query", lambda q, b: choice_answer(
            "get_component_tests" if any(d["operation"] == "get_component_tests"
            for d in self.catalog.descriptors()) else "build"))

    def reopen_catalog(self):
        """Reconstruct all catalog consumers from durable files, without seeding entries."""
        self.catalog = QueryCatalog(self.catalog_root)
        self.admission = QueryAdmission(self.catalog, self.db, self.repository_id)
        self.port = KnowledgeService(self.db, source_resolver=GitSourceResolver(self.repo),
                                     query_catalog=self.catalog)

    async def clean_namespace(self):
        """Delete only this test's UUID namespace from the fixed loopback fixture."""
        assert self.repository_id.startswith("query-proof-")
        await self.db._run("MATCH (n {repository_id:$repo}) DETACH DELETE n",
                           {"repo": self.repository_id}, True)

    def service(self):
        """Reopen the public service with real admission and retrieval bindings."""
        service = super().service()
        self.env.bindings = build_bindings(self.snapshot, knowledge_retriever=self.port,
                                          query_catalog=self.catalog, query_admission=self.admission)
        return service

    def candidate(self):
        """Reuse the actual authored recipe; expectations come from this fixture's source."""
        path = Path(__file__).resolve().parents[2] / "knowledge/examples/component_tests_candidate.json"
        candidate = json.loads(path.read_text(encoding="utf-8"))
        candidate["reviewer"] = "Controlled fixture author; not independent semantic approval"
        candidate["cases"][0] = {"name": "one_declared_test", "arguments": {
            "component_ids": ["knowledge_management"]}, "expected_ids": [self.test_id]}
        candidate["cases"][1] = {"name": "empty_existing_component", "arguments": {
            "component_ids": ["release_manager"]}, "expected_ids": []}
        return candidate

    def research_task(self):
        """Ask the original need, leaving the missing component for human clarification."""
        question = "Which directly declared test files cover acceptance criteria belonging to the project component?"
        need = EvidenceNeed(id="need.tests", category="task_context", priority="required", question=question)
        payload = ResearchRequestPayload(question=question, evidence_needs=[need], evidence_needs_only=True,
            answer_requirements={"original_question": question, "required_fields": ["canonical_id"],
                                 "scope": {"population": "returned_entities"}, "require_complete": True})
        return TaskInput(goal=question, caller=Actor(id="local-proof", kind=ActorKind.HOST),
            scope=make_scope(self.repo, revision=RevisionInfo(commit=self.sha)),
            permissions=["read_repo", "write_query_catalog"], input_payload_schema=schema_ids.RESEARCH_REQUEST,
            input_payload=payload.model_dump(mode="json"), requested_output_schema=schema_ids.EVIDENCE_BUNDLE)

    async def assert_query_result(self, result, task):
        """Check actual consumer evidence and limits after the normal synthesis boundary."""
        final = await complete_requested_synthesis(self, result)
        values = await self.checkpoint_values(final.run_id)
        selected = [r for r in values["results"].values() if r.diagnostics.get("query_operation")]
        assert selected, final.model_dump_json()
        query = selected[-1]
        assert query.diagnostics["query_operation"] == "get_component_tests"
        assert query.evidence
        assert all(e.source.source_version.commit == self.sha for e in query.evidence)
        assert any(self.test_id in e.source.locator for e in query.evidence)
        assert query.limitations, "Declared test references cannot prove execution or completeness"
        assert final.status == RunStatus.PARTIAL, final.model_dump_json()
        assert values["task"].original_goal == task.goal
        assert "need.tests" in query.output_payload.get("coverage", {})
        return final, values

    async def scenario(self):
        """Reject a bad candidate, build once through public resume, then reuse durably."""
        await self.db.setup()
        assert await self.db.publish(self.projection)
        active = await self.db.active(self.repository_id)
        assert active.source_sha == self.sha and active.generation_id == self.projection.generation_id
        bad = deepcopy(self.candidate())
        bad["cases"][0]["expected_ids"] = ["invented.py"]
        with pytest.raises(ValueError, match="expectation"):
            await self.admission.verify_and_activate(bad, repository_id=self.repository_id, source_sha=self.sha)
        assert not any(d["operation"] == "get_component_tests" for d in self.catalog.descriptors())
        task = self.research_task()
        first = await self.service().start_run(task)
        assert first.status == RunStatus.WAITING_HUMAN, first.model_dump_json()
        coding = await self.service().resume_run(first.run_id, answer_human(first, {"free_text": "knowledge_management"}))
        assert coding.status == RunStatus.WAITING_HOST, coding.model_dump_json()
        assert coding.pending_interaction.operation == "build_query"
        result = await self.service().resume_run(coding.run_id, raw_submission(
            coding.pending_interaction.model_dump(mode="json"), coding.run_id, response={"candidate": self.candidate()}))
        final, values = await self.assert_query_result(result, task)
        assert final.run_id == first.run_id
        assert "knowledge.activate_query" in self.capabilities_used(values)
        saved = json.loads((self.catalog_root / "catalog.json").read_text(encoding="utf-8"))
        digest = saved["active"]["get_component_tests"]
        entry = saved["entries"][digest]
        proof = entry["verification"]
        assert entry["compiled"]["digest"] == proof["digest"] == digest
        assert entry["verification_digest"] == digest_data(proof)
        assert proof["source_sha"] == self.sha
        assert proof["generation_id"] == self.projection.generation_id
        checks = proof["checks"]
        assert checks["declared_cases_passed"] == 2
        assert checks["cases"][0]["actual_ids"] == [self.test_id]
        assert checks["cases"][1]["actual_ids"] == []
        assert checks["invalid_input_rejected"] and checks["bound_injection_empty"]
        assert checks["foreign_scope_rejected"] and checks["semantic_usefulness_proven"] is False
        self.reopen_catalog()
        fresh = await self.service().start_run(task.model_copy(update={
            "scope": task.scope.model_copy(update={"component_ids": ["knowledge_management"]})}))
        reused, fresh_values = await self.assert_query_result(fresh, task)
        assert reused.run_id != final.run_id
        assert "host.query_build" not in self.capabilities_used(fresh_values)
        assert "knowledge.activate_query" not in self.capabilities_used(fresh_values)


def test_local_query_growth_public_proof():
    # covers: KM-500b-2
    # covers: KM-500b-3
    # covers: KM-500c-1
    # covers: KM-500c-2
    # angle: real_artifact
    """Run real local graph mechanics; scripted actors make no live-quality claim."""
    case = LocalQueryGrowthCase("scenario")
    result = unittest.TestResult()
    case.run(result)
    assert result.testsRun == 1 and not result.skipped
    assert result.wasSuccessful(), result.errors + result.failures


# DECISION HISTORY
# ========================================
# - 2026-10-02 16:00 [test-writer]: Preserve hosted opt-in while proving the same public mechanics locally. (#TICKETLESS reason=required-ci-proof-repair)
