"""Preserve scoped conditional assessments through the kernel retrieval boundary.
MODULE: integrations.knowledge_assessment
GOAL: Reassess actual bounded evidence without upgrading supplied reports to facts.
BUSINESS CONTEXT: A successful query does not independently verify a historical report.
ARCHITECTURE: Application adapter over the existing neutral assessment function.
"""
from __future__ import annotations

import json
from knowledge.contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult
from knowledge.assessment_evidence import prepare
from knowledge.assessments import assess
from knowledge.errors import KnowledgeError


def bind_assessment(outer: dict | None, inner: dict | None, repository_id: str,
                    revision: str) -> dict | None:
    """Validate caller packet scope without changing its evidence or historical revision.

    Args:
        outer: Optional kernel request packet.
        inner: Optional explicitly supplied neutral packet.
        repository_id: Trusted configured repository identity.
        revision: Trusted pinned source revision or latest.

    Returns:
        Unmodified packet, or None when no assessment was requested.
    """
    if outer is not None and inner is not None and outer != inner:
        raise KnowledgeError("invalid_request", "conflicting assessment packets")
    packet = outer if outer is not None else inner
    if packet is None:
        return None
    prepare(packet)
    if packet["repository_id"] != repository_id or (
        revision != "latest" and packet["source_sha"] != revision
    ):
        raise KnowledgeError("scope_mismatch", "assessment differs from trusted source scope")
    return packet


def finalize_assessment(request: KnowledgeRetrievalRequest, result: KnowledgeRetrievalResult) -> bool:
    """Interpret only the actual evidence remaining after kernel disclosure bounds.

    Args:
        request: Original scoped neutral request.
        result: Final authorized and bounded neutral response.

    Returns:
        Whether the supplied evidence assessment remains conditional or unresolved.
    """
    if request.assessment is None:
        return False
    if (result.assessment is not None
        and "response_budget_exhausted" in result.assessment.get("limitations", [])):
        return True  # The neutral envelope already spent its budget; never restore removed content.
    result.assessment = assess(request.assessment, retrieval=result)
    return result.assessment.get("status") not in {"fulfilled", "supported"}


def assessment_diagnostics(result: KnowledgeRetrievalResult) -> dict[str, str]:
    """Serialize an attributable assessment for existing public capability diagnostics.

    Args:
        result: Final bounded neutral response.

    Returns:
        Additive JSON diagnostic or an empty mapping.
    """
    return ({"knowledge_assessment": json.dumps(result.assessment, sort_keys=True)}
            if result.assessment is not None else {})


def assessment_limits(result: KnowledgeRetrievalResult) -> list[str]:
    """Return explicit conditional interpretation limits for the public evidence bundle.

    Args:
        result: Final neutral result with recomputed assessment.

    Returns:
        Bounded assessment limitations, empty when no obligation remains.
    """
    report = result.assessment
    if report is None or report.get("status") in {"fulfilled", "supported"}:
        return []
    return [*report.get("limitations", []),
            "Conditional evidence assessment remains " + report.get("status", "unresolved")]


def assessment_bundle(result: KnowledgeRetrievalResult, need_id: str, *,
                      include_answer: bool = False) -> dict[str, dict]:
    """Key the actual finalized assessment by the evidence need it answers.

    Args:
        result: Final neutral result.
        need_id: Original need identity.

    Returns:
        Per-need report mapping without source-fact promotion.

    Keyword-only include_answer adds deterministic obligations for the interpreted public path.
    """
    if not include_answer or result.answer is None:
        return {need_id: result.assessment} if result.assessment is not None else {}
    report = {"kind": "retrieval_answer", **result.answer.model_dump(mode="json")}
    if result.assessment is not None:
        report["conditional_assessment"] = result.assessment
        if result.assessment.get("status") not in {"fulfilled", "supported"}:
            report["status"] = "unresolved"
    return {need_id: report}


# DECISION HISTORY
# - 2026-10-01 23:00 [python-coder]: Preserve scoped conditional assessment through real research. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500f-2)

# - 2026-10-09 15:40 [python-coder]: Preserve typed question obligations through public research and scoped query selection. (#KM-500/KM-500e-1-i)
