"""Independent real-kernel acceptance for persisted answer obligations.

MODULE: test_query_answer_contract_acceptance_kernel
GOAL: Detect question loss between research, retrieval and persisted results.
BUSINESS CONTEXT: A scripted sufficiency judgment cannot erase missing required facts.
ARCHITECTURE: Real public KernelService; controlled neutral port, Jev and trace sink.
"""
import json
import contextvars
from types import SimpleNamespace

from kernel.bootstrap import build_bindings
from kernel.config import SourceConfig
from kernel.contracts import Actor, ActorKind, RunStatus, TaskInput, schema_ids
from kernel.providers.fakes import choice_answer
from knowledge.config import KnowledgeConfig
from knowledge.contracts import KnowledgeRetrievalResult
from tests.kernel.helpers import make_scope
from tests.kernel.integration.scenario_support import ScenarioCase, answer_human


class TestPublicKernelAnswerContract(ScenarioCase):
    """Drive the real scheduler and reopen persisted state; no live provider claims."""

    domains = ("primary",)

    def setUp(self):
        """Use one actual configured graph source and an intentionally incomplete port."""
        super().setUp()
        self.config = self.config.model_copy(update={
            "knowledge": KnowledgeConfig(backend="neo4j", repository_id="fixture", repository_root=str(self.repo)),
            "sources": [SourceConfig(id="knowledge.graph", kind="graph_query", categories=["task_context"])],
        })
        self.route_choice = "research"
        self.calls = []
        self.catalog = None
        self.admission = None
        self.requirements = {
            "original_question": "What is the work status of TQ-500f-2?",
            "required_fields": ["work_status"],
            "scope": {"population": "returned_entities"},
            "require_complete": True,
        }

    def service(self):
        """Install only the external neutral port double through real composition."""
        service = super().service()
        owner = self

        class IncompletePort:
            async def capabilities(self):
                """Advertise graph mechanism, not fulfillment."""
                return {"graph": True}

            async def retrieve(self, request):
                """Emit controlled missing-field evidence; expected totals are never injected."""
                owner.calls.append(request)
                actual = request.model_dump(mode="json").get("answer_requirements")
                payload = {
                    "request_id": request.request_id, "retrieval_id": "controlled-missing-field",
                    "status": "ok", "requested_mode": request.mode, "executed_mode": request.mode,
                    "source_sha": "a" * 40, "generation_id": "controlled-generation",
                    "evidence": [{"entity": {"canonical_id": "ADR-900", "kind": "ADR", "title": "Controlled source",
                        "source": {"repository_id": getattr(owner, "response_repository", "fixture"), "source_sha": "a" * 40,
                                   "path": "docs/architecture/adrs/ADR-900-capability-shape.md"}},
                        "content": "This controlled evidence does not provide work_status.",
                        "disclosure_level": request.disclosure_level}],
                }
                if actual is not None:
                    payload["answer"] = {
                        "status": "unresolved", "original_question": actual["original_question"],
                        "required_fields": actual["required_fields"], "scope": actual["scope"],
                        "missing_fields": [{"canonical_id": "ADR-900", "field": "work_status", "reason": "unknown"}],
                        "completeness": {"complete": False, "known_count": 1, "exact_total": None,
                                         "limitations": ["Required work_status is missing."]},
                        "work_status_counts": None, "limitations": ["Required work_status is missing."],
                    }
                if getattr(owner, "response_observation", None) is not None:
                    payload["observation"] = owner.response_observation
                return KnowledgeRetrievalResult.model_validate(payload)

        self.env.bindings = build_bindings(self.snapshot, knowledge_retriever=IncompletePort(),
            query_catalog=self.catalog, query_admission=self.admission)
        return service

    def research_task(self, *, component_ids=None):
        """Pass raw client JSON through service intake and actual payload validation."""
        need = {"id": "need.status", "category": "task_context", "priority": "required",
                "question": self.requirements["original_question"]}
        payload = {"question": need["question"], "evidence_needs": [need], "evidence_needs_only": True,
                   "answer_requirements": self.requirements}
        return TaskInput(goal=need["question"], caller=Actor(id="qa", kind=ActorKind.HOST),
            scope=make_scope(self.repo, component_ids=component_ids or ["decision_kernel"]),
            permissions=["read_repo"], input_payload_schema=schema_ids.RESEARCH_REQUEST,
            input_payload=payload, requested_output_schema=schema_ids.EVIDENCE_BUNDLE)

    def test_research_obligations_reach_actual_retrieval_and_persist(self):
        # covers: KM-500e-1
        # angle: seam
        # angle: criterion
        # angle: reachability
        self._asyncioRunner.run(self._scenario_research_obligations_reach_actual_retrieval_and_persist(), context=contextvars.copy_context())

    async def _scenario_research_obligations_reach_actual_retrieval_and_persist(self):
        """Research-to-retrieval transport preserves the original question and required fields."""
        result = await self.service().start_run(self.research_task())
        assert self.calls, result.model_dump_json()
        observed = self.calls[-1].model_dump(mode="json").get("answer_requirements")
        assert observed is not None
        assert observed["original_question"] == self.requirements["original_question"]
        assert observed["required_fields"] == ["work_status"]
        values = await self.checkpoint_values(result.run_id)
        retrieval_requests = [request for request in values["requests"].values()
                              if request.payload_schema == schema_ids.RETRIEVAL_REQUEST]
        assert retrieval_requests
        assert all(request.payload["answer_requirements"]["required_fields"] == ["work_status"]
                   for request in retrieval_requests)

    def test_scripted_sufficient_judgment_cannot_upgrade_unresolved_answer(self):
        # covers: KM-500e-1
        # covers: KM-500f-2
        # angle: discrimination
        self._asyncioRunner.run(self._scenario_scripted_sufficient_judgment_cannot_upgrade_unresolved_answer(), context=contextvars.copy_context())

    async def _scenario_scripted_sufficient_judgment_cannot_upgrade_unresolved_answer(self):
        """High scripted sufficiency confidence remains subordinate to missing required facts."""
        self.params["answer"] = 1.0
        result = await self.service().start_run(self.research_task())
        from tests.knowledge.query_answer_contract_acceptance_research_support import complete_requested_synthesis
        result = await complete_requested_synthesis(self, result)
        assert self.calls, result.model_dump_json()
        assert result.status == RunStatus.PARTIAL, result.model_dump_json()
        values = await self.checkpoint_values(result.run_id)
        diagnostics = [item.diagnostics for item in values["results"].values()
                       if "knowledge_answer" in item.diagnostics]
        assert diagnostics, "The public capability result lost neutral question fulfillment."
        answers = [json.loads(item["knowledge_answer"]) for item in diagnostics]
        assert all(answer["status"] == "unresolved" for answer in answers)
        assert all(answer["work_status_counts"] is None for answer in answers)

    def test_ambiguous_parent_exclusion_pauses_before_count_and_survives_restart(self):
        # covers: KM-500e-1
        # angle: reachability
        self._asyncioRunner.run(self._scenario_ambiguous_parent_exclusion_pauses_before_count_and_survives_restart(), context=contextvars.copy_context())

    async def _scenario_ambiguous_parent_exclusion_pauses_before_count_and_survives_restart(self):
        """An omitted root-versus-leaf choice must pause before execution or construction."""
        self.requirements = {**self.requirements,
            "original_question": "How many test-writing ACs are there, excluding parent requirements?",
            "scope": {"population": "ac_descendants", "root_id": "TQ-500f", "levels": ["L2", "L3"]}}
        self.catalog = SimpleNamespace(descriptors=lambda: [])
        async def pin(repository_id, source_sha="latest"):
            return {"repository_id": repository_id, "source_sha": "a" * 40,
                    "generation_id": "controlled-generation", "supported_kinds": ["AcceptanceCriterion"],
                    "supported_fields": {"AcceptanceCriterion": ["canonical_id", "level"] + ([] if getattr(self, "mapping_gap", False) else ["work_status"])},
                    "supported_relationships": ["parent", "depends_on"]}
        self.admission = SimpleNamespace(pin=pin)
        self.jev.script("knowledge.query_readiness", "readiness", choice_answer("ready"))
        self.jev.script("knowledge.query_target", "kind", choice_answer("AcceptanceCriterion"))
        self.jev.script("knowledge.query_select", "query", choice_answer("build"))
        pending = await self.service().start_run(self.research_task())
        assert pending.status == RunStatus.WAITING_HUMAN, pending.model_dump_json()
        assert self.calls == []
        values = await self.checkpoint_values(pending.run_id)
        continuations = [item.continuation.state for item in values["work_items"].values()
                         if item.continuation and "answer_requirements" in item.continuation.state]
        assert continuations, "The count obligations disappeared at the human checkpoint."
        assert any(value["answer_requirements"]["scope"].get("inclusion") is None for value in continuations)
        assert "host.query_build" not in self.capabilities_used(values)


    def natural_task(self, *, inclusion="clarify", fields=True):
        """Script only external interpretation; actual producer builds all answer requirements."""
        from kernel.providers.fakes import noul_answer
        self.requirements["original_question"] = (
            "How many TQ-500f test-writing ACs are there and what work statuses do they have, excluding parent requirements?"
            if inclusion == "clarify" else
            "Count every L2 and L3 descendant of TQ-500f, exclude only TQ-500f itself, and show work statuses.")
        self.catalog = SimpleNamespace(descriptors=lambda: [])
        async def pin(repository_id, source_sha="latest"):
            return {"repository_id": repository_id, "source_sha": "a" * 40,
                    "generation_id": "controlled-generation", "supported_kinds": ["AcceptanceCriterion"],
                    "supported_fields": {"AcceptanceCriterion": ["canonical_id", "level"] + ([] if getattr(self, "mapping_gap", False) else ["work_status"])},
                    "supported_relationships": ["parent", "depends_on"]}
        self.admission = SimpleNamespace(pin=pin)
        self.jev.script("knowledge.answer_contract", "field.*", lambda q, b:
            noul_answer(0.99 if fields and q.id == "field.work_status" else 0.01))
        self.jev.script("knowledge.answer_contract", "population", choice_answer("ac_descendants"))
        self.jev.script("knowledge.answer_contract", "inclusion", choice_answer(inclusion))
        self.jev.script("knowledge.answer_contract", "root", choice_answer("TQ-500f"))
        self.jev.script("knowledge.answer_contract", "level.*", lambda q, b:
            noul_answer(0.99 if q.id in {"level.L2", "level.L3"} else 0.01))
        self.jev.script("knowledge.query_readiness", "readiness", choice_answer("ready"))
        self.jev.script("knowledge.query_target", "kind", choice_answer("AcceptanceCriterion"))
        self.jev.script("knowledge.query_select", "query", choice_answer("build"))
        raw = self.research_task().model_dump(mode="json")
        raw["input_payload"].pop("answer_requirements")
        return TaskInput.model_validate(raw)

    def test_natural_question_produces_work_status_need_and_focused_clarification(self):
        # covers: KM-500e-1
        # angle: criterion
        # angle: reachability
        self._asyncioRunner.run(self._scenario_natural_question_produces_work_status_need_and_focused_clarification(), context=contextvars.copy_context())

    async def _scenario_natural_question_produces_work_status_need_and_focused_clarification(self):
        """No caller-built contract: actual planner must preserve field meaning and ambiguity."""
        task = self.natural_task()
        pending = await self.service().start_run(task)
        assert pending.status == RunStatus.WAITING_HUMAN, pending.model_dump_json()
        assert self.calls == []
        values = await self.checkpoint_values(pending.run_id)
        states = [item.continuation.state for item in values["work_items"].values()
                  if item.continuation and item.continuation.state.get("answer_requirements")]
        assert states
        assert states[-1]["answer_requirements"]["required_fields"] == ["work_status"]
        assert states[-1]["answer_requirements"]["scope"]["inclusion"] is None
        assert states[-1]["answer_requirements"]["original_question"] == task.goal
        question = pending.pending_interaction.model_dump_json()
        assert "root_excluded" in question and "terminal_leaves" in question

    def test_fully_explicit_natural_scope_reaches_selection_without_repeat_question(self):
        # covers: KM-500e-1
        # angle: discrimination
        # angle: criterion
        # angle: reachability
        self._asyncioRunner.run(self._scenario_fully_explicit_natural_scope_reaches_selection_without_repeat_question(), context=contextvars.copy_context())

    async def _scenario_fully_explicit_natural_scope_reaches_selection_without_repeat_question(self):
        """The same public producer must honor an already explicit root and level policy."""
        task = self.natural_task(inclusion="root_excluded")
        result = await self.service().start_run(task)
        assert result.status != RunStatus.WAITING_HUMAN, result.model_dump_json()
        batches = [batch.model_dump(mode="json") for batch in self.jev.batches
                   if batch.purpose == "knowledge.query_select"]
        assert batches, result.model_dump_json()
        contract = batches[-1]["state"]["answer_requirements"]
        assert contract["scope"]["inclusion"] == "root_excluded"
        assert contract["scope"]["levels"] == ["L2", "L3"]
        assert contract["required_fields"] == ["work_status"]

    def test_no_confident_required_facts_asks_about_facts_before_selection(self):
        # covers: KM-500e-1
        # angle: boundary
        self._asyncioRunner.run(self._scenario_no_confident_required_facts_asks_about_facts_before_selection(), context=contextvars.copy_context())

    async def _scenario_no_confident_required_facts_asks_about_facts_before_selection(self):
        """A planner that cannot identify requested facts cannot continue with empty obligations."""
        task = self.natural_task(inclusion="root_excluded", fields=False)
        result = await self.service().start_run(task)
        assert result.status == RunStatus.WAITING_HUMAN, result.model_dump_json()
        assert not any(batch.purpose == "knowledge.query_select" for batch in self.jev.batches)
        question = result.pending_interaction.model_dump_json().lower()
        assert "field" in question or "fact" in question, question



    def test_foreign_evidence_diagnosis_compares_actual_scope_and_withholds_evidence(self):
        # covers: KM-500g-2
        # angle: failure
        # angle: criterion
        # angle: reachability
        # angle: seam
        self._asyncioRunner.run(self._scenario_foreign_evidence_diagnosis_compares_actual_scope_and_withholds_evidence(), context=contextvars.copy_context())

    async def _scenario_foreign_evidence_diagnosis_compares_actual_scope_and_withholds_evidence(self):
        """Actual kernel scope rejection must identify expected and observed repository facts."""
        self.response_repository = "controlled-foreign-repository"
        result = await self.service().start_run(self.research_task())
        assert self.calls, result.model_dump_json()
        assert result.status != RunStatus.COMPLETED
        values = await self.checkpoint_values(result.run_id)
        rows = [json.loads(item.diagnostics["knowledge_diagnosis"]) for item in values["results"].values()
                if "knowledge_diagnosis" in item.diagnostics]
        assert rows, "Public scope failure omitted structured diagnosis."
        diagnostic = rows[-1]
        assert diagnostic["expected"]["repository_id"] == "fixture"
        assert diagnostic["observed"]["repository_id"] == "controlled-foreign-repository"
        assert diagnostic["cause"]["status"] == "established"
        assert diagnostic["contract"] and diagnostic["next_step"]["reason"]
        assert not result.evidence_ids

    def test_missing_fact_diagnosis_does_not_invent_remote_trace_or_root_cause(self):
        # covers: KM-500g-2
        # angle: discrimination
        # angle: criterion
        # angle: reachability
        # angle: seam
        self._asyncioRunner.run(self._scenario_missing_fact_diagnosis_does_not_invent_remote_trace_or_root_cause(), context=contextvars.copy_context())

    async def _scenario_missing_fact_diagnosis_does_not_invent_remote_trace_or_root_cause(self):
        """An unverified URL and absent field remain observations, not remote visibility or cause."""
        self.response_observation = {"state": "unverified", "trace_id": "controlled-trace",
                                     "trace_url": "https://trace.example/not-verified"}
        result = await self.service().start_run(self.research_task())
        values = await self.checkpoint_values(result.run_id)
        rows = [json.loads(item.diagnostics["knowledge_diagnosis"]) for item in values["results"].values()
                if "knowledge_diagnosis" in item.diagnostics]
        assert rows, "Public answer failure omitted structured diagnosis."
        diagnostic = rows[-1]
        assert diagnostic["answer_status"] != "fulfilled"
        assert diagnostic["trace"]["state"] != "verified"
        assert diagnostic["trace"].get("trace_url") is None
        assert diagnostic["cause"]["status"] == "unknown"
        assert diagnostic["next_step"]["reason"]


    def test_missing_field_mapping_never_dispatches_query_builder(self):
        # covers: KM-500e-4
        # angle: failure
        # angle: criterion
        # angle: reachability
        # angle: seam
        self._asyncioRunner.run(self._scenario_missing_field_mapping_never_dispatches_query_builder(), context=contextvars.copy_context())

    async def _scenario_missing_field_mapping_never_dispatches_query_builder(self):
        """Even a scripted build choice cannot invent an absent required field mapping."""
        self.mapping_gap = True
        task = self.natural_task(inclusion="root_excluded")
        result = await self.service().start_run(task)
        values = await self.checkpoint_values(result.run_id)
        assert "host.query_build" not in self.capabilities_used(values)
        assert result.status != RunStatus.WAITING_HOST
        selections = [batch.model_dump(mode="json") for batch in self.jev.batches if batch.purpose == "knowledge.query_select"]
        if selections:
            assert "field_availability_gap" in json.dumps(selections[-1]), selections[-1]
            choices = selections[-1]["questions"][0]["criteria"]
            assert "build" not in choices, choices

    def test_available_fields_with_missing_query_can_dispatch_builder(self):
        # covers: KM-500e-4
        # angle: discrimination
        # angle: criterion
        # angle: reachability
        # angle: seam
        self._asyncioRunner.run(self._scenario_available_fields_with_missing_query_can_dispatch_builder(), context=contextvars.copy_context())

    async def _scenario_available_fields_with_missing_query_can_dispatch_builder(self):
        """The same missing-query path stays eligible when requested fields are mapped."""
        task = self.natural_task(inclusion="root_excluded")
        result = await self.service().start_run(task)
        assert result.status == RunStatus.WAITING_HOST, result.model_dump_json()
        assert result.pending_interaction.operation == "build_query"

    def test_actual_child_process_reopens_and_resumes_original_count_scope(self):
        # covers: KM-500e-1
        # angle: real_artifact
        # angle: seam
        # angle: reachability
        self._asyncioRunner.run(self._scenario_actual_child_process_reopens_and_resumes_original_count_scope(), context=contextvars.copy_context())

    async def _scenario_actual_child_process_reopens_and_resumes_original_count_scope(self):
        """An OS process boundary retains the original question and human scope correction."""
        import asyncio
        from pathlib import Path
        import subprocess
        import sys
        task = self.natural_task()
        pending = await self.service().start_run(task)
        assert pending.status == RunStatus.WAITING_HUMAN
        packet = self.run_root / "qa-independent-restart-input.json"
        packet.write_text(json.dumps({"repo": str(self.repo), "run_root": str(self.run_root),
            "config": self.config.model_dump(mode="json"), "pending": pending.model_dump(mode="json"),
            "question": task.goal}), encoding="utf-8")
        process = await asyncio.to_thread(subprocess.run, [sys.executable, "-m", __name__, str(packet)],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert process.returncode == 0, process.stdout + process.stderr
        report = json.loads(process.stdout)
        assert report["run_id"] == pending.run_id
        assert report["status"] == "waiting_host", report
        assert report["original_question"] == task.goal
        assert report["required_fields"] == ["work_status"]
        assert report["scope"]["inclusion"] == "root_excluded"
        assert report["pid"] != __import__("os").getpid()


def _resume_in_child(path):
    """Independent client process: reconstruct external fixtures and resume persisted service state."""
    import asyncio
    import os
    from pathlib import Path
    from kernel.config import KernelConfig
    from kernel.contracts.run import RunEnvelope
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    case = TestPublicKernelAnswerContract()
    case.setUp()
    try:
        case.repo, case.run_root = Path(raw["repo"]), Path(raw["run_root"])
        case.config = KernelConfig.model_validate(raw["config"])
        case.natural_task()
        pending = RunEnvelope.model_validate(raw["pending"])
        response = answer_human(pending, {"free_text": json.dumps({"scope": {"inclusion": "root_excluded"}})})
        result = asyncio.run(case.service().resume_run(pending.run_id, response))
        values = asyncio.run(case.checkpoint_values(result.run_id))
        states = [item.continuation.state for item in values["work_items"].values()
                  if item.continuation and item.continuation.state.get("answer_requirements")]
        requirements = states[-1]["answer_requirements"]
        print(json.dumps({"run_id": result.run_id, "status": result.status.value,
            "original_question": requirements["original_question"], "required_fields": requirements["required_fields"],
            "scope": requirements["scope"], "pid": os.getpid()}))
    finally:
        case.doCleanups()


if __name__ == "__main__":
    import sys
    _resume_in_child(sys.argv[1])
