"""Public kernel guards and continuations for reusable query growth."""

from types import SimpleNamespace


def test_catalog_activation_is_a_narrow_permissioned_effect():
    """# covers: KM-500b-3
    # angle: criterion
    Only the trusted activation binding may persist the query catalog.
    """
    from kernel.bootstrap import build_bindings, load_snapshot
    from kernel.config import load_kernel_config
    from kernel.contracts.enums import SideEffectClass
    from kernel.contracts.work import RequestProposal
    from kernel.registry.eligibility import filter_candidates
    from integrations.query_contracts import activation_request
    from pathlib import Path

    cfg = load_kernel_config()
    snapshot = load_snapshot(cfg, Path.cwd())
    effect = SideEffectClass.CATALOG_WRITE
    descriptor = next(d for d in snapshot.descriptors if d.id == "knowledge.activate_query")
    assert descriptor.side_effect_class == effect
    assert "write_query_catalog" in descriptor.permissions_required
    assert "catalog_write" not in {str(v) for v in __import__(
        "kernel.registry.eligibility", fromlist=["MVP_SIDE_EFFECTS"]).MVP_SIDE_EFFECTS}
    request = activation_request(candidate={}, repository_id="repo", source_sha="a" * 40)
    assert isinstance(request, RequestProposal)
    bindings = build_bindings(snapshot, query_admission=SimpleNamespace())
    common = (request, snapshot, bindings)
    denied = filter_candidates(*common, ["read_repo"], SimpleNamespace(host_operations=0), cfg,
                               operation=request.operation)
    assert not denied.eligible
    assert any(e.reason_code == "permission_denied" for e in denied.excluded
               if e.capability_id == descriptor.id)
    allowed = filter_candidates(*common, ["read_repo", "write_query_catalog"],
                                SimpleNamespace(host_operations=0), cfg,
                                operation=request.operation)
    assert allowed.selected_id == descriptor.id


def test_query_builder_is_a_real_registered_host_operation():
    """# covers: KM-500b-1
    # angle: criterion
    The coding packet has a typed candidate boundary, not an activation assertion.
    """
    from kernel.capabilities.host.registry import host_operation
    from kernel.contracts.schema_catalog import validate_payload
    from integrations.query_contracts import QUERY_BUILD_REQUEST, QUERY_CANDIDATE

    operation = host_operation("host.query_build")
    assert operation is not None
    assert operation.output_model is not None
    request = validate_payload(QUERY_BUILD_REQUEST, {
        "question": "Which tests cover this component?",
        "repository_id": "repo", "source_sha": "a" * 40,
        "generation_id": "generation", "component_ids": ["knowledge_management"],
        "need_id": "need.tests", "attempt_id": "attempt-1",
    })
    text = operation.task_text(request, request.question)
    assert "parameter" in text.lower()
    assert "test" in text.lower()
    candidate = validate_payload(QUERY_CANDIDATE, {"candidate": {"descriptor": {}, "cases": []}})
    assert "activated" not in candidate.model_dump()


from tests.kernel.integration.scenario_support import ScenarioCase, answer_human

class TestQueryGrowthRun(ScenarioCase):
    """Actual scheduler/checkpoints with scripted Jev and no external provider calls."""

    def setUp(self):
        """Configure one scoped graph need and a missing reusable recipe."""
        super().setUp()
        from kernel.config import SourceConfig
        from knowledge.config import KnowledgeConfig
        from kernel.providers.fakes import choice_answer
        self.config = self.config.model_copy(update={
            "knowledge": KnowledgeConfig(backend="neo4j",repository_id="fixture",
                repository_root=str(self.repo)),
            "sources": [SourceConfig(id="graph",kind="graph_query",categories=["task_context"])],
        })
        self.jev.script("knowledge.query_readiness", "readiness", choice_answer("ready"))
        self.jev.script("knowledge.query_target", "kind", choice_answer("Test"))
        self.query_choice="build"
        self.jev.script("knowledge.query_select", "query", lambda q,b: choice_answer(self.query_choice))
        self.route_choice = "research"
        self.catalog = SimpleNamespace(descriptors=lambda: [])
        async def pin(repository_id,source_sha="latest"):
            return {"repository_id":repository_id,"source_sha":"a"*40,"generation_id":"generation","supported_kinds":["Component","AcceptanceCriterion","Test"]}
        self.admission = SimpleNamespace(pin=pin)
        async def capabilities():
            return {"graph":True}
        self.port = SimpleNamespace(capabilities=capabilities)

    def service(self):
        """Rebuild trusted bindings each time, retaining only persisted continuation data."""
        from kernel.bootstrap import build_bindings
        service = super().service()
        self.env.bindings = build_bindings(self.snapshot, knowledge_retriever=self.port,
            query_catalog=self.catalog,query_admission=self.admission)
        return service

    async def test_clarification_restarts_then_emits_real_coding_handoff(self):
        """Clarification and construction use actual human/host ledger boundaries."""
        # covers: KM-500a-1
        # covers: KM-500b-1
        # covers: KM-500c-1
        # angle: criterion
        # angle: reachability
        from kernel.contracts import TaskInput, Actor, ActorKind, RunStatus, schema_ids
        from kernel.contracts.payloads import ResearchRequestPayload
        from kernel.contracts.evidence import EvidenceNeed
        from tests.kernel.helpers import make_scope
        need = EvidenceNeed(id="need.tests",category="task_context",priority="required",
                            question="Which tests cover this component through its acceptance criteria?")
        request = ResearchRequestPayload(question=need.question,evidence_needs=[need],
                                        evidence_needs_only=True)
        task = TaskInput(goal=need.question,caller=Actor(id="tester",kind=ActorKind.HOST),
            scope=make_scope(self.repo),permissions=["read_repo","write_query_catalog"],
            input_payload_schema=schema_ids.RESEARCH_REQUEST,
            input_payload=request.model_dump(mode="json"),requested_output_schema=schema_ids.EVIDENCE_BUNDLE)
        pending = await self.service().start_run(task)
        assert pending.status == RunStatus.WAITING_HUMAN, pending.model_dump_json()
        coding = await self.service().resume_run(pending.run_id,
            answer_human(pending,{"free_text":"knowledge_management"}))
        assert coding.status == RunStatus.WAITING_HOST
        assert coding.run_id == pending.run_id
        assert coding.pending_interaction.operation == "build_query"
        values = await self.checkpoint_values(coding.run_id)
        assert values["task"].original_goal == need.question
        assert len(values["gaps"]) == 1
        assert any(g.gap_type.value == "unsupported" for g in values["gaps"].values())


    async def _build_and_resume(self, grant=True):
        """Real admission/catalog/checkpoints; only Cypher execution and Jev/host are doubles."""
        # covers: KM-500b-3
        # covers: KM-500c-1
        # covers: KM-500c-2
        # angle: criterion
        # angle: reachability
        from knowledge.query_catalog import QueryCatalog
        from knowledge.query_admission import QueryAdmission
        from knowledge.service import KnowledgeService
        from tests.knowledge.test_query_admission import Database, candidate
        from kernel.contracts import TaskInput, Actor, ActorKind, RunStatus, schema_ids
        from kernel.contracts.payloads import ResearchRequestPayload
        from kernel.contracts.evidence import EvidenceNeed
        from tests.kernel.helpers import make_scope
        from tests.kernel.interaction.support import raw_submission
        self.catalog = QueryCatalog(self.run_root / "query-catalog")
        self.db = Database()
        self.admission = QueryAdmission(self.catalog,self.db,"repo")
        self.config=self.config.model_copy(update={"knowledge":self.config.knowledge.model_copy(
            update={"repository_id":"repo","query_catalog_root":str(self.catalog.root)})})
        class Source:
            async def read(self,reference,max_bytes):
                return "Test verifies the selected component acceptance criterion."
        self.port=KnowledgeService(self.db,source_resolver=Source(),query_catalog=self.catalog)
        need=EvidenceNeed(id="need.tests",category="task_context",priority="required",
                          question="Which tests cover the component through acceptance criteria?")
        request=ResearchRequestPayload(question=need.question,evidence_needs=[need],evidence_needs_only=True)
        task=TaskInput(goal=need.question,caller=Actor(id="tester",kind=ActorKind.HOST),
            scope=make_scope(self.repo),permissions=["read_repo", "write_query_catalog"] if grant else ["read_repo"],
            input_payload_schema=schema_ids.RESEARCH_REQUEST,input_payload=request.model_dump(mode="json"),
            requested_output_schema=schema_ids.EVIDENCE_BUNDLE)
        human=await self.service().start_run(task)
        coding=await self.service().resume_run(human.run_id,answer_human(human,{"free_text":"component"}))
        assert coding.status==RunStatus.WAITING_HOST
        submission=raw_submission(coding.pending_interaction.model_dump(mode="json"),coding.run_id,
                                  response={"candidate":candidate()})
        result=await self.service().resume_run(coding.run_id,submission)
        assert result.status in {RunStatus.COMPLETED,RunStatus.PARTIAL},result.model_dump_json()
        if not grant:
            assert result.run_id==human.run_id and result.pending_interaction is None
            assert all(d["operation"]!="get_component_tests" for d in self.catalog.descriptors())
            values=await self.checkpoint_values(result.run_id)
            assert "knowledge.activate_query" not in self.capabilities_used(values)
            assert any(e.reason_code=="permission_denied" for r in values["routing"].values()
                       for e in r.excluded)
            assert sum(e.kind=="gap.fallback_started" for e in values["events"])==1
            return
        assert result.run_id==human.run_id and result.evidence_ids
        values=await self.checkpoint_values(result.run_id)
        assert values["task"].original_goal==need.question
        assert any(e.source.source_version and e.source.source_version.commit=="a"*40
                   for e in values["evidence"].values()), str([(r.status,r.error,r.limitations) for r in values["results"].values()])
        assert "knowledge.activate_query" in self.capabilities_used(values)
        self.catalog=QueryCatalog(self.catalog.root)
        self.admission=QueryAdmission(self.catalog,self.db,"repo")
        self.port=KnowledgeService(self.db,source_resolver=Source(),query_catalog=self.catalog)
        self.query_choice="get_component_tests"
        fresh=await self.service().start_run(task.model_copy(update={"scope":make_scope(self.repo,component_ids=["component"])}))
        assert fresh.status in {RunStatus.COMPLETED,RunStatus.PARTIAL},fresh.model_dump_json()
        assert fresh.evidence_ids and fresh.run_id!=result.run_id
        fresh_values=await self.checkpoint_values(fresh.run_id)
        assert "host.query_build" not in self.capabilities_used(fresh_values)


    async def test_verified_build_resumes_same_research_and_fresh_run_reuses_catalog(self):
        """Real service and verifier retain provenance across construction and fresh reuse."""
        # covers: KM-500b-3
        # covers: KM-500c-1
        # covers: KM-500c-2
        # angle: criterion
        # angle: reachability
        await self._build_and_resume()

    async def test_denied_activation_never_falls_back_or_changes_the_catalog(self):
        """A read-only task can receive a candidate but cannot activate it through any host."""
        # covers: KM-500b-3
        # covers: KM-500c-3
        # angle: criterion
        await self._build_and_resume(grant=False)
