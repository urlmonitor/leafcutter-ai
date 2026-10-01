"""Reproducible reviewed-case metrics; synthetic vectors do not prove semantic quality."""

from __future__ import annotations

from .ports import KnowledgeRetriever

from .contracts import KnowledgeRetrievalRequest
from .errors import invalid


async def evaluate(retriever: KnowledgeRetriever, cases: list[dict]) -> dict:
    """Run versioned requests and compare entity IDs with explicit reviewed judgments.

    Args:
        retriever: Serving port used to execute reviewed evaluation cases.
        cases: Reviewed evaluation requests and expected entity identifiers.

    Returns:
        dict: Per-case precision, recall, correction, provenance, size and latency measurements.
    """
    rows = []
    for case in cases:
        if not case.get("reviewed_by"):
            invalid("evaluation cases require reviewed judgments")
        request = KnowledgeRetrievalRequest.model_validate(case["request"])
        result = await retriever.retrieve(request)
        returned = {item.entity.canonical_id for item in result.evidence}
        relevant = set(case["relevant_ids"])
        corrections = set(case.get("correction_ids", []))
        valid = sum(
            item.entity.source.repository_id == request.repository_id
            and item.entity.source.source_sha == result.source_sha
            and bool(item.entity.source.path)
            for item in result.evidence
        )
        rows.append(
            {
                "id": case["id"],
                "synthetic": case.get("synthetic", False),
                "status": result.status,
                "precision_at_k": len(returned & relevant) / len(returned)
                if returned
                else float(not relevant),
                "recall_at_k": len(returned & relevant) / len(relevant)
                if relevant
                else float(not returned),
                "correction_coverage": len(returned & corrections) / len(corrections)
                if corrections
                else 1.0,
                "provenance_validity": valid / len(result.evidence) if result.evidence else 1.0,
                "content_bytes": len(result.model_dump_json().encode()),
                "latency_ms": result.stats.get("duration_ms"),
                "source_sha": result.source_sha,
                "generation_id": result.generation_id,
                "query_version": result.operation_version,
                "embedding_model": result.stats.get("embedding_model"),
                "result_count": len(result.evidence),
            }
        )
    return {
        "evaluation_version": "1",
        "cases": rows,
        "semantic_usefulness_proven": False,
        "quality_thresholds": "unset pending representative real-model reviewed baseline",
    }
