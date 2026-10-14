"""Bounded content is actual source text, never a summary or backend property."""

import asyncio
import pytest

from knowledge.adapters.git_source import GitSourceResolver
from knowledge.answers import assess_answer
from knowledge.contracts import KnowledgeRetrievalResult
from knowledge.disclosure import evidence
from tests.knowledge.public_retrieval_needs_support import ROOT, REPOSITORY, source_snapshot
from tests.knowledge.test_requested_field_disclosure import request


@pytest.mark.parametrize("control,expected", [
    ("source", "present"), ("withheld", "disclosure_omitted"), ("unavailable", "unknown"),
    ("empty", "canonical_absent"), ("whitespace", "canonical_absent"), ("truncated", "truncated"),
])
def test_content_requires_actual_bounded_source(control, expected):
    # covers: KM-500e-1-i
    # covers: KM-400d-1
    # angle: failure
    # angle: boundary
    class Reader(GitSourceResolver):
        async def read(self, reference, max_bytes):
            if control == "unavailable":
                raise ValueError("Controlled source failure")
            if control == "empty":
                return ""
            if control == "whitespace":
                return " \n\t"
            if control == "truncated":
                return "x" * max_bytes
            return await super().read(reference, max_bytes)

    async def check():
        snapshot = source_snapshot()
        node = next(node for node in snapshot.nodes if node.canonical_id == "KM-500c-2")
        node = node.model_copy(update={"properties": {**node.properties, "content": "UNTRUSTED PROPERTY"}})
        req = request(fields=("content",), level=0 if control == "withheld" else 3)
        item = await evidence(node, req, {}, 100 if control == "truncated" else 12000,
                              source_resolver=Reader(ROOT, REPOSITORY))
        assert item.field_availability["content"] == expected
        assert item.field_locators["content"] == node.source.locator
        result = KnowledgeRetrievalResult(request_id=req.request_id, retrieval_id="content-proof",
            status="ok", requested_mode=req.mode, executed_mode=req.mode, evidence=[item],
            source_sha=snapshot.source_sha, generation_id=snapshot.generation_id)
        answer = assess_answer(req, result)
        assert (answer.status == "fulfilled") is (control == "source")
        if control == "source":
            assert item.content == await GitSourceResolver(ROOT, REPOSITORY).read(node.source, 12000)
        assert item.content != "UNTRUSTED PROPERTY"
    asyncio.run(check())
