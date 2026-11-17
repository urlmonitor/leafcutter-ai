"""Source-attributed clause comparison with explicitly supplied interpretations.
MODULE: knowledge.assessment_clauses
GOAL: Preserve compared literal clauses without selecting authority from similarity.
BUSINESS CONTEXT: A proposed conflict or duplicate is not a canonical source rewrite.
ARCHITECTURE: Bounded neutral assessment over supplied scoped quotes; no discovery or mutation.
"""

from __future__ import annotations
from .assessment_evidence import quoted
from .errors import invalid


def compare_clauses(payload: dict, evidence: list[dict]) -> dict:
    """Retain supported clauses and label a separately supplied candidate interpretation.

    Args:
        payload: Scoped packet with bounded clauses and an optional proposed interpretation.
        evidence: Content already accepted by the common source-scope validation.

    Returns:
        Literal clauses, an attributed inference when supported, and no authority claim.
    """
    requested = payload.get("clauses", [])
    if not isinstance(requested, list) or len(requested) > 32:
        invalid("clause comparison accepts at most 32 supplied clauses")
    indexed = {item["evidence_id"]: item for item in evidence}
    clauses, limitations, identities, anchors = [], [], set(), set()
    for candidate in requested:
        clause = _clause(candidate, indexed)
        anchor = _anchor(clause) if clause else None
        if clause is None or clause["clause_id"] in identities or anchor in anchors:
            limitations.append(
                "compared clause lacks a unique identity and literal scoped supporting quote"
            )
            continue
        clauses.append(clause)
        identities.add(clause["clause_id"])
        anchors.add(anchor)
    interpretation = _interpretation(payload.get("interpretation"), identities)
    if interpretation is None:
        limitations.append(
            "a bounded explicit interpretation citing at least two supported clauses is absent"
        )
    limitations.append(
        "candidate relations are supplied inference; similarity establishes neither equivalence nor source authority"
    )
    return {
        "kind": "clause_comparison",
        "status": "partial" if interpretation else "unresolved",
        "clauses": clauses,
        "interpretation": interpretation,
        "equivalence_established": False,
        "authoritative_clause_id": None,
        "limitations": limitations,
    }


def _clause(candidate: object, indexed: dict) -> dict | None:
    """Select only a named clause whose literal quote occurs in accepted supplied content.

    Args:
        candidate: One untrusted proposed clause.
        indexed: Accepted content keyed by evidence identity.

    Returns:
        Exact quote and source attribution, or None for unsupported content.
    """
    if not isinstance(candidate, dict):
        return None
    identifier = candidate.get("clause_id")
    evidence_id = candidate.get("evidence_id")
    if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 200:
        return None
    if not isinstance(evidence_id, str):
        return None
    item = indexed.get(evidence_id)
    if not quoted(item, candidate.get("quote")):
        return None
    return {
        "clause_id": identifier,
        "evidence_id": evidence_id,
        "quote": candidate["quote"],
        "source": dict(item["source"]),
    }


def _anchor(clause: dict) -> tuple:
    """Distinguish actual compared source clauses from two aliases of the same quote.

    Args:
        clause: Supported literal clause and immutable source attribution.

    Returns:
        Identity of the actual source quote, independent of caller-assigned aliases.
    """
    source = clause["source"]
    return (
        source["repository_id"],
        source["source_sha"],
        source["path"],
        source.get("locator", ""),
        clause["quote"],
    )


def _interpretation(proposal: object, identities: set[str]) -> dict | None:
    """Accept a bounded proposal only when it cites distinct supported clauses.

    Args:
        proposal: Separately supplied relation, rationale and clause identities.
        identities: Clause identities supported by literal scoped content.

    Returns:
        Explicitly inferred non-authoritative proposal, or None when unsupported.
    """
    if not isinstance(proposal, dict) or proposal.get("relation") not in (
        "conflict",
        "duplicate",
        "uncertain",
    ):
        return None
    rationale, cited = proposal.get("rationale"), proposal.get("clause_ids")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 4000:
        return None
    if not isinstance(cited, list) or not 2 <= len(cited) <= 32:
        return None
    if not all(isinstance(identifier, str) for identifier in cited):
        return None
    if len(set(cited)) != len(cited) or not set(cited).issubset(identities):
        return None
    return {
        "relation": proposal["relation"],
        "clause_ids": list(cited),
        "rationale": rationale,
        "inferred": True,
        "authoritative": False,
    }


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Preserve compared literal clauses and keep candidate relations separate from source authority. (#KM-500/KM-500e-2)
