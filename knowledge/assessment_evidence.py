"""Bounded supplied evidence validation for conditional research interpretation.
MODULE: knowledge.assessment_evidence
GOAL: Keep supplied content, attribution and independently verified provenance distinct.
BUSINESS CONTEXT: A report filename or caller boolean is not observed execution.
ARCHITECTURE: Pure input validation; this module performs no source or network reads.
"""

from __future__ import annotations
import json
from .contracts import SourceReference
from .errors import invalid


def prepare(payload: dict) -> tuple[list[dict], list[str]]:
    """Select attributable scoped supplied content without claiming to verify its source.

    Args:
        payload: Bounded assessment packet with repository and immutable source scope.

    Returns:
        Admissible supplied evidence and explicit excluded-content limitations.
    """
    if not isinstance(payload, dict) or len(json.dumps(payload).encode()) > 131072:
        invalid("assessment packet must be an object of at most 131072 bytes")
    if not payload.get("repository_id") or not isinstance(payload.get("source_sha"), str):
        invalid("assessment requires repository and immutable source scope")
    if len(payload["source_sha"]) != 40 or any(
        c not in "0123456789abcdef" for c in payload["source_sha"]
    ):
        invalid("assessment source_sha must be immutable")
    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) > 100:
        invalid("assessment needs at most 100 supplied evidence items")
    accepted, limitations, seen = [], [], set()
    for item in evidence:
        issue = _issue(item, payload, seen)
        if issue:
            limitations.append(issue)
        else:
            accepted.append(item)
            seen.add(item["evidence_id"])
    return accepted, limitations


def _issue(item: dict, payload: dict, seen: set[str]) -> str | None:
    """Validate scope and content while refusing opaque approval booleans.

    Args:
        item: Supplied evidence item to validate.
        payload: Requested repository and immutable source scope.
        seen: Evidence identities already accepted.

    Returns:
        Attributable exclusion reason, or None for admissible supplied content.
    """
    if (
        not isinstance(item, dict)
        or not isinstance(item.get("content"), str)
        or not item.get("content")
    ):
        return "supplied evidence content is missing"
    if (
        not isinstance(item.get("evidence_id"), str)
        or not item["evidence_id"]
        or item["evidence_id"] in seen
    ):
        return "supplied evidence identity is missing or duplicated"
    try:
        source = SourceReference.model_validate(item.get("source"))
    except (ValueError, TypeError):
        return "supplied source reference is invalid"
    if (
        source.repository_id != payload["repository_id"]
        or source.source_sha != payload["source_sha"]
    ):
        return "supplied evidence is outside requested repository or source revision"
    return None


def structured(item: dict) -> dict | None:
    """Decode an explicitly supplied JSON object; never manufacture parsed Markdown."""
    try:
        value = json.loads(item["content"])
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def quoted(item: dict | None, quote: object) -> bool:
    """Require a nonempty literal quote in the actual supplied excerpt."""
    return bool(item and isinstance(quote, str) and quote.strip() and quote in item["content"])


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Do not turn attributed packets into independently verified source proof. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500f-2)
