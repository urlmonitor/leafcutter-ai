"""
ac_triage.py — Python implementation of the AC triage logic.

This module provides a Python-callable interface to the triage routing logic
used by the /plan-feature workflow. It is called by create_ac_workflow.py and
tested by tests/ac_store/test_create_ac_workflow.py.

The JavaScript counterpart (plan-feature.js) dispatches the ac-triage agent
template (Haiku-pinned, read-only). This Python module mirrors that logic
for unit-testing purposes and for use in CI pipelines that cannot invoke
the agent runtime.

Source ticket: EPIC-ACDrivenDevelopment/08_create_ac_workflow.md
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Route constants
# ---------------------------------------------------------------------------

ROUTE_STRATEGIC = "strategic"
ROUTE_BEHAVIORAL = "behavioral"
ROUTE_TECHNICAL = "technical"
ROUTE_COVERED = "covered"

VALID_ROUTES = {ROUTE_STRATEGIC, ROUTE_BEHAVIORAL, ROUTE_TECHNICAL, ROUTE_COVERED}

# Keywords that suggest a request is adding a technical constraint rather
# than a new behaviour.  Heuristic; used by classify_request when no full
# semantic match is found.
_TECHNICAL_KEYWORDS = frozenset([
    "latency", "response time", "sla", "rate limit", "rate-limit",
    "throughput", "timeout", "error rate", "error threshold",
    "p99", "p95", "p50", "percentile",
    "must respond in", "must complete in", "within < ", "under ",
    "security", "encryption", "tls", "authentication", "authoriz",
])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_request(
    user_request: str,
    component: str | None,
    ac_store: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify the user's natural-language request against the AC store.

    Parameters
    ----------
    user_request:
        The user's free-text description of the feature or requirement.
    component:
        Optional component name to filter the AC store (e.g. "inventory").
        If None, all active ACs are considered.
    ac_store:
        List of AC YAML dicts (as loaded from docs/acceptance-criteria/).
        Each entry should have at least: id, title, component, level,
        status, criteria, readiness.

    Returns
    -------
    dict with keys:
        route        — one of "strategic" | "behavioral" | "technical" | "covered"
        existing_acs — list of relevant AC IDs (empty for strategic)
        parent_l1_id — matched L1 AC ID for behavioral route; None otherwise
        rationale    — one sentence explaining the decision
    """
    # 1. Filter to active ACs for the relevant component(s).
    active_acs = _filter_active(ac_store, component)

    if not active_acs:
        return _result(
            ROUTE_STRATEGIC,
            existing_acs=[],
            parent_l1_id=None,
            rationale="No active ACs found for component — treating as new capability.",
        )

    request_lower = user_request.lower()

    # 2. Covered check — does any AC criteria text directly describe the same scenario?
    covered_ids = _find_covered(request_lower, active_acs)
    if covered_ids:
        return _result(
            ROUTE_COVERED,
            existing_acs=covered_ids,
            parent_l1_id=None,
            rationale=f"Request semantically matches existing AC(s): {', '.join(covered_ids[:2])}.",
        )

    # 3. L1 match — does any L1 AC describe the same feature being extended?
    l1_match = _find_l1_match(request_lower, active_acs)
    if l1_match:
        return _result(
            ROUTE_BEHAVIORAL,
            existing_acs=[l1_match],
            parent_l1_id=l1_match,
            rationale=f"Matching L1 AC {l1_match} found — routing as behavioral addition.",
        )

    # 4. Technical constraint check.
    if _is_technical_constraint(request_lower, active_acs):
        technical_ids = [ac["id"] for ac in active_acs[:3]]  # most relevant ACs
        return _result(
            ROUTE_TECHNICAL,
            existing_acs=technical_ids,
            parent_l1_id=None,
            rationale="Request adds a technical constraint to an existing capability.",
        )

    # 5. Default: new capability.
    return _result(
        ROUTE_STRATEGIC,
        existing_acs=[],
        parent_l1_id=None,
        rationale="No matching L1 AC or covered scenario found — treating as new capability.",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _filter_active(
    ac_store: list[dict[str, Any]],
    component: str | None,
) -> list[dict[str, Any]]:
    """Return ACs that are active and match the component filter."""
    result = []
    for ac in ac_store:
        status = ac.get("status", "active")
        if status in ("deprecated", "superseded_by"):
            continue
        if component and ac.get("component", "").lower() != component.lower():
            continue
        result.append(ac)
    return result


def _find_covered(
    request_lower: str,
    active_acs: list[dict[str, Any]],
) -> list[str]:
    """Return AC IDs whose criteria text closely matches the request."""
    covered: list[str] = []
    req_words = set(_tokenize(request_lower))

    for ac in active_acs:
        criteria_text = (ac.get("criteria", "") + " " + ac.get("title", "")).lower()
        ac_words = set(_tokenize(criteria_text))
        # Jaccard similarity > 0.35 → consider covered.
        if req_words and ac_words:
            intersection = req_words & ac_words
            union = req_words | ac_words
            similarity = len(intersection) / len(union)
            if similarity > 0.35:
                covered.append(ac["id"])

    return covered


def _find_l1_match(
    request_lower: str,
    active_acs: list[dict[str, Any]],
) -> str | None:
    """Return the ID of the first L1 AC whose title domain overlaps the request."""
    req_words = set(_tokenize(request_lower))

    for ac in active_acs:
        if ac.get("level") != "L1":
            continue
        title_words = set(_tokenize(ac.get("title", "").lower()))
        if req_words and title_words:
            overlap = req_words & title_words
            # If 30%+ of the L1 title tokens appear in the request → behavioral match.
            if len(overlap) / len(title_words) >= 0.30:
                return ac["id"]

    return None


def _is_technical_constraint(
    request_lower: str,
    active_acs: list[dict[str, Any]],
) -> bool:
    """Return True if the request reads as a technical constraint addition."""
    # Keyword heuristic.
    for kw in _TECHNICAL_KEYWORDS:
        if kw in request_lower:
            return True
    return False


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase alpha tokens; remove stop words."""
    _STOP = frozenset([
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall",
        "can", "to", "of", "in", "for", "on", "with", "at", "by",
        "from", "as", "into", "through", "during", "and", "or", "but",
        "not", "no", "so", "if", "when", "then", "that", "this",
        "it", "its", "their", "user", "users", "given", "when",
    ])
    tokens = re.findall(r"[a-z]+", text)
    return [t for t in tokens if t not in _STOP and len(t) > 2]


def _result(
    route: str,
    existing_acs: list[str],
    parent_l1_id: str | None,
    rationale: str,
) -> dict[str, Any]:
    """Build a triage result dict."""
    return {
        "route": route,
        "existing_acs": existing_acs,
        "parent_l1_id": parent_l1_id,
        "rationale": rationale,
    }
