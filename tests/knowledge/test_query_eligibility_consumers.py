"""Real catalog and research consumers guard fit/provenance and uncertainty compatibility."""

import pytest

from kernel.bootstrap import build_bindings, load_snapshot
from kernel.capabilities.research import ResearchExecutor
from kernel.config import repo_root
from kernel.contracts import RunStatus, schema_ids
from kernel.contracts.enums import RequestKind
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import ResearchRequestPayload
from kernel.providers.fakes import choice_answer
from tests.conftest import load_fixture
from tests.knowledge.public_retrieval_needs_support import controlled_needs, host_submission, packet_request
from tests.knowledge.query_eligibility_support import (
    CASES, admit_exact_query, choices, observe_requests, operation_batches,
    pinned_snapshot, public_harness, run, run_case,
)
from tests.kernel.capabilities.support import child, invocation, resume, script_research
from tests.kernel.entity_context.conftest import EntityServiceRig
from tests.kernel.entity_context.graph_selection_support import AC_ID, SelectionRig
from tests.kernel.entity_context.test_query_eligibility_selection import only_operations
from tests.kernel.retrieval.needs_public_support import resume_graph_needs


@pytest.mark.parametrize("description", load_fixture("_shared/query_eligibility/controls")["prose"])
def test_saved_recipe_population_outweighs_misleading_prose(monkeypatch, description):
    # covers: KM-500a-2-i
    # angle: discrimination
    harness = public_harness(monkeypatch, True)
    harness.operation = "get_ac_descendants"
    try:
        receipt, calls = run(admit_exact_query(harness, description))
        before = (harness.catalog.root / "catalog.json").read_bytes()
        final, values = run(run_case(harness, CASES[1]))
        assert len(operation_batches(harness)) == 1
        offered = choices(operation_batches(harness)[0])
        assert "get_ac_descendants" in offered
        assert receipt["operation"] not in offered, "Zero-hop exact records cannot enumerate descendants"
        assert calls == [], "A filtered recipe must not reach compiled storage"
        assert (harness.catalog.root / "catalog.json").read_bytes() == before
        assert "host.query_build" not in harness.capabilities_used(values)
        assert final.status is not RunStatus.WAITING_HUMAN
    finally:
        harness.doCleanups()


def test_explicit_operation_and_catalog_provenance_compatible(monkeypatch):
    # covers: KM-500a-2-i
    # angle: seam
    harness = public_harness(monkeypatch, True)
    requests, _ = observe_requests(monkeypatch)
    try:
        receipt, calls = run(admit_exact_query(harness, "Read exactly the selected canonical acceptance criteria."))
        before = (harness.catalog.root / "catalog.json").read_bytes()
        harness.operation = receipt["operation"]
        requests.clear()
        final, _ = run(run_case(harness, CASES[8]))
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        assert len(operation_batches(harness)) == 1
        first = requests[0]
        assert first.operation == receipt["operation"]
        assert first.operation_version == "1" and first.operation_digest == receipt["digest"]
        assert first.arguments == {"ac_ids": ["KM-500c-2"]}
        assert first.answer_requirements.model_dump(mode="json") == CASES[8]["expected_requirements"]
        assert all(request.revision == pinned_snapshot().source_sha for request in requests)
        assert calls and all(not call[2] for call in calls)
        assert (harness.catalog.root / "catalog.json").read_bytes() == before
    finally:
        harness.doCleanups()


@pytest.mark.parametrize("outcome", ["uncertain", "unsupported", "unsupported_population"])
@pytest.mark.parametrize("graph_first", [False, True])
def test_uncertain_and_unsupported_results_do_not_veto_sibling_resume(tmp_path, outcome, graph_first):
    # covers: KM-500a-2-i
    # angle: seam
    selection = SelectionRig(tmp_path)
    goal = "Explain " + AC_ID
    selection.choice = "get_entities" if outcome == "uncertain" else outcome
    selection.probability = .79 if outcome == "uncertain" else .99
    ctx = selection.context(goal)
    script_research(selection.jev, {"evaluable": .99, "answer": .99})
    need = EvidenceNeed(id="need.record", category="task_context", question=goal, priority="required")
    body = ResearchRequestPayload(question=goal, evidence_needs=[need], evidence_needs_only=True)
    parent = invocation("research", schema_ids.RESEARCH_REQUEST, body.model_dump(mode="json"))
    research = ResearchExecutor()
    planned = run(research.ainvoke(parent, ctx))
    assert len(planned.requests) == 2
    binding = build_bindings(load_snapshot(ctx.config, repo_root()), knowledge_retriever=selection.port)
    outputs = []
    graph_result = None
    for request in planned.requests:
        current = invocation("retrieve.repository", request.payload_schema, request.payload)
        result = run(binding.resolve("retrieve.repository", "1.0.0").ainvoke(current, ctx))
        is_graph = "knowledge.graph" in request.payload["source_ids"]
        if is_graph:
            graph_result = result
            assert result.evidence == []
            if outcome == "unsupported_population":
                assert result.output_payload["assessments"][need.id]["kind"] == "unsupported_population"
            else:
                assert result.output_payload["assessments"] == {}
        else:
            assert result.evidence
            assert result.output_payload["coverage"][need.id] == "satisfied"
        outputs.append((is_graph, child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                                      result.output_payload, status=result.status)))
    ordered = [output for _, output in sorted(outputs, key=lambda pair: pair[0], reverse=graph_first)]
    collected = run(research.ainvoke(resume(parent, planned, ordered), ctx))
    if collected.status.value == "waiting":
        synthesis = child(ctx, RequestKind.SYNTHESIS, schema_ids.FINDINGS,
                          {"findings": [], "unknowns": [], "disagreements": []})
        collected = run(research.ainvoke(resume(parent, collected, [*ordered, synthesis]), ctx))
    assert collected.evidence
    assert collected.output_payload["coverage"][need.id] == (
        "partial" if outcome == "unsupported_population" else "satisfied")
    assert collected.status.value == ("partial" if outcome == "unsupported_population" else "completed")
    assert selection.port.calls == []
    if outcome == "uncertain":
        assert graph_result.diagnostics["knowledge_selection"] == "uncertain"
        assert graph_result.diagnostics["knowledge_status"] == "selection_uncertain"


@pytest.mark.parametrize("outcome", ["uncertain", "empty"])
def test_useful_sibling_evidence_survives_actual_public_resume(monkeypatch, outcome):
    # covers: KM-500a-2-i
    # angle: reachability
    rig = EntityServiceRig()
    rig.setUp()
    try:
        prepared = SelectionRig(rig.repo)
        rig.config = prepared.config
        rig.intents = [("evidence", .99, .99)]
        rig.needs = {"task_context": .99}
        rig.jev.script("knowledge.operation_select", "operation",
                       choice_answer("get_entities" if outcome == "uncertain" else "unsupported", .79 if outcome == "uncertain" else .99, .64))
        if outcome == "empty":
            only_operations(monkeypatch, {"get_related_tests"})
        service = rig.service

        def registered_service():
            client = service()
            rig.env.bindings = build_bindings(rig.snapshot, knowledge_retriever=prepared.port)
            return client

        monkeypatch.setattr(rig, "service", registered_service)
        task = rig.goal_task("Explain " + AC_ID)
        task = task.model_copy(update={"scope": task.scope.model_copy(update={
            "revision": prepared.context().scope.revision})})
        pending = run(rig.service().start_run(task))
        final = run(resume_graph_needs(rig.service, pending, target=AC_ID,
                    entity_type="ac", document_type="ac_yaml"))
        values = rig.values(final.run_id)
        graph = [result for result in values["results"].values() if "knowledge_selection" in result.diagnostics]
        assert len(graph) == 1
        assert graph[0].output_payload["assessments"] == {}
        assert prepared.port.calls == []
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        assert final.output.payload["evidence"], "Useful native sibling evidence must actually survive"
        assert all(value == "satisfied" for value in final.output.payload["coverage"].values())
        batches = [batch for batch in rig.jev.batches if batch.purpose == "knowledge.operation_select"]
        assert len(batches) == (1 if outcome == "uncertain" else 0)
        if outcome == "uncertain":
            assert graph[0].diagnostics["knowledge_status"] == "selection_uncertain"
        assert len([name for name in rig.capabilities_used(values) if name == "host.retrieval_needs"]) == 1
        assert "host.query_build" not in rig.capabilities_used(values)
    finally:
        rig.doCleanups()


def test_missing_user_meaning_still_requests_focused_clarification(monkeypatch):
    # covers: KM-500a-2-i
    # covers: KM-500a-1
    # angle: failure
    harness = public_harness(monkeypatch, True)
    try:
        async def check():
            question = "Count acceptance criteria excluding parents."
            pending = await harness.service().start_run(harness.question(question))
            response = controlled_needs(packet_request(pending), None, (), status="needs_resolution",
                completeness="exhaustive_count", hierarchy_scope="exclude_parents",
                scope_resolution="user_choice_missing",
                unresolved=["Specify the canonical root, levels and whether to retain intermediate parents."])
            return await harness.service().resume_run(pending.run_id, host_submission(pending, response))
        final = run(check())
        assert final.status is RunStatus.WAITING_HUMAN
        assert harness.storage.calls == [] and operation_batches(harness) == []
        assert "root" in final.pending_interaction.question.lower()
    finally:
        harness.doCleanups()
