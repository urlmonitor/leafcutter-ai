"""Independent contract tests for the isolated, single-request Jev experiment.

These prove batching/validation and model-output handling, not semantic Jev quality.
The independently authored evaluation set supplies the latter check.
"""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy

import httpx
import pytest

from integrations.retrieval_needs_probe import (
    NeedsCatalog,
    NeedsRequest,
    ProbeLimits,
    build_needs_batch,
    run_needs_probe,
)
from kernel.providers.base import JevInvalidResponse, JevPayloadTooLarge, JevUnavailable
from kernel.providers.jev_errors import JevInvalidRequest, JevTransientError
from kernel.providers.jev_http import HttpTransport
from kernel.providers.jev_wire import RawResponse


def request() -> NeedsRequest:
    return NeedsRequest(
        original_question="For KM-500c-2, what must tests demonstrate?",
        context=["Synthetic context: the requested criterion is in the AC store."],
        catalog=NeedsCatalog(
            entity_types={"ac": "Acceptance criterion", "test": "Test source"},
            target_ids={"KM-500c-2": "Literal criterion ID from the question"},
            required_fields={"criteria": "Acceptance criteria", "work_status": "Implementation status"},
            document_types={"ac_yaml": "Canonical AC definition", "test_source": "Test source code"},
            relationships={"parents_1": "Immediate parent, one hop", "children_1": "Direct children, one hop"},
        ),
    )


class RecordingTransport:
    name = "independent-test-transport"
    version = "1"

    def __init__(self, *, probability=0.9, error=None, malformed=None, selected=None, choices=None, probabilities=None):
        self.calls = []
        self.probability = probability
        self.error = error
        self.malformed = malformed
        self.selected = selected
        self.choices = choices or {}
        self.probabilities = probabilities or {}

    async def send(self, state, questions, *, purpose=""):
        self.calls.append(deepcopy({"state": state, "questions": questions, "purpose": purpose}))
        if self.error:
            raise self.error
        answers = {}
        for key, question in questions.items():
            if question["type"] == "noul":
                probability = self.probability if self.selected is None else (0.95 if key in self.selected else 0.05)
                probability = self.probabilities.get(key, probability)
                answers[key] = {"type": "noul", "noul": probability}
            else:
                labels = question["criteria"]
                chosen = next(label for label in ("fields", "single_entity", "not_applicable", "sufficient") if label in labels)
                chosen = self.choices.get(key, chosen)
                answers[key] = {"type": "choice", "choice": chosen,
                                "probabilities": {label: float(label == chosen) for label in labels}}
        if self.malformed == "missing":
            answers.pop(next(iter(answers)))
        elif self.malformed == "unknown_choice":
            key = next(key for key, value in answers.items() if value["type"] == "choice")
            answers[key] = {"type": "choice", "choice": "unoffered",
                            "probabilities": {"unoffered": 1.0}}
        return RawResponse(model="test-only", request_id="test-request", answers=answers,
                           input_tokens=11, output_tokens=7)

    async def aclose(self):
        return None


def test_one_actual_transport_call_contains_all_independent_dimensions():
    # covers: KM-500e-1
    # angle: seam
    source = request()
    transport = RecordingTransport()
    batch = build_needs_batch(source)
    result = asyncio.run(run_needs_probe(source, transport))
    assert len(transport.calls) == result.provider_calls == 1
    assert len(transport.calls[0]["questions"]) == len(batch.questions)
    assert len(batch.questions) > 6
    assert result.original_question == source.original_question
    assert transport.calls[0]["state"]["original_question"] == source.original_question
    assert result.selections["target_ids"] == ["KM-500c-2"]
    assert set(result.selections["required_fields"]) == {"criteria", "work_status"}
    assert result.response.request_id == "test-request"
    assert result.response.usage.input_tokens == 11
    assert result.detail_mode == "fields"
    assert result.completeness == "single_entity"


def test_uncertain_options_remain_uncertain_not_silently_selected():
    # covers: KM-500e-1
    # angle: boundary
    transport = RecordingTransport(probability=0.5)
    result = asyncio.run(run_needs_probe(request(), transport))
    assert result.selections["target_ids"] == []
    assert result.uncertain["target_ids"] == ["KM-500c-2"]
    assert result.unresolved
    assert result.status == "needs_resolution"
    assert result.response.answers
    assert len(transport.calls) == 1


def test_transient_provider_failure_never_retries():
    # covers: KM-500c-3
    # angle: failure
    transport = RecordingTransport(error=JevTransientError("controlled transient"))
    with pytest.raises(JevUnavailable):
        asyncio.run(run_needs_probe(request(), transport))
    assert len(transport.calls) == 1


@pytest.mark.parametrize("malformed", ["missing", "unknown_choice"])
def test_malformed_provider_output_fails_instead_of_returning_a_plan(malformed):
    # covers: KM-500e-1
    # angle: failure
    transport = RecordingTransport(malformed=malformed)
    with pytest.raises(JevInvalidResponse):
        asyncio.run(run_needs_probe(request(), transport))
    assert len(transport.calls) == 1


def test_question_overflow_is_refused_before_any_transport_or_chunking():
    # covers: KM-500c-3
    # angle: boundary
    transport = RecordingTransport()
    with pytest.raises((JevInvalidRequest, ValueError)):
        asyncio.run(run_needs_probe(request(), transport, limits=ProbeLimits(max_questions_per_call=1)))
    assert transport.calls == []


def test_state_overflow_is_refused_before_any_transport():
    # covers: KM-500c-3
    # angle: boundary
    transport = RecordingTransport()
    with pytest.raises((JevPayloadTooLarge, ValueError)):
        asyncio.run(run_needs_probe(request(), transport, limits=ProbeLimits(max_state_chars=10)))
    assert transport.calls == []


def test_ungrounded_offered_id_is_rejected_before_provider():
    # covers: KM-500a-1
    # angle: failure
    transport = RecordingTransport()
    payload = request().model_dump(mode="json")
    payload["catalog"]["target_ids"]["FICTION-999"] = "Unobserved invented target"
    with pytest.raises(ValueError):
        source = NeedsRequest.model_validate(payload)
        asyncio.run(run_needs_probe(source, transport))
    assert transport.calls == []


def test_input_question_and_context_are_not_mutated():
    # covers: KM-500e-1
    # angle: criterion
    source = request()
    before = source.model_dump(mode="json")
    asyncio.run(run_needs_probe(source, RecordingTransport()))
    assert source.model_dump(mode="json") == before


def test_empty_supported_selection_cannot_be_a_resolved_plan():
    # covers: KM-500e-1
    # angle: failure
    result = asyncio.run(run_needs_probe(request(), RecordingTransport(probability=0.0)))
    assert result.status == "needs_resolution"
    assert result.unresolved
    assert result.selections["entity_types"] == []


def test_exact_criterion_selective_output_keeps_need_without_population_gate():
    # covers: KM-500e-1
    # angle: discrimination
    selected = {"entity_types.ac", "target_ids.KM-500c-2", "required_fields.criteria", "document_types.ac_yaml"}
    result = asyncio.run(run_needs_probe(request(), RecordingTransport(selected=selected)))
    assert result.status == "decided"
    assert result.unresolved == []
    assert result.selections["relationships"] == []
    assert result.selections["required_fields"] == ["criteria"]
    assert result.hierarchy_scope == "not_applicable"


def test_multiple_ids_and_document_types_survive_without_collapsing_to_one():
    # covers: KM-500e-1
    # angle: criterion
    payload = request().model_dump(mode="json")
    payload["original_question"] = "Compare KM-500c-1 and KM-500c-2 and their test source."
    payload["catalog"]["target_ids"]["KM-500c-1"] = "Other literal ID"
    payload["source_scope"] = {"repository": "synthetic", "revision": "pinned", "read_roots": ["docs"]}
    source = NeedsRequest.model_validate(payload)
    selected = {"entity_types.ac", "entity_types.test", "target_ids.KM-500c-1", "target_ids.KM-500c-2",
                "required_fields.criteria", "document_types.ac_yaml", "document_types.test_source"}
    result = asyncio.run(run_needs_probe(source, RecordingTransport(selected=selected,
                                         choices={"completeness": "selected_entities"})))
    assert set(result.selections["target_ids"]) == {"KM-500c-1", "KM-500c-2"}
    assert set(result.selections["document_types"]) == {"ac_yaml", "test_source"}
    assert result.source_scope == source.source_scope
    assert result.completeness == "selected_entities"


def test_real_http_transport_sends_one_request_with_all_fields():
    # covers: KM-500e-1
    # angle: seam
    calls = []
    source = request()
    batch = build_needs_batch(source)

    def handler(http_request):
        body = json.loads(http_request.content)
        calls.append(body)
        answers = {}
        for key, question in body["questions"].items():
            if question["type"] == "noul":
                answers[key] = {"type": "noul", "noul": 0.9 if key.startswith("entity_types.") else 0.1}
            else:
                label = next(value for value in ("fields", "single_entity", "not_applicable", "sufficient") if value in question["criteria"])
                answers[key] = {"type": "choice", "choice": label, "probabilities": {label: 1.0}}
        return httpx.Response(200, json={"model": "mock-model", "answers": answers})

    async def invoke():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            transport = HttpTransport(api_key="fake-key", model="jev-latest", timeout_seconds=10, client=client)
            return await run_needs_probe(source, transport)

    result = asyncio.run(invoke())
    assert len(calls) == result.provider_calls == 1
    assert set(calls[0]["questions"]) == {spec.id for spec in batch.questions}
    assert calls[0]["state"]["original_question"] == source.original_question
    assert calls[0]["model"] == "jev-latest"


def test_uncertain_named_target_is_unresolved_even_with_usable_fields():
    # covers: KM-500e-1
    # angle: discrimination
    selected = {"entity_types.ac", "required_fields.criteria", "document_types.ac_yaml"}
    transport = RecordingTransport(selected=selected, probabilities={"target_ids.KM-500c-2": 0.5})
    result = asyncio.run(run_needs_probe(request(), transport))
    assert result.uncertain["target_ids"] == ["KM-500c-2"]
    assert result.status == "needs_resolution"
    assert "target_ids" in result.unresolved


def test_no_authoritative_document_type_cannot_claim_complete_need_selection():
    # covers: KM-500e-1
    # angle: discrimination
    selected = {"entity_types.ac", "required_fields.criteria", "target_ids.KM-500c-2"}
    result = asyncio.run(run_needs_probe(request(), RecordingTransport(selected=selected)))
    assert result.status == "needs_resolution"
    assert "document_types" in result.unresolved


def test_parent_context_can_name_relative_target_without_inventing_parent_id():
    # covers: KM-500e-1
    # angle: discrimination
    selected = {"entity_types.ac", "target_ids.KM-500c-2", "document_types.ac_yaml", "relationships.parents_1"}
    transport = RecordingTransport(selected=selected,
                                   choices={"detail_mode": "bounded_context", "completeness": "selected_entities"})
    result = asyncio.run(run_needs_probe(request(), transport))
    assert result.status == "decided"
    assert result.selections["target_ids"] == ["KM-500c-2"]
    assert result.selections["relationships"] == ["parents_1"]


def test_two_entity_comparison_without_second_id_or_relation_remains_unresolved():
    # covers: KM-500e-1
    # angle: discrimination
    selected = {"entity_types.ac", "target_ids.KM-500c-2", "required_fields.criteria", "document_types.ac_yaml"}
    result = asyncio.run(run_needs_probe(request(), RecordingTransport(selected=selected,
                                         choices={"completeness": "selected_entities"})))
    assert result.status == "needs_resolution"
    assert "multiple_target_ids" in result.unresolved
