"""Independent continuation checks against public query-growth invocation."""
import asyncio
import pytest
from types import SimpleNamespace

from kernel.contracts import CapabilityResult, ResultStatus, schema_ids
from tests.knowledge.test_query_admission import admission, candidate


def context():
    """Supply real graph budget configuration at the controlled invocation boundary."""
    return SimpleNamespace(config=SimpleNamespace(intent=SimpleNamespace(max_clarifications=2),
        limits=SimpleNamespace(langgraph_recursion_limit=100)),
        scope=SimpleNamespace(component_ids=["allowed"]))



def test_resume_rejects_other_verified_version_of_same_operation(tmp_path, monkeypatch):
    # covers: KM-500c-1
    # covers: KM-500b-3
    # angle: failure
    from integrations import query_growth, knowledge_execution
    catalog, verifier, backend = admission(tmp_path)
    original = candidate()
    first = asyncio.run(verifier.verify_and_activate(original, repository_id="repo", source_sha="a" * 40))
    replacement = candidate()
    replacement["descriptor"]["version"] = "2"
    newer = asyncio.run(verifier.verify_and_activate(replacement, repository_id="repo",
        source_sha="a" * 40, expected_active_digest=first["digest"]))
    state = {"phase": "building", "repository_id": "repo", "source_sha": "a" * 40,
        "generation_id": backend.snapshot.generation_id, "question": "Which directly declared tests?",
        "component_ids": ["component"], "need_id": "need.tests", "build_attempted": True}
    child = SimpleNamespace(current_wait=True, status=ResultStatus.COMPLETED,
                            output_schema_id=schema_ids.QUERY_CANDIDATE)
    invocation = SimpleNamespace(id="invoke", work_item_id="work", child_outcomes=[child],
                                 continuation=SimpleNamespace(state=state))
    output = {"candidate": original}
    monkeypatch.setattr(query_growth, "load_output_payload", lambda *_: output)
    payload = SimpleNamespace(detail="locator")
    waiting = asyncio.run(query_growth.invoke_query_growth(None, catalog, verifier,
        invocation, context(), payload, []))
    assert waiting.status == ResultStatus.WAITING
    invocation.continuation = SimpleNamespace(state=waiting.continuation_state)
    child.output_schema_id = schema_ids.QUERY_ACTIVATION_RECEIPT
    output = {"receipt": newer}
    executed = []

    async def retrieval(*args, **kwargs):
        executed.append(True)
        return CapabilityResult(invocation_id="invoke", work_item_id="work", status=ResultStatus.COMPLETED, output_schema_id=schema_ids.EVIDENCE_BUNDLE, output_payload={})

    monkeypatch.setattr(knowledge_execution, "invoke_knowledge", retrieval)
    payload = SimpleNamespace(detail="locator", model_copy=lambda **_: payload)
    result = asyncio.run(query_growth.invoke_query_growth(None, catalog, verifier,
        invocation, context(), payload, []))
    assert executed == [], result.error
    assert result.error.code == "scope_mismatch"
    assert executed == []


@pytest.mark.parametrize("override_scope", [False, True])
def test_scalar_clarification_preserves_pins_and_cannot_override_scope(monkeypatch, override_scope):
    # covers: KM-500a-1
    # covers: KM-500c-1
    # angle: failure
    import json
    from integrations import query_growth, knowledge_execution
    from kernel.contracts.payloads import RetrievalRequestPayload
    from kernel.contracts.evidence import EvidenceNeed
    descriptor = {"operation": "get_filtered_component_tests", "version": "1", "digest": "d" * 64,
        "description": "Direct tests for a component filtered by status", "modes": ["graph"],
        "parameters": {"component_ids": {"type": "string_list", "required": True},
                       "status": {"type": "string", "required": True}}}
    catalog = SimpleNamespace(descriptors=lambda: [descriptor])
    state = {"phase": "select", "question": "Original test question", "original_question": "Original test question",
        "need_id": "need.tests", "repository_id": "repo", "source_sha": "a" * 40,
        "generation_id": "generation", "component_ids": ["allowed"], "clarifications": 0,
        "build_attempted": False, "arguments": {}}
    invocation = SimpleNamespace(id="invoke", work_item_id="work", child_outcomes=[],
                                 continuation=SimpleNamespace(state=state))
    ctx = context()
    payload = RetrievalRequestPayload(need=EvidenceNeed(id="need.tests",category="task_context",
                                                      question="Original test question"))

    async def choose(*args):
        return descriptor["operation"], []

    monkeypatch.setattr(query_growth, "choose", choose)
    waiting = asyncio.run(query_growth.invoke_query_growth(None, catalog, None, invocation, ctx, payload, []))
    assert waiting.status == ResultStatus.WAITING
    assert len(waiting.requests) == 1 and waiting.requests[0].kind.value == "human"
    assert "status" in waiting.requests[0].question
    assert waiting.continuation_state["source_sha"] == "a" * 40
    arguments = {"status": "done"}
    if override_scope:
        arguments["component_ids"] = ["foreign"]
    answer = {"free_text": json.dumps({"question": "Clarified direct-test question", "arguments": arguments})}
    monkeypatch.setattr(query_growth, "load_output_payload", lambda *_: answer)
    invocation.continuation = SimpleNamespace(state=waiting.continuation_state)
    invocation.child_outcomes = [SimpleNamespace(current_wait=True, status=ResultStatus.COMPLETED,
                                                 output_schema_id=schema_ids.HUMAN_ANSWER)]
    observed = []

    async def retrieve(port, inv, context, request, *args, **kwargs):
        observed.append(request)
        return CapabilityResult(invocation_id="invoke", work_item_id="work", status=ResultStatus.COMPLETED, output_schema_id=schema_ids.QUERY_ACTIVATION_RECEIPT, output_payload={"receipt": {}})

    monkeypatch.setattr(knowledge_execution, "invoke_knowledge", retrieve)
    result = asyncio.run(query_growth.invoke_query_growth(None, catalog, None, invocation, ctx, payload, []))
    if override_scope:
        assert result.status == ResultStatus.FAILED
        assert not observed
    else:
        assert result.status == ResultStatus.COMPLETED
        assert observed[0].need.question == "Clarified direct-test question"
        assert observed[0].knowledge["revision"] == "a" * 40
        assert observed[0].knowledge["operation_digest"] == "d" * 64
        assert observed[0].knowledge["arguments"] == {"component_ids": ["allowed"], "status": "done"}
        assert result.diagnostics["query_original_question"] == "Original test question"


@pytest.mark.parametrize("selection,attempted,clarifications,expected", [
    ("build", True, 0, "build_exhausted"),
    ("clarify", False, 2, "clarification_exhausted"),
])
def test_no_progress_stops_without_new_children(monkeypatch, selection, attempted, clarifications, expected):
    # covers: KM-500c-3
    # angle: criterion
    # angle: failure
    from integrations import query_growth
    state = {"phase": "select", "target_kind": "Test", "repository_id": "repo", "generation_id": "generation",
        "supported_kinds": ["Test"], "supported_fields": {"Test": ["status"]}, "question": "Original unresolved question", "need_id": "need.tests",
        "component_ids": ["component"], "source_sha": "a" * 40,
        "build_attempted": attempted, "clarifications": clarifications}
    invocation = SimpleNamespace(id="invoke", work_item_id="work", child_outcomes=[],
                                 continuation=SimpleNamespace(state=state))
    ctx = context()
    async def choose(*args):
        return selection, []
    monkeypatch.setattr(query_growth, "choose", choose)
    for _ in range(2):
        result = asyncio.run(query_growth.invoke_query_growth(None, SimpleNamespace(descriptors=lambda: []),
            None, invocation, ctx, SimpleNamespace(), []))
        assert result.status == ResultStatus.BLOCKED
        assert result.error.code == expected
        assert not result.requests
        assert invocation.continuation.state["question"] == "Original unresolved question"


def test_repeated_failed_builder_delivery_never_becomes_activation():
    # covers: KM-500c-3
    # angle: criterion
    # angle: failure
    from integrations.query_growth import invoke_query_growth
    state = {"phase": "building", "question": "Original unresolved question", "build_attempted": True}
    child = SimpleNamespace(current_wait=True, output_schema_id=schema_ids.QUERY_CANDIDATE,
                            status=ResultStatus.FAILED)
    for _ in range(2):
        invocation = SimpleNamespace(id="invoke", work_item_id="work", child_outcomes=[child],
                                     continuation=SimpleNamespace(state=dict(state)))
        result = asyncio.run(invoke_query_growth(None, None, None, invocation, context(), None, []))
        assert result.status == ResultStatus.FAILED and result.error.code == "build_failed"
        assert not result.requests


@pytest.mark.parametrize("target,build_allowed", [("Test", True), ("Decision", False)])
def test_source_mapping_is_checked_before_build_packet(monkeypatch, target, build_allowed):
    # covers: KM-500a-3
    # covers: KM-500b-1
    # angle: criterion
    from integrations import query_growth
    descriptor = {**candidate()["descriptor"], "modes": ["graph"], "digest": "d" * 64}
    state = {"phase": "select", "planning_context": True, "question": "Original question",
        "need_id": "need.tests", "repository_id": "repo", "source_sha": "a" * 40,
        "generation_id": "generation", "component_ids": ["component"], "clarifications": 0,
        "supported_kinds": ["Component", "AcceptanceCriterion", "Test"], "supported_fields": {"Test": ["status"]}, "build_attempted": False}
    invocation = SimpleNamespace(id="invoke", work_item_id="work", child_outcomes=[],
                                 continuation=SimpleNamespace(state=state))
    ctx = context()
    choices = []
    async def choose(context, inv, purpose, *args):
        choices.append(purpose)
        return (target if purpose == "knowledge.query_target" else "build"), []
    monkeypatch.setattr(query_growth, "choose", choose)
    result = asyncio.run(query_growth.invoke_query_growth(None,
        SimpleNamespace(descriptors=lambda: [descriptor]), None, invocation, ctx, None, []))
    if build_allowed:
        assert result.status == ResultStatus.WAITING
        packet = result.requests[0].payload
        assert packet["source_sha"] == "a" * 40 and packet["need_id"] == "need.tests"
        assert packet["available_queries"][0]["operation"] == descriptor["operation"]
        assert packet["remaining_budget"]["construction_attempts_remaining"] == 0
        assert packet["remaining_budget"]["clarifications_remaining"] == 2
        assert "Test" in packet["expected_result"]
        assert result.continuation_state["selection_reason"]
    else:
        assert result.status == ResultStatus.BLOCKED
        assert result.error.code == "source_mapping_unsupported"
        assert not result.requests
        assert choices == ["knowledge.query_target"]
