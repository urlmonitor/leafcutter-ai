"""Public conditional evidence-assessment port, independent from discovery.
MODULE: knowledge.assessments
GOAL: Expose honest evidence interpretation through standalone and retrieval paths.
BUSINESS CONTEXT: Supplied evidence may support a bounded interpretation without proving a live run.
ARCHITECTURE: Neutral read-only consumer; injected actual retrieval outranks packet declarations.
"""

from __future__ import annotations
from .assessment_evidence import prepare
from .assessment_proof import verification
from .errors import invalid


def assess(
    payload: dict, *, retrieval: object | None = None, manifest: object | None = None
) -> dict:
    """Assess supplied evidence and, when present, the final actual retrieval result.

    Args:
        payload: Explicit bounded scope and supplied evidence packet.

    Returns:
        Attributed interpretation, explicit limitations and no independent provenance claim.

    Keyword-only retrieval: Actual final disclosed response; never an expected oracle.
    Keyword-only manifest: Actual pinned manifest for source fitness when available.
    """
    evidence, limitations = prepare(payload)
    declarations = _declarations(payload, retrieval)
    kind = payload.get("kind")
    if kind == "clause_comparison":
        from .assessment_clauses import compare_clauses

        result = compare_clauses(payload, evidence)
    elif kind == "impact":
        from .assessment_impact import impact

        result = impact(payload)
    elif kind == "verification":
        result = verification(payload, evidence, declarations)
    elif kind == "capability_fit":
        from .capability_fit import assess_capability_fit

        inputs = dict(payload.get("requirements", {}))
        for name, default in (("matching_operation", None), ("catalog_complete", False)):
            if name in payload and name in inputs and payload[name] != inputs[name]:
                invalid("conflicting capability assessment " + name)
            inputs.setdefault(name, payload.get(name, default))
        result = assess_capability_fit(manifest or payload.get("manifest", {}), **inputs)
    elif kind in {"readiness", "implementation", "regression"}:
        from .assessment_interpretation import interpret

        result = interpret(payload, evidence, declarations, retrieval)
    else:
        invalid("unsupported evidence assessment kind")
    result["limitations"] = limitations + result.get("limitations", [])
    result.update(
        repository_id=payload["repository_id"],
        source_sha=payload["source_sha"],
        evidence_basis="supplied evidence; attribution is not independently verified",
        discovery="actual disclosed declarations"
        if retrieval is not None
        else "supplied packet only",
    )
    if retrieval is not None:
        _bind_retrieval(result, payload, retrieval)
    return result


def _declarations(payload: dict, retrieval: object | None) -> list[str]:
    """Use actual canonical links when called from research; ignore packet overrides.

    Args:
        payload: Requested assessment packet.
        retrieval: Actual final disclosed response, if available.

    Returns:
        Actual canonical references or explicitly supplied standalone declarations.
    """
    if retrieval is None:
        value = payload.get("declarations", [])
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
    fields = (
        ("covered_by",)
        if payload.get("kind") == "verification"
        else ("implemented_by", "covered_by")
    )
    return [
        reference
        for item in retrieval.evidence
        for field in fields
        for reference in (item.entity.properties.get(field) or [])
        if isinstance(reference, str)
    ]


def _bind_retrieval(result: dict, payload: dict, retrieval: object) -> None:
    """Refuse to credit supplied reports against failed or differently scoped retrieval.

    Args:
        result: Assessment output to constrain by actual retrieval.
        payload: Requested repository and source scope.
        retrieval: Actual final research response.
    """
    same = retrieval.source_sha == payload["source_sha"] and all(
        item.entity.source.repository_id == payload["repository_id"] for item in retrieval.evidence
    )
    if not same or retrieval.status not in {"ok", "partial"}:
        result["status"] = "unresolved"
        result["limitations"].append(
            "actual retrieval does not establish the supplied assessment scope"
        )
        if "receipts" in result:
            result["receipts"], result["executed_proof"] = [], "unverified"


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Make conditional assessment reachable through actual research without oracle backfill. (#KM-500/KM-500f-2)
