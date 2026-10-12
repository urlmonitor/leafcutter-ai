"""Reviewed judgments remain distinct from vector mechanics and runtime measures."""

import asyncio
import importlib


def test_reviewed_cases_measure_relevance_corrections_provenance_and_size():
    # covers: KM-400c-5
    # angle: criterion
    evaluation = importlib.import_module("knowledge.evaluation")
    c = importlib.import_module("knowledge.contracts")

    class Retriever:
        async def retrieve(self, request):
            node = c.Entity(
                canonical_id="D-corrected",
                kind="Decision",
                title="Correction",
                source=c.SourceReference(
                    repository_id="repo", source_sha="a" * 40, path="fixture.yaml"
                ),
            )
            return c.KnowledgeRetrievalResult(
                request_id=request.request_id,
                retrieval_id="test",
                status="ok",
                requested_mode="exact",
                executed_mode="exact",
                source_sha="a" * 40,
                generation_id="g",
                evidence=[c.KnowledgeEvidence(entity=node)],
                stats={"duration_ms": 2.0},
            )

    cases = [
        {
            "id": "synthetic-reviewed",
            "synthetic": True,
            "reviewed_by": "test-reviewer",
            "request": {
                "repository_id": "repo",
                "request_id": "test",
                "arguments": {"entity_ids": ["D-corrected"]},
            },
            "relevant_ids": ["D-corrected", "D-other"],
            "correction_ids": ["D-corrected"],
        }
    ]
    report = asyncio.run(evaluation.evaluate(Retriever(), cases))
    row = report["cases"][0]
    assert row["precision_at_k"] == 1.0 and row["recall_at_k"] == 0.5
    assert row["correction_coverage"] == 1.0 and row["provenance_validity"] == 1.0
    assert row["content_bytes"] > 0 and row["latency_ms"] == 2.0
    assert report["semantic_usefulness_proven"] is False
