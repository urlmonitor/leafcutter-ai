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
from tests.kernel.integration.scenario_support import ScenarioCase
from tests.knowledge.query_answer_contract_host_support import (
    accepted_needs, configure_count_task, interpret_count, resume_count_in_child,
)


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
        # Natural-language retrieval asks Jev to pick the graph read (DK-300d-4); answer it here,
        # not in the shared ScenarioCase, so selector regressions stay visible elsewhere.
        self.operation = "get_component_context"
        self.jev.script("knowledge.operation_select", "operation", lambda q, b: choice_answer(self.operation))
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


    def natural_task(self, *, inclusion="clarify", fields=True, legacy=False):
        """Keep question-only intake distinct from explicit legacy builder obligations."""
        return configure_count_task(self, inclusion=inclusion, fields=fields, legacy=legacy)

    def test_natural_question_produces_work_status_need_and_focused_clarification(self):
        # covers: KM-500e-1
        # angle: criterion
        # angle: reachability
        self._asyncioRunner.run(self._scenario_natural_question_produces_work_status_need_and_focused_clarification(), context=contextvars.copy_context())

    async def _scenario_natural_question_produces_work_status_need_and_focused_clarification(self):
        """No caller-built contract: actual planner must preserve field meaning and ambiguity."""
        task = self.natural_task()
        pending, request = await interpret_count(self, task)
        assert pending.status == RunStatus.WAITING_HUMAN, pending.model_dump_json()
        assert self.calls == []
        values = await self.checkpoint_values(pending.run_id)
        needs = accepted_needs(values)[-1]
        assert needs["selections"]["required_fields"] == ["work_status"]
        assert needs["hierarchy_scope"] == "unknown"
        assert needs["hierarchy_levels"] == []
        assert needs["original_question"] == task.goal
        assert needs["source_scope"] == request["source_scope"]
        assert pending.usage_summary.host_operations == 1
        assert "host.query_build" not in self.capabilities_used(values)
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
        result, request = await interpret_count(self, task, inclusion="root_excluded")
        assert result.status != RunStatus.WAITING_HUMAN, result.model_dump_json()
        batches = [batch.model_dump(mode="json") for batch in self.jev.batches
                   if batch.purpose == "knowledge.operation_select"]
        assert batches, result.model_dump_json()
        contract = batches[-1]["state"]["answer_requirements"]
        assert contract["scope"]["inclusion"] == "root_excluded"
        assert contract["scope"]["levels"] == ["L2", "L3"]
        assert contract["required_fields"] == ["work_status"]
        assert self.calls and self.calls[0].operation == "get_ac_descendants"
        values = await self.checkpoint_values(result.run_id)
        requests = [r for r in values["requests"].values() if r.payload_schema == schema_ids.RETRIEVAL_REQUEST]
        assert requests and all(r.payload["answer_requirements"] == contract for r in requests)
        assert all(r.payload["retrieval_needs"]["source_scope"] == request["source_scope"] for r in requests)
        assert result.pending_interaction.operation == "synthesize_evidence"
        assert len(accepted_needs(values)) == 1
        assert result.usage_summary.host_operations == 2  # interpretation plus the pending synthesis

    def test_no_confident_required_facts_asks_about_facts_before_selection(self):
        # covers: KM-500e-1
        # angle: boundary
        self._asyncioRunner.run(self._scenario_no_confident_required_facts_asks_about_facts_before_selection(), context=contextvars.copy_context())

    async def _scenario_no_confident_required_facts_asks_about_facts_before_selection(self):
        """A planner that cannot identify requested facts cannot continue with empty obligations."""
        task = self.natural_task(inclusion="root_excluded", fields=False)
        result, _ = await interpret_count(self, task, inclusion="root_excluded", fields=False)
        assert result.status == RunStatus.WAITING_HUMAN, result.model_dump_json()
        assert self.calls == []
        assert not any(batch.purpose in {"knowledge.operation_select", "knowledge.query_select"} for batch in self.jev.batches)
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
        """Legacy explicit obligations: a build choice cannot invent an absent field mapping."""
        self.mapping_gap = True
        task = self.natural_task(inclusion="root_excluded", legacy=True)
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
        """Legacy explicit obligations retain their existing mapped-field builder eligibility."""
        task = self.natural_task(inclusion="root_excluded", legacy=True)
        result = await self.service().start_run(task)
        assert result.status == RunStatus.WAITING_HOST, result.model_dump_json()
        assert result.pending_interaction.operation == "build_query"

    def test_natural_ac_query_gap_does_not_borrow_legacy_builder_authority(self):
        # covers: KM-500e-1-i
        # covers: KM-500e-4
        # angle: failure
        # angle: discrimination
        self._asyncioRunner.run(self._scenario_natural_ac_query_gap(), context=contextvars.copy_context())

    async def _scenario_natural_ac_query_gap(self):
        """An AC interpretation cannot acquire component-only query creation authority."""
        task = self.natural_task(inclusion="root_excluded")
        self.operation = "unsupported"
        result, _ = await interpret_count(self, task, inclusion="root_excluded")
        assert result.status == RunStatus.PARTIAL, result.model_dump_json()
        choices = [b.questions[0].criteria for b in self.jev.batches if b.purpose == "knowledge.operation_select"]
        assert choices and all("query_catalog" not in choice for choice in choices)
        values = await self.checkpoint_values(result.run_id)
        assert "host.query_build" not in self.capabilities_used(values)
        assert not self.calls and not result.evidence_ids

    def test_actual_child_process_reopens_and_resumes_original_count_scope(self):
        # covers: KM-500e-1
        # angle: real_artifact
        # angle: seam
        # angle: reachability
        self._asyncioRunner.run(self._scenario_actual_child_process_reopens_and_resumes_original_count_scope(), context=contextvars.copy_context())

    async def _scenario_actual_child_process_reopens_and_resumes_original_count_scope(self):
        """A real process retains the question, trust scope, clarification and cumulative usage."""
        import asyncio
        from pathlib import Path
        import subprocess
        import sys
        task = self.natural_task()
        pending, request = await interpret_count(self, task)
        assert pending.status == RunStatus.WAITING_HUMAN
        packet = self.run_root / "qa-independent-restart-input.json"
        packet.write_text(json.dumps({"repo": str(self.repo), "run_root": str(self.run_root),
            "config": self.config.model_dump(mode="json"), "pending": pending.model_dump(mode="json"),
            "question": task.goal, "source_scope": request["source_scope"]}), encoding="utf-8")
        process = await asyncio.to_thread(subprocess.run, [sys.executable, "-m", __name__, str(packet)],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert process.returncode == 0, process.stdout + process.stderr
        report = json.loads(process.stdout)
        assert report["run_id"] == pending.run_id
        assert report["original_question"] == task.goal
        assert report["required_fields"] == ["work_status"]
        assert report["scope"]["inclusion"] == "root_excluded"
        assert report["scope"]["levels"] == ["L2", "L3"]
        assert report["source_scope"] == request["source_scope"]
        assert report["host_operations"] == 3  # two interpretations plus pending synthesis
        assert report["host_input_tokens"] == 22 and report["host_output_tokens"] == 14
        assert report["jev_calls"] >= pending.usage_summary.jev_calls
        assert report["interpretation_count"] == 2
        assert report["operation"] == "get_ac_descendants"
        assert report["status"] == "waiting_host" and report["pending_operation"] == "synthesize_evidence"
        assert report["pid"] != __import__("os").getpid()


if __name__ == "__main__":
    import sys
    resume_count_in_child(TestPublicKernelAnswerContract, sys.argv[1])


# DECISION HISTORY
# ================================================================================
# - 2026-10-06 12:00 [test-writer]: Script the operation_select question in this fixture (not the shared ScenarioCase); #1008 routes natural-language retrieval through it. (#KnowledgeFixturesOpSelect)
# - 2026-10-09 [test-writer]: Drive the real needs host and restart protocol; isolate legacy builder compatibility. (#KM-500e-1-i)
