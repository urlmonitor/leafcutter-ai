"""Typed verification claims over actual declarations and supplied execution reports.
MODULE: knowledge.assessment_proof
GOAL: Separate canonical test references from historical reports and observed proof.
BUSINESS CONTEXT: Done status, filenames and scripted actors do not establish live success.
ARCHITECTURE: Pure conditional assessment; no repository discovery or execution.
"""

from __future__ import annotations
from .assessment_evidence import structured
from .assessment_quotes import quoted_report


def verification(payload: dict, evidence: list[dict], declarations: list[str]) -> dict:
    """Retain each supported supplied report's own identities and scope.

    Args:
        payload: Requested assessment scope.
        evidence: Scoped supplied content from the common evidence filter.
        declarations: Actually retrieved references, or explicitly supplied standalone references.

    Returns:
        Declared references, supported report records and explicit proof limitations.
    """
    receipts, limitations = [], []
    for item in evidence:
        if item.get("kind") != "execution_receipt":
            continue
        content = structured(item)
        quoted = quoted_report(item) if content is None else None
        if not _valid_receipt(content) and quoted is None:
            limitations.append(
                "execution report format or required identity is unsupported: "
                + item["evidence_id"]
            )
            continue
        receipts.append(
            {
                **_reported_fields(content or quoted),
                "proof_kind": "supplied_quoted_report" if quoted else "supplied_execution_report",
                "evidence_id": item["evidence_id"],
                "source": item["source"],
                "provenance_verified": False,
            }
        )
    if not receipts:
        limitations.append(
            "execution evidence is unverified; declared references alone do not establish a run"
        )
    return {
        "kind": "verification",
        "status": "partial" if receipts or declarations else "unresolved",
        "declared_references": sorted(set(declarations)),
        "receipts": receipts,
        "executed_proof": "reported" if receipts else "unverified",
        "limitations": limitations,
        "independent_execution_verified": False,
    }


def _reported_fields(content: dict) -> dict:
    """Return only the documented proof vocabulary, never arbitrary packet fields.

    Args:
        content: Decoded and validated supplied report fields.

    Returns:
        Only documented report claims and their interpretation metadata.
    """
    names = {
        "tested_sha",
        "run_id",
        "environment",
        "actor",
        "execution_status",
        "research_fulfillment",
        "test_ids",
        "deployment",
        "artifact_locator",
        "provider_execution",
        "quoted_claims",
        "reviewed_by",
        "interpretation",
    }
    return {name: value for name, value in content.items() if name in names}


def _valid_receipt(value: dict | None) -> bool:
    """Accept the explicit structured report format while retaining every claimed state.

    Args:
        value: Decoded explicitly structured execution report.

    Returns:
        Whether all required report identities and literal states are present.
    """
    if not value:
        return False
    names = (
        "tested_sha",
        "run_id",
        "environment",
        "actor",
        "execution_status",
        "research_fulfillment",
    )
    return (
        all(isinstance(value.get(name), str) and value[name] for name in names)
        and len(value["tested_sha"]) == 40
        and all(c in "0123456789abcdef" for c in value["tested_sha"])
        and isinstance(value.get("test_ids"), list)
        and all(isinstance(name, str) for name in value["test_ids"])
    )


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Keep store SHA, tested SHA, actor and fulfillment independent. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500f-2)
