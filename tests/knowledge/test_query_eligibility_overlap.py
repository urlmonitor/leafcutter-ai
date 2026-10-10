"""Supplemental overlap witnesses, independent of the frozen first 43 executions."""
from __future__ import annotations

import asyncio

import pytest

from integrations.research_needs import RepositoryNeedsInterpreter
from kernel.capabilities.research.state import Plan
from kernel.contracts.retrieval_needs import RetrievalNeedsOutput
from knowledge.adapters.neo4j_queries import query
from knowledge.answer_models import AnswerRequirements, AnswerScope
from knowledge.contracts import Entity, KnowledgeRetrievalRequest, ProjectionSnapshot, Relation, SourceReference
from knowledge.projection.validation import validate_snapshot
from knowledge.service import KnowledgeService
from tests.conftest import load_fixture
from tests.kernel.entity_context.graph_selection_support import SHA, SelectionRig, _choices
from tests.knowledge import public_retrieval_needs_support as public
from tests.knowledge.query_eligibility_support import (
    choices, observe_requests, operation_batches, pinned_snapshot, public_harness,
)

DATA = load_fixture("_shared/query_eligibility/overlap")


class NativeOverlap:
    """Controlled driver/source IO; production query, population, disclosure and answer code."""

    def __init__(self, root, case):
        self.root, self.case = root, case
        source = SourceReference(repository_id="fixture", source_sha=SHA, path=case["path"])
        props = {"depends_on": [case["id"]]} if case["kind"] == "AcceptanceCriterion" else {"synthetic": True}
        self.node = Entity(canonical_id=case["id"], kind=case["kind"], title="Self endpoint",
                           source=source, properties=props)
        edge = Relation(source=source, source_id=case["id"], target_id=case["id"], edge_type=case["edge"])
        self.snapshot = ProjectionSnapshot(repository_id="fixture", source_sha=SHA,
            generation_id="controlled-overlap", nodes=[self.node], edges=[edge],
            supported_kinds=[case["kind"]], supported_relationships=[case["edge"]])
        validate_snapshot(self.snapshot)
        self.driver_calls, self.calls, self.results = [], [], []
        self.service = KnowledgeService(self, source_resolver=self)

    async def capabilities(self):
        return {"graph": True, "semantic": False, "hybrid": False, "status": "ready"}

    async def active(self, repository_id):
        return self.snapshot if repository_id == "fixture" else None

    async def get_generation(self, repository_id, generation_id):
        return self.snapshot if repository_id == "fixture" and generation_id == self.snapshot.generation_id else None

    async def query(self, *args):
        return await query(self, *args)

    async def _run(self, statement, parameters=None, write=False):
        assert not write
        self.driver_calls.append((statement, parameters))
        if "edge_type" in parameters:
            assert parameters["edge_type"] == self.case["edge"]
            assert parameters["kind"] == self.node.kind
            assert "[" + "r:" + self.case["edge"].upper() + "]" in statement
        return [{"payload": self.node.model_dump_json()}] if self.node.canonical_id in parameters["ids"] else []

    async def neighbors(self, *args):
        return [], []

    async def read(self, reference, max_bytes):
        return (self.root / reference.path).read_bytes()[:max_bytes].decode("utf-8")

    async def retrieve(self, request):
        self.calls.append(request)
        result = await self.service.retrieve(request)
        self.results.append(result)
        return result


def exact_needs(case):
    goal = "Read the authored content of " + case["id"]
    needs = public.controlled_needs({"original_question": goal, "source_scope": {}}, case["id"], ["content"])
    if case["kind"] == "Decision":
        needs["selections"].update(entity_types=["decision"], document_types=["decision"])
    output = RetrievalNeedsOutput.model_validate(needs)
    plan = RepositoryNeedsInterpreter().apply(Plan(goal, "", [], []), output)
    return goal, {"retrieval_needs": output, "answer_requirements": plan.answer_requirements}


@pytest.mark.parametrize("case", DATA["native"], ids=lambda row: row["operation"])
def test_native_self_endpoint_reaches_real_answer_consumer(tmp_path, case):
    # covers: KM-500a-2-i
    # angle: seam
    SelectionRig(tmp_path)
    port = NativeOverlap(tmp_path, case)
    need = AnswerRequirements(original_question="Read exact source", required_fields=["content"],
                              scope=AnswerScope(entity_ids=[case["id"]]))
    request = KnowledgeRetrievalRequest(request_id="overlap", repository_id="fixture", revision=SHA,
        operation=case["operation"], mode="graph", arguments={"entity_ids": [case["id"]]},
        disclosure_level=3, answer_requirements=need)
    result = asyncio.run(port.retrieve(request))
    assert result.status == "ok"
    assert result.answer.status == "fulfilled"
    assert result.answer.limitations == [] and result.answer.missing_fields == []
    assert [item.entity.canonical_id for item in result.evidence] == [case["id"]]
    assert any(params.get("edge_type") == case["edge"] for _, params in port.driver_calls)
    if case["operation"] == "get_declared_dependents":
        assert result.stats["population"]["population"] == "declared_dependents"
        assert result.answer.scope.population == "returned_entities"
        assert result.evidence[0].path[0].source_id == result.evidence[0].path[0].target_id


@pytest.mark.parametrize("case", DATA["native"], ids=lambda row: row["operation"])
def test_native_self_endpoint_remains_selectable(tmp_path, case):
    # covers: KM-500a-2-i
    # angle: discrimination
    rig = SelectionRig(tmp_path)
    rig.port = NativeOverlap(tmp_path, case)
    rig.choice = case["operation"]
    goal, kwargs = exact_needs(case)
    result, _, _ = rig.run(goal, **kwargs)
    assert len(rig.operation_batches()) == 1
    offered = _choices(rig.operation_batches()[0])
    assert case["operation"] in offered, "The native result can contain the required exact identity"
    wrong_kind = "get_related_tests" if case["kind"] == "AcceptanceCriterion" else "get_related_lessons"
    assert wrong_kind not in offered
    assert result.evidence and len(rig.port.calls) == 2
    assert [(call.operation, call.disclosure_level) for call in rig.port.calls] == [
        (case["operation"], 0), ("get_entities", 3)]
    discovery, hydrated = rig.port.results
    assert discovery.answer.status == "partial"
    assert discovery.evidence[0].field_availability["content"] == "disclosure_omitted"
    assert hydrated.answer.status == "fulfilled"
    assert rig.port.calls[0].answer_requirements == rig.port.calls[1].answer_requirements
    assert rig.port.calls[-1].answer_requirements.scope.entity_ids == [case["id"]]
    assert rig.port.calls[-1].answer_requirements.required_fields == ["content"]
    assert hydrated.evidence[0].entity.canonical_id == case["id"]
    assert hydrated.evidence[0].entity.source.path == case["path"]
    assert hydrated.evidence[0].entity.source.source_sha == SHA
    assert hydrated.evidence[0].field_availability["content"] == "present"
    assert hydrated.evidence[0].field_locators["content"] == ""


@pytest.mark.parametrize("endpoint_kind", ["AcceptanceCriterion", None], ids=["typed-cycle", "unknown-endpoint"])
def test_admitted_round_trip_remains_selectable(monkeypatch, endpoint_kind):
    # covers: KM-500a-2-i
    # angle: seam
    harness = public_harness(monkeypatch, catalog=True)
    requests, results = observe_requests(monkeypatch)
    original = pinned_snapshot()
    root = next(node for node in original.nodes if node.canonical_id == "KM-500c-2")
    test_node = Entity(canonical_id="Test:overlap", kind="Test", title="Linked test", source=root.source)
    edge = Relation(source=root.source, source_id=root.canonical_id, target_id=test_node.canonical_id,
                    edge_type="covered_by")
    snapshot = original.model_copy(update={"nodes": [*original.nodes, test_node], "edges": [edge],
        "supported_kinds": [*original.supported_kinds, "Test"],
        "supported_relationships": [*original.supported_relationships, "covered_by"]})
    validate_snapshot(snapshot)
    monkeypatch.setattr(public, "source_snapshot", lambda: snapshot)
    driver_calls = []

    async def compiled_read(statement, parameters=None, write=False):
        assert not write
        driver_calls.append((statement, parameters))
        assert "(n0)-[r0:COVERED_BY]->(n1:Test" in statement
        assert "(n1)<-[r1:COVERED_BY]-(n2:" in statement
        assert parameters["step_0_edge"] == parameters["step_1_edge"] == "covered_by"
        assert parameters.get("step_1_kind") == endpoint_kind
        # One declared AC -> Test edge admits its AC endpoint after the reverse hop.
        nodes = [root] if root.canonical_id in parameters["arg_ac_ids"] else []
        return [{"payloads": [node.model_dump_json() for node in nodes], "expansion_truncated": False}]

    harness.storage._run = compiled_read
    candidate = load_fixture("_shared/query_eligibility/saved_exact")
    candidate["descriptor"].update(operation="read_round_trip", description="Read endpoints reached by the declared round trip")
    candidate["descriptor"]["recipe"]["steps"] = [
        {"edge_type": "covered_by", "direction": "outgoing", "kind": "Test"},
        {"edge_type": "covered_by", "direction": "incoming", "kind": endpoint_kind},
    ]

    async def exercise():
        receipt = await harness.admission.verify_and_activate(candidate,
            repository_id=public.REPOSITORY, source_sha=snapshot.source_sha)
        assert receipt["status"] == "activated"
        driver_calls.clear()
        harness.operation = "read_round_trip"
        final, values = await public.interpret_public_question(harness,
            "Read the criteria of KM-500c-2", fields=("criteria",))
        return final, values

    try:
        final, values = asyncio.run(exercise())
        batches = operation_batches(harness)
        assert len(batches) == 1
        assert "read_round_trip" in choices(batches[0]), "Admitted reverse traversal can return its seed"
        assert [(request.operation, request.disclosure_level) for request in requests] == [
            ("read_round_trip", 0), ("get_entities", 3)]
        assert driver_calls and len(results) == 2
        assert results[0].answer.status == "partial"
        assert results[0].evidence[0].field_availability["criteria"] == "disclosure_omitted"
        assert requests[0].answer_requirements == requests[1].answer_requirements
        request, result = requests[-1], results[-1]
        assert result.evidence[0].entity.source.path == root.source.path
        assert result.evidence[0].entity.source.source_sha == snapshot.source_sha
        assert request.answer_requirements.scope.entity_ids == ["KM-500c-2"]
        assert request.answer_requirements.required_fields == ["criteria"]
        assert result.answer.status == "fulfilled"
        assert result.evidence[0].entity.canonical_id == "KM-500c-2"
        assert result.evidence[0].field_locators["criteria"] == "/criteria"
        assert public.answer_assessments(values)
        assert final.pending_interaction is None
    finally:
        harness.doCleanups()
