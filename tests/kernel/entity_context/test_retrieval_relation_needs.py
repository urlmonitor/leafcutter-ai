"""Finite relation obligations preserve anchors, result kinds and source boundaries."""

import pytest

from integrations.research_needs import RepositoryNeedsInterpreter
from kernel.capabilities.research.state import Plan
from kernel.contracts.retrieval_needs import RetrievalNeedsOutput
from tests.knowledge.public_retrieval_needs_support import controlled_needs
from tests.kernel.entity_context.support import AC_ID


def needs(*, relation="covered_by", kind="test", doc="code", targets=None, completeness="examples"):
    body = controlled_needs({"original_question": "Find related evidence", "source_scope": {}},
                            AC_ID, ("content",), completeness=completeness)
    body["selections"].update(entity_types=[kind], document_types=[doc],
        relationships=[relation], target_ids=targets or [AC_ID])
    return RetrievalNeedsOutput.model_validate(body)


def interpreted(output):
    return RepositoryNeedsInterpreter().apply(Plan(output.original_question, "", [], []), output)


@pytest.mark.parametrize("change,reason", [
    ({"targets": [AC_ID, "EC-1200"]}, "one original anchor"),
    ({"kind": "ac", "doc": "ac_yaml"}, "result kind differ"),
    ({"completeness": "exhaustive_count"}, "exhaustive"),
    ({"completeness": "exhaustive_set"}, "exhaustive"),
])
def test_relation_requests_cannot_narrow_or_claim_complete_populations(change, reason):
    # covers: KM-500e-1-i
    # covers: DK-300d-4
    # angle: failure
    with pytest.raises(ValueError, match=reason):
        interpreted(needs(**change))


def test_related_result_is_not_required_to_equal_its_anchor(selection):
    # covers: KM-500e-1-i
    # covers: DK-300d-4
    # angle: discrimination
    output = needs()
    plan = interpreted(output)
    assert plan.answer_requirements["scope"]["entity_ids"] == []
    assert plan.answer_requirements["scope"]["root_id"] == AC_ID
    selection.choice = "get_related_tests"
    selection.port.response_entity = ("Test:pkg/tests.py", "Test", "pkg/tests.py", "")
    result, _, _ = selection.run(AC_ID, retrieval_needs=output, answer_requirements=plan.answer_requirements)
    assert selection.port.calls and selection.port.calls[0].arguments == {"entity_ids": [AC_ID]}
    assert result.output_payload["evidence"]
    assert all(item["source"]["locator"].find("Test%3Apkg%2Ftests.py") >= 0
               for item in result.output_payload["evidence"])


def test_unrelated_lookup_cannot_satisfy_relation_or_hide_paid_usage(selection):
    # covers: KM-500e-1-i
    # angle: discrimination
    output = needs()
    plan = interpreted(output)
    selection.choice = "get_entities"
    result, _, _ = selection.run(AC_ID, retrieval_needs=output, answer_requirements=plan.answer_requirements)
    assert selection.port.calls == []
    assert sum(item.calls for item in result.usage) == 1
    assert result.status.value == "failed"


def test_component_relation_respects_explicit_component_scope(selection):
    # covers: KM-500e-1-i
    # covers: DK-300d-4-ii
    # angle: failure
    output = needs(relation="governing_adrs", kind="adr", doc="adr", targets=["foreign_component"])
    plan = interpreted(output)
    selection.choice = "get_relevant_adrs"
    result, _, _ = selection.run(AC_ID, context=selection.context(AC_ID, components=("decision_kernel",)),
        retrieval_needs=output, answer_requirements=plan.answer_requirements)
    assert selection.port.calls == []
    assert result.status.value == "failed"
    assert sum(item.calls for item in result.usage) == 1


def test_examples_content_cannot_fulfill_after_kernel_excerpt_cut(selection):
    # covers: KM-500e-1-i
    # covers: DK-300d-4
    # angle: boundary
    import json

    from kernel.contracts.payloads import RetrievalLimits
    from tests.kernel.entity_context.graph_selection_support import GRAPH_FACT

    output = needs()
    plan = interpreted(output)
    assert plan.answer_requirements["require_complete"] is False
    selection.choice = "get_related_tests"
    selection.port.response_entity = ("Test:pkg/tests.py", "Test", "pkg/tests.py", "")
    result, _, _ = selection.run(AC_ID, retrieval_needs=output,
        answer_requirements=plan.answer_requirements, limits=RetrievalLimits(max_chars=12))
    assert selection.port.calls
    excerpts = [item["excerpt"] for item in result.output_payload["evidence"]]
    assert excerpts and sum(map(len, excerpts)) <= 12
    assert excerpts[0] == GRAPH_FACT[:12]
    assert result.output_payload["truncated"] is True
    assert json.loads(result.diagnostics["knowledge_answer"])["status"] != "fulfilled"
    assert result.status.value == "partial"
