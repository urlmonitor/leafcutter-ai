"""Frozen public eligibility cases: controlled interpretation/choice, actual retrieval sources."""
import json
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
import yaml

from kernel.contracts import RunStatus, schema_ids
from tests.knowledge.public_retrieval_needs_support import answer_assessments
from tests.knowledge.query_eligibility_support import (
    CASES, ORACLE, choices, observe_requests, operation_batches,
    pinned_snapshot, public_harness, run, run_case,
)


@pytest.mark.parametrize("case", CASES[:8], ids=lambda case: case["id"])
def test_public_population_choice_executes_frozen_scope(monkeypatch, case):
    # covers: KM-500a-2-i
    # angle: reachability
    harness = public_harness(monkeypatch, case["catalog"])
    harness.operation = "get_ac_descendants"
    requests, _ = observe_requests(monkeypatch)
    try:
        final, values = run(run_case(harness, case))
        batches = operation_batches(harness)
        assert len(batches) == 1
        expected = case["expected_requirements"]
        assert batches[0].state["original_question"] == case["question"]
        assert batches[0].state["answer_requirements"] == expected
        assert requests, final.model_dump_json()
        first = requests[0]
        assert first.operation == case["expected_operation"]
        assert first.arguments == {"root_id": expected["scope"]["root_id"]}
        assert first.answer_requirements.model_dump(mode="json") == expected
        assert all(request.revision == pinned_snapshot().source_sha for request in requests)
        assert first.budget.max_results > 0
        children = [row for row in values["requests"].values() if row.payload_schema == schema_ids.RETRIEVAL_REQUEST]
        assert len(children) == 1
        assert children[0].payload["source_ids"] == ["knowledge.graph"]
        assert children[0].payload["retrieval_needs"]["source_scope"]["read_roots"] == ["docs"]
        assert children[0].payload["answer_requirements"] == expected
        assert choices(batches[0]).keys() >= {"get_ac_descendants", "unsupported"}
        assert not ({"get_entities", "get_related_tests", "get_declared_dependents"} & choices(batches[0]).keys()), (
            "Proved wrong populations reached the paid selector: " + repr(list(choices(batches[0]))))
        assert "host.query_build" not in harness.capabilities_used(values)
        assert final.status is not RunStatus.WAITING_HUMAN
    finally:
        harness.doCleanups()


def test_exact_ac_fields_keep_hydratable_get_entities(monkeypatch):
    # covers: KM-500a-2-i
    # angle: criterion
    case = CASES[8]
    harness = public_harness(monkeypatch, case["catalog"])
    requests, _ = observe_requests(monkeypatch)
    try:
        node = next(node for node in pinned_snapshot().nodes if node.canonical_id == "KM-500c-2")
        assert "test_spec" not in node.properties, "Control must require immutable source hydration"
        final, values = run(run_case(harness, case))
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        assert len(operation_batches(harness)) == 1
        assert requests[0].operation == "get_entities"
        assert requests[0].arguments == {"entity_ids": ["KM-500c-2"]}
        assert all(request.answer_requirements == requests[0].answer_requirements for request in requests)
        assert requests[0].answer_requirements.model_dump(mode="json") == case["expected_requirements"]
        evidence = list(values["evidence"].values())
        for field, expected in ORACLE["exact_record"]["required_fields"].items():
            matches = [item for item in evidence if item.source.section_locator == "/" + field]
            assert len(matches) == 1
            item = matches[0]
            assert (yaml.safe_load(item.excerpt) if field == "test_spec" else item.excerpt) == expected
            uri = urlsplit(item.source.locator)
            query = parse_qs(uri.query)
            assert unquote(uri.path).strip("/") == "KM-500c-2"
            assert query["path"] == [node.source.path]
            assert query["locator"] == ["/" + field]
            assert item.source.source_version.commit == pinned_snapshot().source_sha
        assert answer_assessments(values)[-1]["status"] == "fulfilled"
        offered = choices(operation_batches(harness)[0])
        assert "get_entities" in offered
        assert "get_declared_dependents" in offered, "Same-kind self-dependency is not proved disjoint"
        assert not ({"get_related_tests", "get_ac_descendants"} & offered.keys()), offered
    finally:
        harness.doCleanups()


@pytest.mark.parametrize("case", [CASES[0], CASES[1]], ids=lambda case: case["id"])
def test_selection_does_not_promote_incomplete_counts(monkeypatch, case):
    # covers: KM-500a-2-i
    # angle: discrimination
    harness = public_harness(monkeypatch, case["catalog"])
    harness.operation = "get_ac_descendants"
    harness.config = harness.config.model_copy(update={"retrieval":
        harness.config.retrieval.model_copy(update={"top_k": 2})})
    requests, neutral = observe_requests(monkeypatch)
    try:
        final, values = run(run_case(harness, case))
        assert len(operation_batches(harness)) == 1
        assert requests[0].operation == "get_ac_descendants"
        assert neutral and any(item.truncated for item in neutral)
        answers = answer_assessments(values)
        assert len(answers) == 1
        answer = answers[0]
        assert 0 < answer["completeness"]["known_count"] < ORACLE["populations"]["tq_all"]["canonical_count"]
        assert answer["completeness"]["exact_total"] is None
        assert answer["work_status_counts"] is None
        assert answer["status"] != "fulfilled"
        assert final.status is not RunStatus.COMPLETED
        assert all(json.loads(row.diagnostics["knowledge_answer"])["completeness"]["exact_total"] is None
            for row in values["results"].values() if "knowledge_answer" in row.diagnostics)
    finally:
        harness.doCleanups()
