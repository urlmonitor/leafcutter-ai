"""Explicit reviewed literal claims over otherwise unstructured report content.
MODULE: knowledge.assessment_quotes
GOAL: Consume historical Markdown without guessing prose semantics or inventing run identity.
BUSINESS CONTEXT: Attributed report interpretation is useful but is not independently verified execution.
ARCHITECTURE: Every admitted value must occur in a literal quote within the supplied content.
"""

from __future__ import annotations
from .assessment_evidence import quoted

_FIELDS = {
    "tested_sha",
    "run_id",
    "environment",
    "actor",
    "execution_status",
    "research_fulfillment",
    "test_ids",
    "artifact_locator",
    "provider_execution",
}
_REQUIRED = {"tested_sha", "environment", "actor", "execution_status", "research_fulfillment"}


def quoted_report(item: dict) -> dict | None:
    """Validate each reviewed literal claim without performing semantic extraction.

    Args:
        item: Supplied report content with explicit reviewer-attributed quoted claims.

    Returns:
        Supported quoted report interpretation, or None when required support is absent.
    """
    claims = item.get("claims", {})
    if not isinstance(claims, dict) or not item.get("reviewed_by") or set(claims) - _FIELDS:
        return None
    values = {}
    for name, claim in claims.items():
        if not isinstance(claim, dict) or not quoted(item, claim.get("quote")):
            return None
        value = claim.get("value")
        parts = value if isinstance(value, list) else [value]
        if not parts or any(
            not isinstance(part, str) or not part or part not in claim["quote"] for part in parts
        ):
            return None
        values[name] = value
    if not _valid_identity(values):
        return None
    values.setdefault("run_id", None)
    values.setdefault("test_ids", [])
    return {
        **values,
        "quoted_claims": claims,
        "reviewed_by": item["reviewed_by"],
        "proof_kind": "supplied_quoted_report",
        "interpretation": True,
    }


def _valid_identity(values: dict) -> bool:
    """Require literal string identities and an immutable tested revision.

    Args:
        values: Claims already backed by exact report quotes.

    Returns:
        Whether all required report identities are valid literal strings.
    """
    if not _REQUIRED <= set(values) or not all(
        isinstance(values.get(name), str) for name in _REQUIRED
    ):
        return False
    return len(values["tested_sha"]) == 40 and all(
        c in "0123456789abcdef" for c in values["tested_sha"]
    )


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Preserve original report quotes and historical identities without fabricated structured records. (#KM-500/KM-500f-2)
