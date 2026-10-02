"""Reviewed research evaluation over the same validated retrieval entry point.
MODULE: knowledge.evaluation
GOAL: Measure actual retrieval independently from reviewed expected outcomes.
BUSINESS CONTEXT: Unavailable or unexecuted work is never perfect empty retrieval.
ARCHITECTURE: Legacy-compatible evaluator plus versioned assertions and explicit denominators.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import time
from typing import cast
from .ports import KnowledgeRetriever
from .contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult
from .query_catalog import QueryCatalog
from .errors import invalid, KnowledgeError
from .evaluation_assertions import judge


async def evaluate(
    retriever: KnowledgeRetriever, cases: list[dict] | dict, *, query_catalog: QueryCatalog | None = None
) -> dict:
    """Execute reviewed cases; expectations are consumed only after actual retrieval.

    Args:
        retriever: Configured serving port.
        cases: Legacy reviewed list or explicit version-two reviewed case pack.

    Returns:
        Serialized actual evidence, independent verdicts, measures and coverage limits.

    Keyword-only query_catalog: Same trusted catalog used by normal research.
    """
    rich = isinstance(cases, dict)
    pack = cases if isinstance(cases, dict) else {"cases": cases}
    if rich and pack.get("evaluation_version") != "2":
        invalid(
            "evaluation objects require explicit version 2 adaptation; planned specifications are not runnable"
        )
    authored = pack.get("cases", [])
    if not isinstance(authored, list) or len(authored) > 500:
        invalid("evaluation needs at most 500 explicit cases")
    rows = [await _case(retriever, case, pack, rich, query_catalog) for case in authored]
    report: dict[str, object] = {
        "evaluation_version": "2" if rich else "1",
        "cases": rows,
        "semantic_usefulness_proven": False,
        "quality_thresholds": "unset pending representative real-model reviewed baseline",
    }
    if rich:
        verdicts = Counter(row["verdict"] for row in rows)
        report.update(
            denominators={
                "total": len(rows),
                "executed": sum(row["execution_state"] == "executed" for row in rows),
                "passed": verdicts["passed"],
                "failed": verdicts["failed"],
                "not_run": verdicts["not_run"],
            },
            execution_status_counts=dict(Counter(row.get("status", "not_run") for row in rows)),
            coverage=pack.get("coverage", {}),
            source_sha=pack.get("source_sha"),
            reviewed_by=pack.get("reviewed_by"),
            review_fingerprint=hashlib.sha256(
                json.dumps(pack, sort_keys=True).encode()
            ).hexdigest(),
            answer_semantics_version="required-fields-v1",
            implementation_digest=_implementation_digest(),
            comparison_state="baseline required; no promotion decision",
        )
    return report


async def _case(
    retriever: KnowledgeRetriever, case: dict, pack: dict, rich: bool, catalog: QueryCatalog | None
) -> dict:
    """Run a case once, retaining not-run state and independent expectations.

    Args:
        retriever: Actual configured serving port.
        case: One independently reviewed case.
        pack: Case-set review and source metadata.
        rich: Whether version-two assertions apply.
        catalog: Optional trusted operation catalog.

    Returns:
        One measured case report with actual output and independent verdict.
    """
    reviewer = case.get("reviewed_by") or pack.get("reviewed_by")
    if not reviewer:
        invalid("evaluation cases require reviewed judgments")
    state = case.get("state", "runnable")
    base = {
        "id": case["id"],
        "specification_state": state,
        "family": case.get("family"),
        "category": case.get("category"),
        "reviewed_by": reviewer,
    }
    if state != "runnable":
        return {
            **base,
            "execution_state": "not_run",
            "verdict": "not_run",
            "reason": case.get("reason", "case is not runnable"),
            "actual": None,
        }
    started = time.perf_counter()
    try:
        actual, row = await _execute_case(retriever, case, catalog)
    except (KnowledgeError, ValueError) as exc:
        actual = {"status": getattr(exc, "code", "error"), "message": str(exc)}
        row = {
            "id": case["id"],
            "status": actual["status"],
            "precision_at_k": None,
            "recall_at_k": None,
            "provenance_validity": None,
        }
    row["end_to_end_ms"] = round((time.perf_counter() - started) * 1000, 3)
    if not rich:
        return row
    expected = case.get("assertions", [])
    judgments = [judge(actual, assertion) for assertion in expected]
    judgments.extend(_scope_judgments(actual, case, pack))
    passed = bool(expected) and all(item["passed"] for item in judgments)
    return {
        **base,
        **row,
        "execution_state": "executed",
        "verdict": "passed" if passed else "failed",
        "actual": actual,
        "expected": expected,
        "judgments": judgments,
    }


def _scope_judgments(actual: dict, case: dict, pack: dict) -> list[dict]:
    """Validate requested oracle scope while retaining genuine unavailable source pins.

    Args:
        actual: Actual serialized response.
        case: Executed request or supplied assessment packet.
        pack: Reviewed immutable source binding.

    Returns:
        Source identity judgments appropriate to the observed execution state.
    """
    sha = pack.get("source_sha")
    if not sha:
        return []
    request = case.get("request", case.get("assessment", {}))
    revision = request.get("revision", request.get("source_sha", "latest"))
    judgments = []
    if revision != "latest":
        judgments.append(
            judge(
                {"requested_source_sha": revision}, {"path": "requested_source_sha", "equals": sha}
            )
        )
    if actual.get("status") not in {"unavailable", "unsupported", "disabled", "error", "stale"}:
        judgments.append(judge(actual, {"path": "source_sha", "equals": sha}))
    return judgments


async def _execute_case(
    retriever: KnowledgeRetriever, case: dict, catalog: QueryCatalog | None
) -> tuple[dict, dict]:
    """Invoke the actual public retrieval or assessment consumer before any grading.

    Args:
        retriever: Configured research serving port.
        case: Reviewed executable request or supplied assessment packet.
        catalog: Optional trusted query catalog.

    Returns:
        Actual serialized output and applicable measured fields.
    """
    if "assessment" in case:
        if "request" in case:
            invalid("evaluation case must choose retrieval or supplied assessment")
        from .assessments import assess

        actual = assess(case["assessment"])
        return actual, {
            "id": case["id"],
            "status": actual["status"],
            "precision_at_k": None,
            "recall_at_k": None,
            "provenance_validity": None,
            "measurement_kind": "supplied_evidence_assessment",
        }
    raw = case.get("request")
    request = (
        catalog.request(cast(dict, raw))
        if catalog
        else KnowledgeRetrievalRequest.model_validate(raw)
    )
    result = await retriever.retrieve(request)
    return result.model_dump(mode="json"), _metrics(case, request, result)


def _metrics(case: dict, request: KnowledgeRetrievalRequest, result: KnowledgeRetrievalResult) -> dict:
    """Measure relevance only for successful complete retrieval, retaining every state.

    Args:
        case: Reviewed expected entity and correction identities.
        request: Actual validated request.
        result: Actual retrieval response.

    Returns:
        Measurements, with null quality measures for incomplete execution.
    """
    returned = {item.entity.canonical_id for item in result.evidence}
    relevant = set(case.get("relevant_ids", []))
    corrections = set(case.get("correction_ids", []))
    valid = sum(
        item.entity.source.repository_id == request.repository_id
        and item.entity.source.source_sha == result.source_sha
        and bool(item.entity.source.path)
        for item in result.evidence
    )
    successful = result.status == "ok" and not result.truncated
    return {
        "id": case["id"],
        "synthetic": case.get("synthetic", False),
        "status": result.status,
        "precision_at_k": (
            len(returned & relevant) / len(returned) if returned else float(not relevant)
        )
        if successful
        else None,
        "recall_at_k": (
            len(returned & relevant) / len(relevant) if relevant else float(not returned)
        )
        if successful
        else None,
        "correction_coverage": (
            len(returned & corrections) / len(corrections) if corrections else 1.0
        )
        if successful
        else None,
        "provenance_validity": (valid / len(result.evidence) if result.evidence else 1.0)
        if successful
        else None,
        "content_bytes": len(result.model_dump_json().encode()),
        "latency_ms": result.stats.get("duration_ms"),
        "source_sha": result.source_sha,
        "generation_id": result.generation_id,
        "query_version": result.operation_version,
        "query_digest": request.operation_digest or "builtin:1",
        "embedding_model": result.stats.get("embedding_model"),
        "mapper_version": result.stats.get("mapper_version"),
        "result_count": len(result.evidence),
    }


def _implementation_digest() -> str | None:
    """Fingerprint the executing answer contract without confusing it with source-data SHA."""
    from pathlib import Path

    root = Path(__file__).parent
    names = (
        "contracts.py",
        "answer_models.py",
        "answers.py",
        "disclosure.py",
        "populations.py",
        "projection/canonical_loader.py",
    )
    try:
        content = b"".join(name.encode() + b"\0" + (root / name).read_bytes() for name in names)
    except OSError:
        return None
    return hashlib.sha256(content).hexdigest()


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Grade actual serialized responses with reviewed versioned oracles. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500d-3)
