"""Requested source fields retain provenance and do not bypass disclosure bounds."""

import asyncio

import pytest

from knowledge.adapters.git_source import GitSourceResolver
from knowledge.contracts import KnowledgeRetrievalRequest, RetrievalBudget
from knowledge.service import KnowledgeService
from tests.knowledge.public_retrieval_needs_support import REPOSITORY, ROOT, SnapshotStorage, source_snapshot


def request(*, fields=("criteria", "test_spec"), level=3, byte_cap=32768):
    return KnowledgeRetrievalRequest(repository_id=REPOSITORY, request_id="source-fields-proof",
        operation="get_entities", mode="exact", arguments={"entity_ids": ["KM-500c-2"]},
        revision=source_snapshot().source_sha, disclosure_level=level,
        budget=RetrievalBudget(max_content_bytes=byte_cap),
        answer_requirements={"original_question": "What must tests demonstrate for KM-500c-2?",
            "required_fields": list(fields), "scope": {"population": "returned_entities"}, "require_complete": True})


@pytest.mark.parametrize("control", ["unavailable", "truncated"])
def test_unavailable_or_truncated_extra_field_never_fulfills_source_answer(control):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: failure
    # angle: boundary
    """An intact main criterion cannot hide failure reading its additionally requested field."""
    class ControlledFieldReader(GitSourceResolver):
        async def read(self, reference, max_bytes):
            if reference.locator == "/test_spec":
                if control == "unavailable":
                    raise ValueError("selected source field unavailable")
                return "x" * max_bytes
            return await super().read(reference, max_bytes)

    async def check():
        result = await KnowledgeService(SnapshotStorage(),
            source_resolver=ControlledFieldReader(ROOT, REPOSITORY)).retrieve(request())
        assert result.evidence and result.evidence[0].content
        assert result.answer.status != "fulfilled"
        missing = [item for item in result.answer.missing_fields if item.field == "test_spec"]
        assert missing and missing[0].reason == ("truncated" if control == "truncated" else "unknown")
        assert not result.evidence[0].field_contents
        assert len(result.model_dump_json().encode()) <= 16000
    asyncio.run(check())


def test_requested_source_fields_fit_whole_response_budget():
    # covers: KM-500e-1-i
    # covers: KM-400d-4
    # angle: boundary
    """The extra field envelope consumes the existing total response byte budget."""
    async def check():
        result = await KnowledgeService(SnapshotStorage(),
            source_resolver=GitSourceResolver(ROOT, REPOSITORY)).retrieve(request(byte_cap=2000))
        assert len(result.model_dump_json().encode()) <= 2000
        assert result.answer.status != "fulfilled"
        assert result.truncated
    asyncio.run(check())


@pytest.mark.parametrize("level", [0, 3])
def test_backend_extras_and_unrequested_test_spec_are_never_disclosed(level):
    # covers: KM-500e-1-i
    # covers: KM-400d-1
    # angle: adversarial
    # angle: discrimination
    """Additional backend properties cannot create unauthorized source-field evidence."""
    class PollutedStorage(SnapshotStorage):
        async def query(self, *args, **kwargs):
            rows = await super().query(*args, **kwargs)
            for row in rows:
                row.properties.update(test_spec=[{"name": "UNTRUSTED-BACKEND-VALUE"}], private_extra="DO-NOT-DISCLOSE")
            return rows

    async def check():
        result = await KnowledgeService(PollutedStorage(),
            source_resolver=GitSourceResolver(ROOT, REPOSITORY)).retrieve(request(fields=("criteria",), level=level))
        assert result.evidence
        assert all(not item.field_contents for item in result.evidence)
        assert "UNTRUSTED-BACKEND-VALUE" not in result.model_dump_json()
        assert "DO-NOT-DISCLOSE" not in result.model_dump_json()
    asyncio.run(check())


@pytest.mark.parametrize("control", ["extra_field", "unrequested", "wrong_locator", "missing_locator", "discovery_level", "empty_text"])
def test_public_mapper_rejects_untrusted_additional_field_text(control):
    # covers: KM-500e-1-i
    # covers: KM-400d-1
    # angle: adversarial
    # angle: seam
    """A malformed retriever-port result cannot promote unrequested or uncited field text."""
    from types import SimpleNamespace
    from integrations.knowledge_capability import map_bounded_evidence
    from kernel.config import load_kernel_config
    from kernel.contracts.base import utc_now
    from kernel.contracts.payloads import RetrievalRequestPayload
    from knowledge.answers import assess_answer

    async def check():
        fields = ("criteria",) if control in {"extra_field", "unrequested"} else ("criteria", "test_spec")
        req = request(fields=fields)
        result = await KnowledgeService(SnapshotStorage(),
            source_resolver=GitSourceResolver(ROOT, REPOSITORY)).retrieve(req)
        assert result.evidence
        field = "private_extra" if control == "extra_field" else "test_spec"
        item = result.evidence[0]
        locator = "/criteria" if control == "wrong_locator" else "/test_spec"
        result.evidence = [item.model_copy(update={
            "field_contents": {field: " \n  " if control == "empty_text" else "UNTRUSTED-PORT-FIELD"},
            "field_locators": {} if control == "missing_locator" else {field: locator},
            "disclosure_level": 0 if control == "discovery_level" else 3,
        })]
        payload = RetrievalRequestPayload(need={"id": "need.question", "category": "task_context", "question": "Requested facts"},
            answer_requirements=req.answer_requirements.model_dump(mode="json"))
        mapped = map_bounded_evidence(SimpleNamespace(config=load_kernel_config(), clock=utc_now),
            payload, req, result, SimpleNamespace(id="inv-0123456789abcdef"))
        assert mapped
        assert all("UNTRUSTED-PORT-FIELD" not in (item.excerpt or "") for item in mapped)
        assert all(not item.field_contents for item in result.evidence)
        if "test_spec" in fields:
            assert assess_answer(req, result).status != "fulfilled"
    asyncio.run(check())


@pytest.mark.parametrize("control", ["one_result", "shared_chars"])
def test_additional_public_citations_share_result_and_character_limits(control):
    # covers: KM-500e-1-i
    # covers: KM-400d-4
    # angle: boundary
    """An extra citation consumes the same caller limits as its main criterion."""
    from types import SimpleNamespace
    from integrations.knowledge_capability import map_bounded_evidence
    from kernel.config import load_kernel_config
    from kernel.contracts.base import utc_now
    from kernel.contracts.payloads import RetrievalRequestPayload
    from knowledge.answers import assess_answer

    async def check():
        req = request()
        if control == "one_result":
            req = req.model_copy(update={"budget": req.budget.model_copy(update={"max_results": 1})})
        result = await KnowledgeService(SnapshotStorage(),
            source_resolver=GitSourceResolver(ROOT, REPOSITORY)).retrieve(req)
        assert result.answer.status == "fulfilled"
        payload = RetrievalRequestPayload(need={"id": "need.question", "category": "task_context", "question": "Requested facts"},
            answer_requirements=req.answer_requirements.model_dump(mode="json"),
            limits={"max_chars": 700 if control == "shared_chars" else None})
        mapped = map_bounded_evidence(SimpleNamespace(config=load_kernel_config(), clock=utc_now),
            payload, req, result, SimpleNamespace(id="inv-0123456789abcdef"))
        assert mapped
        if control == "one_result":
            assert len(mapped) <= 1
        else:
            assert sum(len(item.excerpt or "") for item in mapped) <= 700
        assert result.truncated
        assert assess_answer(req, result).status != "fulfilled"
    asyncio.run(check())
