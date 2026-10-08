"""
MODULE: kernel.intent.gap_quality
GOAL: Make capability gap records readable and honest: a per-capability exclusion reason, a
    ranked and capped "closest capabilities" list, and a readable title for the need.
BUSINESS CONTEXT: A gap is product evidence for the backlog (Rev 3 section 14); a draft that
    lists every capability unranked, without saying why each one was excluded, or titles the need
    with a sorted bag of words, cannot be acted on.
ARCHITECTURE: Pure functions over routing assessments' exclusion lists; no scheduler imports. The
    dedup identity stays the normalised need in the gap key; the readable text is a separate
    field.
"""

from __future__ import annotations

from collections.abc import Iterable

from kernel.contracts.decision import ExcludedCandidate

#: How many "closest capabilities" a gap record and its draft list.
MAX_CLOSEST = 5
MAX_TITLE_CHARS = 80
#: Output schema recorded for a decline: the kernel produces no output for it.
NO_OUTPUT_SCHEMA = "none"
_NEED_PHRASES = {"evidence": "evidence retrieval", "options": "option generation",
                 "synthesis": "evidence synthesis"}
#: Reasons ordered from "nearly fits" to "far away" (first failing check order, reversed).
_CLOSENESS = ("permission_denied", "side_effect_forbidden", "budget_exhausted", "scope_mismatch",
              "output_schema_mismatch", "payload_schema_mismatch", "kind_mismatch",
              "binding_missing", "unavailable", "disabled")


def reason_rank(reason: str) -> int:
    """Return how far a reason code is from a fit (lower is closer; unknown codes last)."""
    base = reason.split(":", 1)[0]
    return _CLOSENESS.index(base) if base in _CLOSENESS else len(_CLOSENESS)


def exclusion_map(excluded: Iterable[ExcludedCandidate]) -> dict[str, str]:
    """Return `{capability_id: reason_code}` for the excluded candidates."""
    return {e.capability_id: e.reason_code for e in excluded}


def rank_closest(eligible: Iterable[str], exclusions: dict[str, str],
                 limit: int = MAX_CLOSEST) -> list[str]:
    """Return the closest capabilities: eligible-but-failed first, then by exclusion reason.

    Args:
        eligible: Ids that were eligible but did not (or could not) serve the request.
        exclusions: `{capability_id: reason_code}` of the excluded ones.
        limit: Maximum list length.

    Returns:
        list[str]: Capability ids, closest first, ties broken by id, capped at `limit`.
    """
    ranked = sorted(set(eligible))
    ranked += sorted((c for c in exclusions if c not in ranked),
                     key=lambda c: (reason_rank(exclusions[c]), c))
    return ranked[:limit]


def readable_need(goal: str, limit: int = MAX_TITLE_CHARS) -> str:
    """Return the original goal on one line, truncated for use in titles."""
    flat = " ".join(goal.split())
    return flat if len(flat) <= limit else flat[:limit - 3].rstrip() + "..."


def need_phrase(request_kind: str, normalized_need: str, need_title: str) -> str:
    """Return the need as a phrase for titles: the capability asked for, not the root goal.

    A gap about a typed child request (evidence, options, synthesis) names that operation and its
    category; the goal that caused it is unrelated to what to build. Free-form capability gaps
    keep their readable need.
    """
    kind = str(getattr(request_kind, "value", request_kind))
    label = _NEED_PHRASES.get(kind)
    if label is None:
        return need_title or normalized_need
    detail = normalized_need if normalized_need and normalized_need != kind else ""
    return f"{label} ({detail})" if detail else label


def describe_candidate(capability_id: str, exclusions: dict[str, str]) -> str:
    """Return one bullet text: the capability and, when known, why it was excluded."""
    reason = exclusions.get(capability_id)
    return f"{capability_id} (excluded: {reason})" if reason else f"{capability_id} (eligible)"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: Gap draft titles come from the need (`need_phrase`): a
#   synthesis or evidence child gap was titled with the root goal that happened to trigger it.
#   (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: The dedup key keeps the normalised (sorted token) need while
#   titles use a separate readable field, so aggregation across runs is unchanged and a title
#   reads like the goal. (#KernelBootstrapV0/INTENT)
# ====================================================================
