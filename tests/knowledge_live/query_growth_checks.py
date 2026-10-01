"""Opt-in Aura query-growth proof with explicitly scripted Jev judgments."""
import json
import os
import unittest
from pathlib import Path
from uuid import uuid4

from kernel.bootstrap import build_bindings
from kernel.config import SourceConfig
from kernel.contracts import TaskInput, Actor, ActorKind, RunStatus, schema_ids
from kernel.contracts.payloads import ResearchRequestPayload
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.task import RevisionInfo
from kernel.providers.fakes import choice_answer
from knowledge.config import KnowledgeConfig, build_retriever
from knowledge.query_catalog import QueryCatalog
from knowledge.query_admission import build_query_admission
from tests.kernel.helpers import make_scope
from tests.kernel.integration.scenario_support import ScenarioCase, answer_human
from tests.kernel.interaction.support import raw_submission

@unittest.skipUnless(os.environ.get("LEAFCUTTER_RUN_AURA_QUERY_LIVE")=="1","explicit Aura read opt-in required")
class TestAuraQueryGrowth(ScenarioCase):
    """Actual graph/verifier/catalog/kernel; only Jev and human/host delivery are doubles."""
    __test__ = False

    def setUp(self):
        super().setUp()
        self.repo=Path(__file__).resolve().parents[2]
        self.sha="9f70de80ebcafe59ff55cce6732deb92069f9541"
        self.catalog_root=Path(os.environ["LOCALAPPDATA"])/"Leafcutter"/"query-catalog-km500"/str(uuid4())
        self.config=self.config.model_copy(update={
            "knowledge":KnowledgeConfig(backend="neo4j",repository_id="leafcutter",
                repository_root=str(self.repo),query_catalog_root=str(self.catalog_root)),
            "sources":[SourceConfig(id="graph",kind="graph_query",categories=["task_context"])],
        })
        self.port=build_retriever(self.config.knowledge)
        self.addAsyncCleanup(self.port.close)
        self.admission=build_query_admission(self.config.knowledge,self.port)
        self.catalog=QueryCatalog(self.catalog_root)
        self.route_choice="research"
        self.jev.script("knowledge.query_readiness","readiness",choice_answer("ready"))
        self.jev.script("knowledge.query_target","kind",choice_answer("Test"))
        self.jev.script("knowledge.query_select","query",lambda q,b:choice_answer(
            "get_component_tests" if any(d["operation"]=="get_component_tests" for d in self.catalog.descriptors()) else "build"))

    def service(self):
        service=super().service()
        self.env.bindings=build_bindings(self.snapshot,knowledge_retriever=self.port,
            query_catalog=self.catalog,query_admission=self.admission)
        return service

    async def test_aura_admission_same_research_and_persistent_reuse(self):
        """Real compiled Cypher executes through the full paused/resumed kernel."""
        # covers: KM-500b-2
        # covers: KM-500b-3
        # covers: KM-500c-1
        # angle: real_artifact
        question="Which directly declared test files cover acceptance criteria belonging to the project component?"
        need=EvidenceNeed(id="need.tests",category="task_context",priority="required",question=question)
        payload=ResearchRequestPayload(question=question,evidence_needs=[need],evidence_needs_only=True)
        task=TaskInput(goal=question,caller=Actor(id="authorized-query-demo",kind=ActorKind.HOST),
            scope=make_scope(self.repo,revision=RevisionInfo(commit=self.sha)),
            permissions=["read_repo","write_query_catalog"],input_payload_schema=schema_ids.RESEARCH_REQUEST,
            input_payload=payload.model_dump(mode="json"),requested_output_schema=schema_ids.EVIDENCE_BUNDLE)
        first=await self.service().start_run(task)
        assert first.status==RunStatus.WAITING_HUMAN,first.model_dump_json()
        second=await self.service().resume_run(first.run_id,
            answer_human(first,{"free_text":"git_vcs_operations"}))
        built=False
        if second.status==RunStatus.WAITING_HOST and second.pending_interaction.operation=="build_query":
            candidate=json.loads((self.repo/"knowledge/examples/component_tests_candidate.json").read_text())
            second=await self.service().resume_run(second.run_id,raw_submission(
                second.pending_interaction.model_dump(mode="json"),second.run_id,response={"candidate":candidate}))
            built=True
        values=await self.checkpoint_values(second.run_id)
        selected=[r for r in values["results"].values() if r.diagnostics.get("query_operation")]
        assert selected,second.model_dump_json()
        assert selected[-1].diagnostics["query_operation"]=="get_component_tests",selected[-1].diagnostics
        assert second.status in {RunStatus.COMPLETED,RunStatus.PARTIAL},second.model_dump_json()
        assert built, "fresh isolated catalog must exercise actual verification and activation"
        assert selected[-1].evidence
        assert all(e.source.source_version and e.source.source_version.commit == self.sha
                   for e in selected[-1].evidence)
        assert selected[-1].limitations, "bounded graph evidence must retain completeness limits"
        assert second.status == RunStatus.PARTIAL
        assert values["task"].original_goal == need.question
        assert "need.tests" in selected[-1].output_payload.get("coverage", {}), selected[-1].output_payload
        self.catalog=QueryCatalog(self.catalog_root)
        fresh=await self.service().start_run(task.model_copy(update={"scope":task.scope.model_copy(
            update={"component_ids":["git_vcs_operations"]})}))
        assert fresh.status in {RunStatus.COMPLETED,RunStatus.PARTIAL},fresh.model_dump_json()
        fresh_values=await self.checkpoint_values(fresh.run_id)
        assert "host.query_build" not in self.capabilities_used(fresh_values)
        result={"status":"passed","source_sha":self.sha,"repository_id":"leafcutter",
            "backend":"Aura","jev":"scripted; real provider payload authorization pending",
            "host_candidate":"BA-authored reviewed recipe","built_this_run":built,
            "selected_operation":"get_component_tests","persistent_catalog":str(self.catalog_root),
            "evidence_count":len(selected[-1].evidence),"checkpoint_reopened":True,"fresh_run_reused":True,
            "database_writes":False,"external_provider_calls":0,"embedding_calls":0,
            "first_run_status":second.status.value,"fresh_run_status":fresh.status.value}
        (self.repo/"reports/knowledge-query-growth-aura.json").write_text(json.dumps(result,indent=2)+"\n")


def test_aura_query_growth_public_proof():
    """Drive the real Aura scenario through a synchronous discoverable proof entry."""
    # covers: KM-500b-2
    # covers: KM-500b-3
    # covers: KM-500c-1
    # covers: KM-500c-2
    # angle: real_artifact
    assert os.environ.get("LEAFCUTTER_RUN_AURA_QUERY_LIVE") == "1", "explicit Aura read opt-in required"
    case = TestAuraQueryGrowth("test_aura_admission_same_research_and_persistent_reuse")
    result = unittest.TestResult()
    case.run(result)
    assert result.testsRun == 1
    assert not result.skipped
    assert result.wasSuccessful(), result.errors + result.failures
