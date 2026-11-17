"""Bounded source and regression interpretations from supplied literal evidence.
MODULE: knowledge.assessment_interpretation
GOAL: Retain inspected locations while exposing unsupported stages and test-design gaps.
BUSINESS CONTEXT: Filenames and static source cannot establish runtime causation or exhaustive coverage.
ARCHITECTURE: Pure quote validation over scoped input; no new inspection permissions.
"""

from __future__ import annotations
from .contracts import KnowledgeRetrievalResult
from .assessment_evidence import quoted, structured


def interpret(
    payload: dict, evidence: list[dict], declarations: list[str], retrieval: KnowledgeRetrievalResult | None = None
) -> dict:
    """Dispatch a conditional interpretation using only provided attributable content.

    Args:
        payload: Requested bounded interpretation and candidate statements.
        evidence: Scoped supplied content.
        declarations: Actual retrieved or explicitly supplied references.
        retrieval: Optional actual disclosed response for canonical candidate facts.

    Returns:
        Bounded interpretation with explicit source and execution limits.
    """
    if payload["kind"] == "readiness":
        from .assessment_readiness import readiness

        return readiness(payload, evidence, retrieval)
    if payload["kind"] == "regression":
        return _regression(payload, evidence)
    return _implementation(payload, evidence, declarations)


def _implementation(payload: dict, evidence: list[dict], declarations: list[str]) -> dict:
    """Admit source stages only with literal scoped content and keep runtime separate.

    Args:
        payload: Requested stages and optional runtime attempt identity.
        evidence: Scoped content actually supplied for inspection.
        declarations: Actual retrieved or supplied implementation references.

    Returns:
        Bounded source interpretation and separately attributed runtime evidence.
    """
    indexed = {
        item["evidence_id"]: item for item in evidence if item.get("kind") == "source_excerpt"
    }
    stages, limitations = [], []
    for stage in payload.get("stages", []):
        item = indexed.get(stage.get("evidence_id"))
        if not quoted(item, stage.get("quote")):
            limitations.append("source stage lacks an inspected literal supporting quote")
            continue
        stages.append(
            {
                "name": stage.get("name"),
                "evidence_id": item["evidence_id"],
                "quote": stage["quote"],
                "source": item["source"],
                "interpretation": True,
            }
        )
    cause = _runtime_cause(payload, evidence)
    limitations.append("bounded source interpretation does not establish a complete code graph")
    if cause is None:
        limitations.append("matching runtime request/attempt diagnostic evidence is absent")
    return {
        "kind": "implementation",
        "status": "partial" if stages else "unresolved",
        "stages": stages,
        "declared_references": declarations,
        "runtime_cause": cause,
        "complete_code_graph": False,
        "limitations": limitations,
    }


def _runtime_cause(payload: dict, evidence: list[dict]) -> dict | None:
    """Retain only an explicitly attributed diagnostic for the matching attempt.

    Args:
        payload: Requested runtime request, attempt and source identities.
        evidence: Scoped diagnostic content supplied for this assessment.

    Returns:
        Matching attributed diagnostic claim, or None when unestablished.
    """
    required = ("request_id", "attempt_id", "source_sha")
    if not all(payload.get(name) for name in required):
        return None
    for item in evidence:
        if item.get("kind") != "runtime_diagnostic":
            continue
        value = structured(item)
        if (
            value
            and all(value.get(name) == payload[name] for name in required)
            and value.get("cause")
        ):
            return {
                "reported_cause": value["cause"],
                **{name: value[name] for name in required},
                "evidence_id": item["evidence_id"],
                "source": item["source"],
                "independently_verified": False,
            }
    return None


def _regression(payload: dict, evidence: list[dict]) -> dict:
    """Keep fixture interpretations and missing comparison evidence visible.

    Args:
        payload: Proposed fixture interpretations and inspected change scope.
        evidence: Scoped fixture or test source content.

    Returns:
        Evidence-backed candidate reruns with explicit test-design gaps.
    """
    indexed = {
        item["evidence_id"]: item
        for item in evidence
        if item.get("kind") in {"fixture", "source_excerpt"}
    }
    recommendations, gaps = [], []
    fields = (
        "test_id",
        "behavior",
        "seeded_facts",
        "expected_result",
        "comparison_case",
        "actual_boundaries",
        "simulated_boundaries",
    )
    for inspection in payload.get("inspections", []):
        item = indexed.get(inspection.get("evidence_id"))
        if not quoted(item, inspection.get("quote")):
            gaps.append("fixture recommendation lacks inspected supporting content")
            continue
        missing = [
            name for name in fields if inspection.get(name) is None or inspection.get(name) == ""
        ]
        if missing:
            gaps.append("fixture evidence missing " + ", ".join(missing))
        recommendations.append(
            {
                **{name: inspection.get(name) for name in fields},
                "source": item["source"],
                "evidence_id": item["evidence_id"],
                "quote": inspection["quote"],
                "interpretation": True,
                "executed_branch_proof": "unverified",
            }
        )
    if not recommendations:
        gaps.append("inspected test/fixture evidence is unavailable")
    return {
        "kind": "regression",
        "status": "partial" if recommendations else "unresolved",
        "recommendations": recommendations,
        "design_gaps": gaps,
        "exhaustive": False,
        "minimal": False,
        "change_scope": payload.get("change_scope"),
        "limitations": [
            "bounded recommendations do not prove executed coverage or a complete consumer graph"
        ],
    }


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Bound source and fixture interpretation by actual quoted content. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500f-4)
